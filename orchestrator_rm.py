"""GA Orch-RM 资源调度 (P3 ⑦ 落地 / SOP §14.2 P3)

核心编排层资源管理：token 预算追踪 + 限流(RPM/TPM) + 配额决策。
差异化：cost_tracker 是前端显示，本模块是核心编排层路由决策依据（影响 Bandit/Handoff）。

设计：低风险纯新模块，不碰现有流程
- record(): 记录 token 消耗（per-model input/output/cost）
- can_acquire(): 限流决策（RPM/TPM/日预算）
- should_throttle(): 预算预警（>80% 日预算）
- 持久化 + 线程安全
"""
import json, os, time, threading, datetime
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque


@dataclass
class TokenRecord:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    ts: float = field(default_factory=time.time)


class OrchestratorRM:
    def __init__(self, rpm_limit=0, tpm_limit=0, daily_budget=0.0, state_path=None):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.daily_budget = daily_budget
        self.state_path = state_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'temp', 'orch_rm_state.json')
        self._lock = threading.Lock()
        self._records = []
        self._per_model = defaultdict(lambda: {'input': 0, 'output': 0, 'cost': 0.0, 'count': 0})
        self._rpm_window = deque()
        self._tpm_window = deque()
        self._load()

    def record(self, model, input_tokens, output_tokens, cost):
        with self._lock:
            r = TokenRecord(model, input_tokens, output_tokens, cost)
            self._records.append(r)
            m = self._per_model[model]
            m['input'] += input_tokens
            m['output'] += output_tokens
            m['cost'] += cost
            m['count'] += 1
            now = r.ts
            self._rpm_window.append(now)
            self._tpm_window.append((now, input_tokens + output_tokens))
            self._prune(now)
            self._save()

    def _prune(self, now):
        while self._rpm_window and now - self._rpm_window[0] > 60:
            self._rpm_window.popleft()
        while self._tpm_window and now - self._tpm_window[0][0] > 60:
            self._tpm_window.popleft()

    def can_acquire(self):
        now = time.time()
        with self._lock:
            self._prune(now)
            if self.rpm_limit and len(self._rpm_window) >= self.rpm_limit:
                return False, 'rpm_limit'
            if self.tpm_limit and sum(t for _, t in self._tpm_window) >= self.tpm_limit:
                return False, 'tpm_limit'
        if self.daily_budget and self._today_cost() >= self.daily_budget:
            return False, 'daily_budget'
        return True, None

    def _today_cost(self):
        today = datetime.date.today().toordinal()
        return sum(r.cost for r in self._records
                   if datetime.date.fromtimestamp(r.ts).toordinal() == today)

    def should_throttle(self):
        if not self.daily_budget:
            return False
        return self._today_cost() / self.daily_budget > 0.8

    def stats(self):
        with self._lock:
            return {k: dict(v) for k, v in self._per_model.items()}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            data = {'records': [asdict(r) for r in self._records[-500:]]}
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load(self):
        try:
            if os.path.exists(self.state_path) and os.path.getsize(self.state_path) > 0:
                data = json.loads(open(self.state_path, encoding='utf-8').read())
                for rd in data.get('records', []):
                    m = self._per_model[rd['model']]
                    m['input'] += rd.get('input_tokens', 0)
                    m['output'] += rd.get('output_tokens', 0)
                    m['cost'] += rd.get('cost', 0.0)
                    m['count'] += 1
        except Exception:
            pass
