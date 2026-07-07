"""GA 响应质量估计器 (P2 质量估计器落地 / SOP §14.2 ④⑤ 共同前提)

分层评估 LLM 响应质量，为 Cascade(④) / Planner-Executor(⑤) / Handoff(②) 提供升级依据。

调研依据（SOP v1.7 论文）：
- FrugalGPT (Chen 2023)：cascade 按置信度/评分逐级上更大模型
- RouteLLM (Ong 2024)：偏好数据训练轻量 router，cost-quality trade-off
- LLM-as-Judge 实践：明确评分标准 + 采样评估（非全量）+ 启发式预过滤降成本

设计：分层评估，成本递增、可开关
- L0 硬信号层（零成本，复用 P0）：max_tokens 截断 / 格式损坏 / 异常中断
- L1 启发式层（低成本，纯规则）：过短 / 重复循环 / 拒绝模式 / 空垃圾响应
- L2 LLM-Judge 层（高成本，config 开关 + judge_fn 注入）：裁判 LLM 打分融合

原则：估计器永不抛异常影响主流程；judge_fn 由调用方注入避免硬依赖。
"""
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Any


@dataclass
class QualityScore:
    score: float                      # 0.0-1.0，越高越好
    level: str                        # 'L0' / 'L1' / 'L2'
    signals: list = field(default_factory=list)   # 触发的信号描述
    suggest_escalate: bool = False    # score < 阈值 → 建议升级/handoff


# ── L1 启发式信号检测器（纯规则，零额外 LLM 调用）──
def _sig_empty_garbage(text: str) -> bool:
    """空响应或仅标点/空白（无实质字母/汉字）"""
    if not text or not text.strip():
        return True
    return not re.search(r'[a-zA-Z\u4e00-\u9fff]', text)


def _sig_too_short(text: str, threshold: int = 30) -> bool:
    """响应实质内容过短（< threshold 字符）"""
    return len(text.strip()) < threshold


_REFUSAL_PATTERNS = [
    r'我不能', r'无法协助', r'无法帮助', r'抱歉.{0,6}不能', r'作为.{0,4}(AI|人工智能|语言模型)',
    r'I\s+cannot', r"I\s+can'?t\s+(help|assist|do)", r"I'm\s+sorry.{0,20}(can'?t|unable|not\s+able)",
    r'作为.{0,4}AI.{0,10}(不能|无法|不可以)',
]
def _sig_refusal(text: str) -> bool:
    """拒绝模式（明确表示无法完成任务）"""
    return any(re.search(p, text, re.IGNORECASE) for p in _REFUSAL_PATTERNS)


def _sig_repetition(text: str, dup_ratio: float = 0.6) -> bool:
    """重复循环：trigram 重复占比超 dup_ratio（模型卡在循环输出）"""
    words = text.split()
    if len(words) < 15:    # 短文本不检测
        return False
    trigrams = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
    if not trigrams:
        return False
    unique_ratio = len(set(trigrams)) / len(trigrams)
    return (1 - unique_ratio) > dup_ratio   # 重复 trigram 占比 > 阈值


# ── L0 硬信号（复用 P0 / llmcore 已有检测，零成本）──
def _detect_hard_signals(text: str, llm_warn: Optional[str] = None) -> list:
    """从响应文本/warn 字符串检测硬质量信号"""
    out = []
    blob = (text or '') + '\n' + (llm_warn or '')
    if '[!!! Response truncated: max_tokens' in blob:
        out.append('max_tokens_truncated')
    if '[!!! 流异常中断' in blob:
        out.append('stream_interrupted')
    if '_raw' in blob and 'malformed' in blob.lower():    # tool args 格式损坏标记
        out.append('malformed_tool_args')
    return out


def estimate_quality(
    response_text: str,
    level: str = 'L1',
    judge_fn: Optional[Callable[[str], float]] = None,
    llm_warn: Optional[str] = None,
    escalate_threshold: float = 0.5,
) -> QualityScore:
    """评估 LLM 响应质量。

    Args:
        response_text: 模型响应文本
        level: 'L0'(仅硬信号) / 'L1'(硬+启发式) / 'L2'(全层含LLM-judge)
        judge_fn: L2 层裁判函数 fn(text)->float(0-1)，由调用方注入
        llm_warn: llmcore 生成的 warn 字符串（用于 L0 硬信号检测）
        escalate_threshold: score < 此值 → suggest_escalate=True
    Returns:
        QualityScore
    """
    signals = []
    score = 1.0

    # ── L0 硬信号层 ──
    hard = _detect_hard_signals(response_text, llm_warn)
    if hard:
        signals.extend(hard)
        score = min(score, 0.15)    # 硬信号 = 近乎失败

    # ── L1 启发式层 ──
    if level in ('L1', 'L2'):
        if _sig_empty_garbage(response_text):
            signals.append('empty_garbage'); score = min(score, 0.1)
        else:
            if _sig_too_short(response_text):
                signals.append('too_short'); score -= 0.3
            if _sig_repetition(response_text):
                signals.append('repetition'); score -= 0.4
            if _sig_refusal(response_text):
                signals.append('refusal'); score -= 0.5
        score = max(0.0, score)

    # ── L2 LLM-Judge 层（可选）──
    if level == 'L2' and judge_fn is not None:
        try:
            j = float(judge_fn(response_text))
            if 0.0 <= j <= 1.0:
                score = (score + j) / 2.0          # 规则分与裁判分融合
                signals.append(f'llm_judge={j:.2f}')
        except Exception:
            pass    # judge 失败不影响主评估

    score = round(max(0.0, min(1.0, score)), 2)
    return QualityScore(
        score=score,
        level=level,
        signals=signals,
        suggest_escalate=score < escalate_threshold,
    )
