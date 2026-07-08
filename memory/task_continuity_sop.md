## 版本信息

- 版本：v1.0
- 创建时间：2026-07-08
- 最后验证：2026-07-08
- 状态：有效
- 替代方案：无

---

# 任务接续 SOP (Task Continuity)

> **目的**：复杂任务执行中若遇意外中断（工具异常/进程崩溃/会话结束），能从断点恢复，不丢失进度。
> **依据**：Durable Execution 范式（conductor 32K★ "durable and highly resilient"、LangGraph Checkpointer）—— 状态落盘，崩溃从断点续。
> **基础设施**：`state_checkpoint.py` 的 `save_task_state` / `load_task_state` / `list_active_tasks` / `complete_task_state`。

---

## 1. 触发条件（何时启用任务接续）

满足任一即应启用：
- 任务 ≥3 步且有依赖/多文件协同（同 plan_sop 触发条件）。
- 长程任务（预计 >10 轮交互）。
- 用户明确要求"可中断可恢复"。

简单任务（1-2 步）无需启用，避免开销。

---

## 2. task_state schema

```json
{
  "task_id": "唯一标识（如 upgrade_tui_20260708）",
  "description": "用户原始任务描述",
  "plan": ["步骤1", "步骤2", ...],
  "current_step": 2,
  "completed_steps": ["步骤1（已完成）"],
  "key_findings": ["关键发现A", "关键发现B"],
  "context_snapshot": { "关键变量/路径/状态" },
  "status": "in_progress"
}
```

---

## 3. 集成点（何时 save / load）

### Save（写检查点）
1. **plan 建立后**：立即 `save_task_state` 记录任务描述+plan。
2. **每完成一步**：更新 current_step / completed_steps / key_findings 后 save。
3. **关键节点**：获得重要发现、创建重要文件后 save。

### Load（读检查点恢复）
1. **会话启动**：调用 `list_active_tasks()` 检查是否有未完成任务；有则提示用户可恢复。
2. **`/resume` 或用户说"继续"**：`load_task_state(task_id)` 读取进度，从 current_step 续。

### Complete（清理）
1. **任务完成**：`complete_task_state(task_id)` —— 标记 completed 并清除 checkpoint（有进有出，避免堆积）。

---

## 4. 恢复流程

中断后恢复的 Agent 行为：
1. `list_active_tasks()` 看有无未完成任务。
2. 若有：`load_task_state(task_id)` 读取 plan/current_step/completed_steps/key_findings。
3. 向用户汇报："检测到未完成任务 X，进度 Y/Z，已完成 ...，是否继续？"
4. 用户确认后，从 current_step 续，**不重复已完成步骤**。

---

## 5. 与现有机制的关系

| 机制 | 作用 | 区别 |
|---|---|---|
| `state_checkpoint` (任务级) | **任务进度**持久化 | 本 SOP 核心 |
| `agentmain.py` `/resume` | 对话**历史**恢复 | 恢复聊天记录，不含任务进度 |
| `L4_raw_sessions/` | 会话**归档** | 事后追溯，非实时恢复 |
| `update_working_checkpoint` | 工作记忆(notepad) | 每轮注入，防上下文丢失 |

> **互补**：`/resume` 恢复对话历史 + `load_task_state` 恢复任务进度，两者配合实现完整接续。

---

## 6. 典型坑

1. **checkpoint 堆积**：必须 complete 清理（有进有出），否则 temp/checkpoints 膨胀。
2. **快照过大**：context_snapshot 只存关键变量/路径，不存大对象/完整输出。
3. **task_id 冲突**：用"任务短名+日期"确保唯一。
4. **假完成**：complete 前确认任务真的完成（用户确认或验证通过），否则进度丢失。

---

## 7. 已知限制

- 当前为 Agent 主动调用（行为规则），未硬集成到 agent_loop。
- 仅持久化 JSON-able 状态，不持久化运行中内存对象。
- 多会话并发同 task_id 可能冲突（建议每会话独立 task_id）。
