"""GA Cost-aware MoA 决策门 (基于真实验证: MoA简单任务浪费成本)

真实模型验证发现: MoA简单任务QE=0.30 < 单模型0.70(浪费3x成本), 复杂任务持平。
决策门: 简单任务直接走最优单模型(省成本), 复杂任务才启用MoA。

复杂度评估信号:
- 查询长度 (长→复杂)
- 复杂关键词 (代码/推理/创意/架构/分析) vs 简单关键词 (翻译/问候/定义)
"""
import re

_COMPLEX_KW = ['写代码','实现','解释原理','分析','对比','设计','优化','debug','重构',
               '算法','函数','架构','证明','推导','规划','方案','评审','总结长文','转换复杂']
_SIMPLE_KW = ['你好','翻译','日期','时间','今天是','定义是什么','几点','叫什么',
              '在吗','谢谢','是的','好的']


def assess_complexity(query):
    """评估查询复杂度。返回 (score 0-1, signals list)。"""
    if not query:
        return 0.0, ['empty']
    score = 0.0
    signals = []
    q = query.strip()
    qlen = len(q)
    # 长度信号
    if qlen > 200: score += 0.35; signals.append('long_query(%d)' % qlen)
    elif qlen > 80: score += 0.15; signals.append('medium_query(%d)' % qlen)
    # 复杂关键词 (强信号)
    matched_cplx = [k for k in _COMPLEX_KW if k in q]
    if matched_cplx: score += 0.4; signals.append('complex_kw:%s' % ','.join(matched_cplx[:2]))
    # 多指令/多步骤 (分号/编号/列表)
    if q.count('\n') >= 2 or len(re.findall(r'[1-9][\.、)]', q)) >= 2:
        score += 0.2; signals.append('multi_step')
    # 简单关键词 (负信号)
    matched_simple = [k for k in _SIMPLE_KW if k in q]
    if matched_simple: score -= 0.35; signals.append('simple_kw:%s' % ','.join(matched_simple[:2]))
    # 纯短问答
    if qlen < 15 and not matched_cplx: score -= 0.2; signals.append('very_short')
    return round(max(0.0, min(1.0, score)), 2), signals


def should_use_moa(query, threshold=0.3):
    """决策门: 复杂度 >= threshold 才启用MoA。返回 (use_bool, complexity, signals)。"""
    complexity, signals = assess_complexity(query)
    return complexity >= threshold, complexity, signals
