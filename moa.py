"""GA Mixture-of-Agents 多智能体聚合 (P3 ⑨ 落地 / SOP §14.2 P3)

Together AI MoA 范式：多 Proposer 并行生成 → Aggregator 综合。
复用现有多 session + quality_estimator + routing_log 基础设施。

调研依据：
- MoA (Together AI, 2024)：多 Proposer 生成 + Aggregator 综合，复杂推理/创意/代码质量提升
- LLM-as-Judge 实践：quality_estimator 对各 proposal 评分，加权/选择/聚合

设计：三阶段流水线
- Phase 1 propose：多模型并行（threading）生成候选响应
- Phase 2 score：quality_estimator 对各候选评分（0-1）
- Phase 3 aggregate：有 aggregator → 主模型综合多候选；无 → 选最高分（轻量模式）

接入方式：暴露为 `moa` 工具（模型主动触发，低风险，非主流程），经 handler.parent.llmclients 访问多模型。
"""
import threading
from quality_estimator import estimate_quality


class MixtureOfAgents:
    """多智能体聚合：多 proposer 并行 + 质量评分 + 聚合。"""

    def __init__(self, clients, aggregator_client=None, max_proposers=3, judge_level='L1', orm=None, clients_provider=None):
        self.proposers = [c for c in clients[:max_proposers] if c is not None and not isinstance(c, dict)]
        self.aggregator = aggregator_client
        self.judge_level = judge_level
        self.orm = orm                       # P3⑦ 集成: propose 后自动 record 消耗
        self.clients_provider = clients_provider  # 动态获取当前 clients(感知 handoff/切换)
        self._max_proposers = max_proposers
        self._lock = threading.Lock()

    def _get_proposers(self):
        """动态获取 proposers: 有 provider 则每次 ask 时重新解析(感知 handoff 后 llmclients 变化)。"""
        if self.clients_provider:
            try:
                cs = self.clients_provider()
                return [c for c in cs[:self._max_proposers] if c is not None and not isinstance(c, dict)]
            except Exception:
                pass
        return self.proposers

    def _propose_one(self, client, messages, out, idx):
        try:
            resp = ""
            # 纯生成模式：不传 tools，避免 proposer 调工具（聚合阶段才综合）
            gen = client.chat(messages=messages, tools=[])
            for ch in gen:
                if isinstance(ch, str):
                    resp += ch
            with self._lock:
                out[idx] = resp if resp.strip() else None
            # P3⑦ 集成: 自动记录 token 消耗到 ORM (用 client.model 作 key; token 粗估)
            if self.orm is not None:
                try:
                    be = getattr(client, 'backend', client)
                    model = getattr(be, 'model', getattr(client, 'name', 'unknown'))
                    in_t = sum(len(str(m.get('content', ''))) // 4 for m in messages)
                    self.orm.record(model, in_t, max(1, len(resp) // 4), 0.0)
                except Exception:
                    pass
        except Exception:
            with self._lock:
                out[idx] = None

    @staticmethod
    def _build_agg_prompt(user_msg, proposals):
        """构建 aggregator 综合提示：原文 + 各候选 + 综合指令。"""
        parts = [f"[用户原始请求]\n{user_msg}\n\n[多个模型的候选响应]"]
        for i, (ridx, txt, qs) in enumerate(proposals):
            parts.append(f"\n--- 候选 {i + 1}（模型{ridx}，质量分 {qs.score:.2f}）---\n{txt}")
        parts.append(
            "\n\n[综合指令] 以上是多个模型对同一请求的候选响应。请综合它们的优点、修正不足，"
            "输出一个高质量最终响应。保留正确信息，去除冗余/错误，结构清晰。直接输出最终答案。")
        return [{"role": "user", "content": "\n".join(parts)}]

    def ask(self, messages):
        """执行 MoA 三阶段。messages: [{"role":"user","content":...}]。返回 (final_text, scored, meta)。"""
        # Phase 1: 并行 propose (动态获取 proposers, 感知 handoff/切换后 llmclients 变化)
        proposers = self._get_proposers()
        out = [None] * len(proposers)
        threads = []
        for i, c in enumerate(proposers):
            t = threading.Thread(target=self._propose_one, args=(c, messages, out, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        # Phase 2: score（过滤空/失败）
        scored = []
        for i, txt in enumerate(out):
            if txt:
                qs = estimate_quality(txt, level=self.judge_level)
                scored.append((i, txt, qs))
        if not scored:
            return None, [], {'reason': 'all_proposers_failed'}
        # Phase 3: aggregate
        user_msg = next((m.get('content', '') for m in messages if m.get('role') == 'user'), '')
        if self.aggregator and len(scored) >= 2:
            try:
                agg_messages = self._build_agg_prompt(user_msg, scored)
                final = ""
                for ch in self.aggregator.chat(messages=agg_messages, tools=[]):
                    if isinstance(ch, str):
                        final += ch
                if final.strip():
                    return final, scored, {'mode': 'aggregate', 'best_score': max(s.score for _, _, s in scored)}
            except Exception:
                pass  # aggregator 失败 → 退回选最高分
        # 轻量模式：选最高分 proposal
        best = max(scored, key=lambda x: x[2].score)
        return best[1], scored, {'mode': 'best', 'best_idx': best[0], 'best_score': best[2].score}
