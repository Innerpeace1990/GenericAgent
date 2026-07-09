## 版本信息

- 版本：v1.0
- 创建时间：2026-07-09
- 最后验证：2026-07-09
- 状态：有效
- 替代方案：无
- 关联：fsapp.py, fs_group.py, lessons_feishu_integration.md

---

# 飞书群消息监控与总结 SOP

## 1. 概述

本能力基于飞书官方服务端 API + lark_oapi SDK，实现对机器人所在群聊的消息监控、持久化、查询与总结。

### 能力清单

| 功能 | API/SDK | 说明 |
|------|---------|------|
| 群列表 | `c.im.v1.chat.list()` | 获取机器人所在全部群（chat_id/群名/成员数） |
| 群消息拉取 | `c.im.v1.message.list()` | 按 chat_id 拉取历史消息（支持分页） |
| 消息持久化 | `save_message()` | 收到群消息时自动写入 JSONL（`data/feishu_messages/<chat_id>.jsonl`） |
| 消息搜索 | `search_messages()` | 跨群按关键词搜索持久化消息 |
| 拉取总结 | `summarize_chat()` | 拉取群消息并整理为可总结文本 |
| 飞书命令 | `/chats /summary /search` | 飞书中直接触发 |

### 模块位置

- **tool**：`frontends/fs_group.py` — 可被 GA agent 通过 code_run 调用
- **集成**：`frontends/fsapp.py` — handle_message 持久化 + handle_command 命令路由
- **持久化目录**：`data/feishu_messages/` — `<chat_id>.jsonl` 文件

## 2. 前提条件

- `mykey.py` 已配置 `fs_app_id` + `fs_app_secret`
- 飞书后台"事件订阅"设置为**长连接模式**（非 Webhook）
- 机器人权限：
  - 普通：`im:message.group_at_msg`（被@才有消息）
  - 全量：`im:message.group_msg`（所有群消息，敏感权限）
- 机器人已被添加到目标群

## 3. API 文档依据（官方）

- 获取群列表：https://open.feishu.cn/document/server-docs/group/chat/list
- 获取群消息历史：https://open.feishu.cn/document/server-docs/im-v1/message/list
- 事件订阅概述：https://open.feishu.cn/document/server-docs/event-subscription-guide/overview
- 接收消息事件：`im.message.receive_v1`（SDK 方法名 `register_p2_im_message_receive_v1`）

## 4. SDK 消息结构（关键发现）

`message.list` 返回的 `item` 结构：
```python
item.sender.id          # 发送者 open_id（如 "ou_xxx"）
item.sender.sender_type  # "user" 或 "app"
item.msg_type            # "text", "image", "system" 等
item.body.content        # 内容 JSON 字符串
item.create_time         # 毫秒时间戳字符串
```

⚠️ **不要使用** `sender.sender_id`（无此属性）、`body.message_type`（无此属性）

## 5. 事件订阅方式

`register_p2_im_message_receive_v1` 的 **"p2" 指 P2 事件类型（v2.0 schema）**，非 peer-to-peer。该方法注册的是 `im.message.receive_v1` 事件，**同时覆盖单聊和群聊**。

## 6. 使用方式

### 6.1 飞书命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/chats` | 列出机器人所在群 | `/chats` |
| `/summary <id/名> [条数] [小时]` | 拉取总结 | `/summary oc_xxx 50 24` |
| `/search <关键词> [小时]` | 搜索持久化消息 | `/search ERP 24` |

### 6.2 GA Agent 调用

Agent 通过 `code_run` 直接调用：
```python
from frontends import fs_group
fs_group.list_chats()           # 列出群
fs_group.summarize_chat(chat_id="oc_xxx", limit=50)  # 拉取总结
fs_group.search_messages("关键词", hours=24)           # 搜索
```

FEISHU_EXTRA_PROMPT 第 3 条已更新为能力描述（不再禁止）。
Agent 获知群列表后即可自动总结群消息。

## 7. 故障排查

| 问题 | 检查 |
|------|------|
| 收不到群消息 | ① 飞书后台确认事件订阅方式=长连接 ② 检查权限 `im:message.group_msg` ③ 机器人已入群 |
| `list_chats` 返回空 | 检查 `im:chat` 权限 |
| `list_messages` 返回空 | 检查 `im:message` 或 `im:message.group_msg` 权限 |
| sender_id 为空 | 系统消息无发送者，正常 |
| fsapp 未连接 | 检查 `logs/fsapp.log` 是否出现 `connected to wss` |

## 8. 注意事项

- 群消息持久化仅在 fsapp **运行中**生效（长连接收到消息时写入）
- `search_messages` 只能搜索**持久化后的**消息（收不到之前的历史）
- 对于历史总结应使用 `summarize_chat → prefer_local=False` 强制拉 API
- 重启 fsapp 后需确认 `logs/fsapp.log` 出现 `connected to wss`
