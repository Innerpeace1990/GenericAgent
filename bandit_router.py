"""GA Bandit 自适应模型路由 (P3 落地 / SOP §14.2 P3)

UCB1 多臂老虎机：根据历史质量奖励自适应选模型，探索-利用平衡。
让多模型选择从"固定顺序 failover"升级为"数据驱动"。

调研依据：
- RouteLLM (Ong 2024)：偏好数据训练轻量 router，cost-quality trade-off
- Multi-Armed Bandit 经典 UCB1 (Auer 2002)：ucb = mean + c·√(ln N / n)

设计：
- 奖励信号：quality_estimator 的 QualityScore.score (0-1，越高越好)
- 探索系数 c=√2（标准 UCB1），可调
- 冷启动：均匀探索（优先未选过的 arm）
- 状态持久化：bandit_state.json（多 namespace 隔离，如不同任务类型）
- 线程安全 + 异常兜底（持久化/加载失败不影响路由）
"""
import json, os, math, threading
from dataclasses import dataclass, asdict

_LOCK = threading.Lock()
_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', 'bandit_state.json')


@dataclass
class ArmStats:
    count: int = 0
    total_reward: float = 0.0

    @property
    def mean(self):
        return self.total_reward / self.count if self.count > 0 else 0.0


class UCB1Bandit:
    """UCB1 自适应路由器。n_arms=模型数，select()→选最优arm，update(arm,reward)→反馈。"""

    def __init__(self, n_arms, explore_c=None, state_path=None, namespace=''):
        if n_arms < 1:
            raise ValueError("n_arms must be >= 1")
        self.n_arms = n_arms
        self.c = explore_c if explore_c is not None else math.sqrt(2)
        self.namespace = namespace or 'default'
        self.arms = [ArmStats() for _ in range(n_arms)]
        self.total = 0
        self.state_path = state_path or _STATE_PATH
        self._load()

    def select(self):
        """UCB1 选 arm。冷启动优先未探索的（count==0）；否则取 ucb 最大。"""
        for i, a in enumerate(self.arms):
            if a.count == 0:
                return i
        if self.total <= 0:
            return 0
        ln_total = math.log(self.total)
        best_i, best_ucb = 0, -1.0
        for i, a in enumerate(self.arms):
            ucb = a.mean + self.c * math.sqrt(ln_total / a.count)
            if ucb > best_ucb:
                best_ucb, best_i = ucb, i
        return best_i

    def update(self, arm_idx, reward):
        """反馈 reward（归一化到 [0,1]）给 arm_idx。持久化。"""
        if not (0 <= arm_idx < self.n_arms):
            return
        reward = max(0.0, min(1.0, float(reward)))
        with _LOCK:
            self.arms[arm_idx].count += 1
            self.arms[arm_idx].total_reward += reward
            self.total += 1
            self._save()

    def stats(self):
        return [{'arm': i, 'count': a.count, 'mean': round(a.mean, 3)} for i, a in enumerate(self.arms)]

    def _load(self):
        try:
            if not os.path.exists(self.state_path):
                return
            with open(self.state_path, encoding='utf-8') as f:
                data = json.load(f)
            state = data.get(self.namespace)
            if not state:
                return
            for i, a in enumerate(state.get('arms', [])):
                if i < self.n_arms:
                    self.arms[i] = ArmStats(count=a.get('count', 0), total_reward=a.get('total_reward', 0.0))
            self.total = state.get('total', 0)
        except Exception:
            pass  # 加载失败用默认空状态

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            data = {}
            if os.path.exists(self.state_path):
                try:
                    with open(self.state_path, encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[self.namespace] = {'arms': [asdict(a) for a in self.arms], 'total': self.total}
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 持久化失败不影响路由
