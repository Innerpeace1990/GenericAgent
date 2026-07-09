"""飞书群消息监控与历史拉取工具模块 (feishu group tools)

基于飞书官方 API：
- 获取会话历史消息 message.list: https://open.feishu.cn/document/server-docs/im-v1/message/list
- 获取群列表 chat.list: https://open.feishu.cn/document/server-docs/group/chat/list
- 服务端 SDK lark_oapi (Python)

本模块提供：
1. list_chats()           - 列出机器人所在的所有群
2. list_messages()        - 拉取指定群的最近历史消息
3. save_message()         - 持久化收到的群消息到 data/feishu_messages/<chat_id>.jsonl
4. summarize_chat()       - 拉取群消息并整理成可总结的文本（供 LLM 总结）
5. search_messages()      - 按关键词在持久化消息中搜索
6. find_chat_by_name()    - 按群名/关键词查找 chat_id

设计原则：
- 所有函数都用同一个 lark Client（懒加载），避免重复创建
- 持久化采用 JSONL 追加，按 chat_id 分文件
- 供 GA agent 通过 code_run 调用，也可被 fsapp.py 内部 handle_command 直接调用
"""
import json
import os
import time
import threading
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import ListChatRequest, ListMessageRequest
from lark_oapi.api.contact.v3 import GetUserRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "feishu_messages"

_client = None
_client_lock = threading.Lock()

# 与 fsapp.py 一致的配置键名
_FS_APP_ID = os.environ.get("FS_APP_ID", "")
_FS_APP_SECRET = os.environ.get("FS_APP_SECRET", "")


def set_credentials(app_id: str, app_secret: str):
    """由 fsapp.py 启动时注入真实凭证（优先级高于环境变量）。"""
    global _FS_APP_ID, _FS_APP_SECRET, _client
    with _client_lock:
        if app_id:
            _FS_APP_ID = app_id
        if app_secret:
            _FS_APP_SECRET = app_secret
        _client = None  # 强制重建


def _get_client():
    """懒加载 lark Client。优先用 fsapp 注入的凭证，其次环境变量。"""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        if not _FS_APP_ID or not _FS_APP_SECRET:
            # 尝试从 fsapp 模块读取已初始化的全局凭证
            try:
                import fsapp  # noqa
                if getattr(fsapp, "APP_ID", "") and getattr(fsapp, "APP_SECRET", ""):
                    return fsapp.client or fsapp.create_client()
            except Exception:
                pass
        if not _FS_APP_ID or not _FS_APP_SECRET:
            raise RuntimeError(
                "飞书凭证未配置：请通过 set_credentials() 注入，或设置 FS_APP_ID/FS_APP_SECRET 环境变量"
            )
        _client = (
            lark.Client.builder()
            .app_id(_FS_APP_ID)
            .app_secret(_FS_APP_SECRET)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
        return _client


# ─────────────────────────────────────────────────────────
# 发言人姓名解析 contact.user.get
# ─────────────────────────────────────────────────────────
_NAME_CACHE = {}


def resolve_sender_name(open_id, sender_type=None):
    """解析单个发送者的显示名。

    优先级：app→🤖机器人；否则调 contact.user.get 取 name/en_name/nickname。
    受限于应用权限，可能返回 None（此时调用方应做"成员N"降级）。
    结果带缓存（含 None，避免重复请求）。
    """
    if sender_type == "app" or not open_id:
        return "🤖机器人" if sender_type == "app" else None
    if open_id in _NAME_CACHE:
        return _NAME_CACHE[open_id]
    name = None
    try:
        client = _get_client()
        req = GetUserRequest.builder().user_id(open_id).user_id_type("open_id").build()
        resp = client.contact.v3.user.get(req)
        if resp.success() and resp.data and resp.data.user:
            u = resp.data.user
            name = getattr(u, "name", None) or getattr(u, "en_name", None) or getattr(u, "nickname", None) or None
    except Exception:
        pass
    _NAME_CACHE[open_id] = name  # None 也缓存
    return name


def build_sender_map(messages):
    """为一批消息构建 open_id→显示名 的映射。

    拿到真名的用真名；拿不到的统一分配稳定编号"成员1/成员2…"（按首次出现顺序）。
    """
    seen = []
    id_set = set()
    for m in messages:
        if (m.get("sender_type") or "") == "app":
            continue
        sid = m.get("sender_id") or ""
        if sid and sid not in id_set:
            id_set.add(sid)
            seen.append(sid)
    name_map = {}
    member_idx = 0
    for sid in seen:
        real = resolve_sender_name(sid)
        if real:
            name_map[sid] = real
        else:
            member_idx += 1
            name_map[sid] = f"成员{member_idx}"
    return name_map


# ─────────────────────────────────────────────────────────
# 群列表 chat.list
# ─────────────────────────────────────────────────────────
def list_chats(page_size: int = 100, max_pages: int = 10):
    """列出机器人所在的所有群。

    Returns:
        dict: {"chats": [...], "count": N}，每个元素含 chat_id, name, chat_mode,
              member_count, description, external, owner_id
        若出错返回 {"error": "..."}
    """
    client = _get_client()
    chats = []
    page_token = None
    pages = 0
    while pages < max_pages:
        builder = ListChatRequest.builder().user_id_type("open_id").page_size(min(page_size, 100))
        if page_token:
            builder = builder.page_token(page_token)
        req = builder.build()
        resp = client.im.v1.chat.list(req)
        if not resp.success():
            return {"error": f"chat.list failed: code={resp.code} msg={resp.msg} log_id={resp.get_log_id()}"}
        data = resp.data
        if data is None:
            break
        for item in (getattr(data, "items", None) or []):
            chats.append({
                "chat_id": getattr(item, "chat_id", ""),
                "name": getattr(item, "name", ""),
                "description": getattr(item, "description", ""),
                "chat_mode": getattr(item, "chat_mode", ""),  # group / p2p
                "chat_type": getattr(item, "chat_type", ""),  # private / public
                "external": getattr(item, "external", None),
                "owner_id": getattr(item, "owner_id", ""),
                "member_count": getattr(item, "member_count", 0),
            })
        page_token = getattr(data, "page_token", None)
        has_more = getattr(data, "has_more", False)
        pages += 1
        if not has_more or not page_token:
            break
    return {"chats": chats, "count": len(chats)}


def find_chat_by_name(keyword: str, page_size: int = 100):
    """按群名关键词模糊查找，返回匹配的群列表。

    Args:
        keyword: 群名包含的关键词
    Returns:
        dict: {"chats": [...], "count": N}；若 list_chats 出错返回 {"error": "..."}
    """
    kw = (keyword or "").strip().lower()
    res = list_chats(page_size=page_size)
    if isinstance(res, dict) and "error" in res:
        return res
    chats = res.get("chats", []) if isinstance(res, dict) else res
    if not kw:
        return {"chats": chats, "count": len(chats)}
    matched = []
    for c in chats:
        name = (c.get("name") or "").lower()
        desc = (c.get("description") or "").lower()
        if kw in name or kw in desc:
            matched.append(c)
    return {"chats": matched, "count": len(matched)}


# ─────────────────────────────────────────────────────────
# 消息历史 message.list
# ─────────────────────────────────────────────────────────
def _extract_message_text(msg, msg_type=None):
    """从消息对象中提取纯文本内容（兼容 text/post）。

    message.list 返回的 body.content 是 JSON 字符串。
    """
    body = getattr(msg, "body", None)
    if body is None:
        return ""
    content_str = getattr(body, "content", "") or ""
    if msg_type is None:
        msg_type = getattr(body, "message_type", "") or getattr(msg, "msg_type", "")
    if msg_type == "text" or msg_type == "":
        try:
            cobj = json.loads(content_str) if content_str else {}
            if isinstance(cobj, dict):
                return cobj.get("text", "") or ""
        except Exception:
            return content_str
        return ""
    if msg_type == "post":
        try:
            cobj = json.loads(content_str) if content_str else {}
            title = cobj.get("title", "")
            lines = []
            lang_content = cobj.get("content", cobj)
            if isinstance(lang_content, dict):
                # 可能嵌套 {zh_cn: {title, content}}
                for _k, v in lang_content.items():
                    if isinstance(v, dict) and "content" in v:
                        lang_content = v
                        title = title or v.get("title", "")
                        break
            content = lang_content.get("content", []) if isinstance(lang_content, dict) else []
            for para in content:
                if isinstance(para, list):
                    parts = []
                    for el in para:
                        if isinstance(el, dict):
                            tag = el.get("tag", "")
                            if tag == "text":
                                parts.append(el.get("text", ""))
                            elif tag == "at":
                                parts.append(f"@{el.get('user_name', el.get('user_id', ''))}")
                            elif tag == "a":
                                parts.append(el.get("text", el.get("href", "")))
                    if parts:
                        lines.append("".join(parts))
            text = ("\n".join(lines)).strip()
            if title:
                text = f"【{title}】\n{text}"
            return text
        except Exception:
            return content_str[:200]
    # 其他类型(image/file/...)返回类型标识
    return f"[{msg_type}]"


def list_messages(chat_id: str, limit: int = 50, start_time: str = None, end_time: str = None):
    """拉取指定群的最近历史消息（按时间倒序，最新在前）。

    Args:
        chat_id: 群的 chat_id（以 oc_ 开头）
        limit: 最多返回多少条（会自动分页，每页最多50）
        start_time: 起始时间（毫秒时间戳字符串），可选
        end_time: 结束时间（毫秒时间戳字符串），可选
    Returns:
        list[dict]: 每条消息含 message_id, create_time(秒), sender_id, sender_type,
                    msg_type, text, chat_id
        若出错返回 {"error": "..."}
    """
    if not chat_id:
        return {"error": "chat_id 不能为空（以 oc_ 开头）"}
    client = _get_client()
    messages = []
    page_token = None
    pages = 0
    max_pages = max(1, (limit // 50) + 2)
    while pages < max_pages and len(messages) < limit:
        builder = (
            ListMessageRequest.builder()
            .container_id_type("chat")
            .container_id(chat_id)
            .sort_type("ByCreateTimeDesc")
            .page_size(min(50, limit - len(messages)) if not page_token else 50)
        )
        if start_time:
            builder = builder.start_time(str(start_time))
        if end_time:
            builder = builder.end_time(str(end_time))
        if page_token:
            builder = builder.page_token(page_token)
        req = builder.build()
        resp = client.im.v1.message.list(req)
        if not resp.success():
            return {"error": f"message.list failed: code={resp.code} msg={resp.msg} log_id={resp.get_log_id()}"}
        data = resp.data
        if data is None:
            break
        for item in (getattr(data, "items", None) or []):
            create_time_ms = getattr(item, "create_time", "0")
            try:
                ct = int(create_time_ms) / 1000.0 if create_time_ms else 0
            except Exception:
                ct = 0
            sender = getattr(item, "sender", None)
            sender_id = getattr(sender, "id", "") if sender else ""
            sender_type = getattr(sender, "sender_type", "") if sender else ""
            msg_type = getattr(item, "msg_type", "") or ""
            text = _extract_message_text(item, msg_type)
            messages.append({
                "message_id": getattr(item, "message_id", ""),
                "create_time": ct,  # 秒级时间戳
                "create_time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ct)) if ct else "",
                "sender_id": sender_id,
                "sender_type": sender_type,  # user / app
                "msg_type": msg_type,
                "text": text,
                "chat_id": chat_id,
            })
            if len(messages) >= limit:
                break
        page_token = getattr(data, "page_token", None)
        has_more = getattr(data, "has_more", False)
        pages += 1
        if not has_more or not page_token:
            break
    return messages


# ─────────────────────────────────────────────────────────
# 持久化（实时收到的群消息）
# ─────────────────────────────────────────────────────────
def _chat_file(chat_id: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"{chat_id}.jsonl"


def save_message(chat_id: str, message_id: str, *, sender_id: str = "", sender_name: str = "",
                 msg_type: str = "text", text: str = "", create_time: float = None, extra: dict = None):
    """持久化一条收到的群消息（JSONL 追加）。线程安全。

    Returns:
        dict: 保存的消息记录
    """
    if not chat_id:
        return None
    if create_time is None:
        create_time = time.time()
    record = {
        "message_id": message_id,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "msg_type": msg_type,
        "text": text,
        "create_time": create_time,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(create_time)),
    }
    if extra:
        record.update(extra)
    fpath = _chat_file(chat_id)
    with open(fpath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_messages(chat_id: str, keyword: str = None, hours: float = None):
    """从本地持久化文件读取消息（可选关键词过滤、最近N小时）。

    Args:
        chat_id: 群 chat_id
        keyword: 关键词过滤（不区分大小写），可选
        hours: 只取最近 N 小时的消息，可选
    Returns:
        list[dict]: 消息记录列表（时间正序）
    """
    fpath = _chat_file(chat_id)
    if not fpath.exists():
        return []
    cutoff = (time.time() - hours * 3600) if hours else None
    records = []
    kw = (keyword or "").strip().lower()
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if cutoff and rec.get("create_time", 0) < cutoff:
                continue
            if kw and kw not in (rec.get("text") or "").lower() and kw not in (rec.get("sender_name") or "").lower():
                continue
            records.append(rec)
    return records


def search_messages(keyword: str, chat_id: str = None, hours: float = None):
    """跨群（或指定群）按关键词搜索持久化消息。

    Args:
        keyword: 关键词
        chat_id: 指定群，None=搜索所有群文件
        hours: 只搜最近 N 小时
    Returns:
        list[dict]: 匹配的消息记录
    """
    kw = (keyword or "").strip().lower()
    if not kw:
        return []
    files = []
    if chat_id:
        p = _chat_file(chat_id)
        if p.exists():
            files = [p]
    else:
        files = sorted(DATA_DIR.glob("*.jsonl")) if DATA_DIR.exists() else []
    results = []
    for fpath in files:
        recs = load_messages(fpath.stem, keyword=kw, hours=hours)
        results.extend(recs)
    return results


# ─────────────────────────────────────────────────────────
# 总结辅助
# ─────────────────────────────────────────────────────────
def summarize_chat(chat_id: str = None, chat_name: str = None, limit: int = 50,
                   hours: float = None, prefer_local: bool = True):
    """拉取群消息并整理成可总结的文本（实际总结由 LLM 完成）。

    Args:
        chat_id: 群 chat_id（优先）。若只给 chat_name 会先 find_chat_by_name 解析
        chat_name: 群名关键词（当无 chat_id 时用）
        limit: 最多拉取多少条
        hours: 只看最近 N 小时（会换算成 start_time）
        prefer_local: True=优先用本地持久化消息（实时收到的），不足或为空时回退 API
    Returns:
        dict: {
            "chat_id", "chat_name", "source": "local"/"api"/"mixed",
            "count", "messages": [...], "text": "整理好的文本"
        }
    """
    # 1. 解析 chat_id
    resolved_name = chat_name
    if not chat_id and chat_name:
        found = find_chat_by_name(chat_name)
        if isinstance(found, dict) and "error" in found:
            return found
        matches = found.get("chats", []) if isinstance(found, dict) else found
        if not matches:
            return {"error": f"未找到群名包含 '{chat_name}' 的群"}
        if len(matches) > 1:
            names = [f"{m.get('name')}({m.get('chat_id')})" for m in matches[:10]]
            return {"error": f"匹配到多个群，请指定更精确的名称或 chat_id：" + " | ".join(names)}
        chat_id = matches[0].get("chat_id")
        resolved_name = matches[0].get("name")

    if not chat_id:
        return {"error": "需要 chat_id 或 chat_name"}

    # 2. 计算时间范围
    start_time = str(int((time.time() - hours * 3600) * 1000)) if hours else None

    # 3. 优先本地持久化消息
    local_msgs = []
    if prefer_local:
        local_msgs = load_messages(chat_id, hours=hours)

    api_msgs = []
    used_source = "local"
    if not local_msgs:
        # 本地为空，回退 API
        used_source = "api"
        api_msgs = list_messages(chat_id, limit=limit, start_time=start_time)
        if isinstance(api_msgs, dict) and "error" in api_msgs:
            return api_msgs
    elif len(local_msgs) < limit:
        used_source = "mixed"

    base = local_msgs if local_msgs else api_msgs
    # 过滤系统通知消息（加群/退群/设置变更等），这类无对话内容且无有效发送者
    base = [m for m in base if (m.get("msg_type") or "") != "system"]
    # 构建发言人友好名映射（真名优先，否则"成员N"），彻底避免显示 OU-A9A 这类代码
    name_map = build_sender_map(base)
    # 统一字段，时间正序
    normalized = []
    for m in base:
        stype = m.get("sender_type") or ""
        sid = m.get("sender_id") or ""
        if stype == "app":
            sender = "🤖机器人"
        elif m.get("sender_name"):
            sender = m["sender_name"]
        elif sid in name_map:
            sender = name_map[sid]
        else:
            sender = sid[:12] if sid else "未知"
        normalized.append({
            "ts": m.get("create_time_str") or m.get("ts") or
                  (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m.get("create_time", 0)))
                   if m.get("create_time") else ""),
            "sender": sender,
            "text": (m.get("text") or "")[:500],
        })
    normalized.sort(key=lambda x: x["ts"])

    # 4. 整理成文本
    lines = []
    for m in normalized:
        sender = m["sender"]
        ts = m["ts"]
        lines.append(f"[{ts}] {sender}: {m['text']}")
    text = "\n".join(lines)

    return {
        "chat_id": chat_id,
        "chat_name": resolved_name or chat_id,
        "source": used_source,
        "count": len(normalized),
        "messages": normalized,
        "text": text,
    }


# ─────────────────────────────────────────────────────────
# 自检 / 命令行入口
# ─────────────────────────────────────────────────────────
def selftest():
    """打印本模块可用性与配置状态（不发起真实 API 调用）。"""
    info = {
        "data_dir": str(DATA_DIR),
        "data_dir_exists": DATA_DIR.exists(),
        "app_id_configured": bool(_FS_APP_ID),
        "app_secret_configured": bool(_FS_APP_SECRET),
        "persisted_chats": sorted(p.stem for p in DATA_DIR.glob("*.jsonl")) if DATA_DIR.exists() else [],
    }
    return info


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="飞书群消息工具")
    parser.add_argument("--chats", action="store_true", help="列出所有群")
    parser.add_argument("--find", type=str, default="", help="按群名查找")
    parser.add_argument("--messages", type=str, default="", help="拉取群消息 (chat_id)")
    parser.add_argument("--limit", type=int, default=50, help="消息条数")
    parser.add_argument("--summary", type=str, default="", help="总结群 (chat_id 或群名)")
    parser.add_argument("--hours", type=float, default=0, help="最近N小时")
    parser.add_argument("--selftest", action="store_true", help="自检")
    args = parser.parse_args()

    if args.selftest:
        print(json.dumps(selftest(), ensure_ascii=False, indent=2))
    elif args.chats:
        print(json.dumps(list_chats(), ensure_ascii=False, indent=2))
    elif args.find:
        print(json.dumps(find_chat_by_name(args.find), ensure_ascii=False, indent=2))
    elif args.messages:
        hours = args.hours or None
        st = str(int((time.time() - hours * 3600) * 1000)) if hours else None
        print(json.dumps(list_messages(args.messages, limit=args.limit, start_time=st),
                         ensure_ascii=False, indent=2))
    elif args.summary:
        hours = args.hours or None
        # summary 参数可能是 chat_id 或群名
        arg = args.summary
        if arg.startswith("oc_"):
            r = summarize_chat(chat_id=arg, limit=args.limit, hours=hours)
        else:
            r = summarize_chat(chat_name=arg, limit=args.limit, hours=hours)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
