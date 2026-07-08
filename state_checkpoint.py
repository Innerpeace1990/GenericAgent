"""GA 会话状态检查点/持久化 (P3 ⑥ 落地 / SOP §14.2 P3)

轻量状态切片：保存/恢复关键会话状态到 json，支持断电/重启后恢复。
"""

import json, os, time, threading

_LOCK = threading.Lock()
_CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', 'checkpoints')


def _cp_path(namespace, d=None):
    d = d or _CHECKPOINT_DIR
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'state_{namespace}.json')


def save_checkpoint(state, namespace='default', checkpoint_dir=None):
    try:
        cp = _cp_path(namespace, checkpoint_dir)
        entry = dict(state)
        entry['_timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        entry['_epoch'] = time.time()
        with _LOCK:
            data = {}
            if os.path.exists(cp) and os.path.getsize(cp) > 0:
                data = json.loads(open(cp, encoding='utf-8').read())
            data[namespace] = entry
            with open(cp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_checkpoint(namespace='default', checkpoint_dir=None):
    try:
        cp = _cp_path(namespace, checkpoint_dir)
        if not os.path.exists(cp):
            return None
        data = json.loads(open(cp, encoding='utf-8').read())
        return data.get(namespace)
    except Exception:
        return None


def delete_checkpoint(namespace='default', checkpoint_dir=None):
    try:
        cp = _cp_path(namespace, checkpoint_dir)
        if os.path.exists(cp) and os.path.getsize(cp) > 0:
            data = json.loads(open(cp, encoding='utf-8').read())
            data.pop(namespace, None)
            with open(cp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ===== P1: 任务级接续 (Task Continuity) =====
# 依据: durable execution 范式 (conductor/LangGraph checkpoint) —— 状态持久化，崩溃从断点恢复。

_TASK_NS_PREFIX = 'task_'


def save_task_state(task_id, description='', plan=None, current_step=0,
                    completed_steps=None, key_findings=None, context_snapshot=None):
    """保存任务执行状态，支持意外中断后接续。
    复杂任务(>=3步)应在 plan 建立后及每完成一步时调用。"""
    state = {
        'task_id': task_id,
        'description': description,
        'plan': plan or [],
        'current_step': current_step,
        'completed_steps': completed_steps or [],
        'key_findings': key_findings or [],
        'context_snapshot': context_snapshot or {},
        'status': 'in_progress',
    }
    save_checkpoint(state, namespace=_TASK_NS_PREFIX + task_id)
    return task_id


def load_task_state(task_id):
    """加载任务状态用于接续。返回 dict 或 None。"""
    return load_checkpoint(namespace=_TASK_NS_PREFIX + task_id)


def list_active_tasks():
    """列出所有 in_progress 的任务（供会话启动时检查是否有未完成任务）。"""
    try:
        if not os.path.exists(_CHECKPOINT_DIR):
            return []
        results = []
        for f in os.listdir(_CHECKPOINT_DIR):
            if f.startswith('state_task_') and f.endswith('.json'):
                try:
                    data = json.loads(open(os.path.join(_CHECKPOINT_DIR, f), encoding='utf-8').read())
                    for ns, st in data.items():
                        if st and st.get('status') == 'in_progress':
                            results.append({
                                'task_id': st.get('task_id', ''),
                                'description': st.get('description', '')[:60],
                                'progress': f"{st.get('current_step', 0)}/{len(st.get('plan', []))}",
                                'updated': st.get('_timestamp', ''),
                            })
                except Exception:
                    pass
        return results
    except Exception:
        return []


def complete_task_state(task_id):
    """任务完成：标记 completed 并清除 checkpoint（有进有出）。"""
    st = load_task_state(task_id)
    if st:
        st['status'] = 'completed'
        save_checkpoint(st, namespace=_TASK_NS_PREFIX + task_id)
    delete_checkpoint(namespace=_TASK_NS_PREFIX + task_id)
