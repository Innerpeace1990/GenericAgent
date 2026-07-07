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
