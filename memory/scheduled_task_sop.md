## 版本信息

- 版本：v1.0
- 创建时间：2026-07-06
- 最后验证：2026-07-06
- 状态：有效
- 替代方案：无

---

# 定时任务 SOP

目录：`../sche_tasks/` 放任务定义JSON，`../sche_tasks/done/` 放执行报告

## 任务JSON格式（*.json）
```json
{"schedule":"08:00", "repeat":"daily", "enabled":true, "prompt":"...", "max_delay_hours":6}
```
repeat可选：daily | weekday | weekly | monthly | once | every_Nh（每N小时）| every_Nd（每N天）
max_delay_hours（可选，默认6）：超过schedule多少小时后不再触发，防止开机太晚执行过时任务

## 触发流程
1. scheduler.py（reflect/）每60秒轮询 sche_tasks/*.json
2. 条件全满足才触发：enabled=true + 当前时间≥schedule + 冷却时间已过（基于done/最新报告时间戳）
3. 触发时拼prompt，含报告路径 `../sche_tasks/done/YYYY-MM-DD_任务名.md`
4. **收到任务后第一件事**：用 update_working_checkpoint 记录报告目标文件路径，防止长任务执行中遗忘
5. 执行完毕后将报告写入上述路径（scheduler靠此文件判断今天已执行）

## 日志与监控
- scheduler自动写日志到 `sche_tasks/scheduler.log`（触发/跳过/错误）
- `scheduler.health_check()` 返回所有任务状态列表（HEALTHY/OVERDUE/DISABLED/NEVER_RUN/ERROR）
- JSON解析错误、schedule格式错误、未知repeat类型均会记录日志

## 注意
- once类型：执行一次后冷却100年（实际效果为永久跳过）
- 任务文件只管"干什么"，报告路径由scheduler自动生成注入prompt
- sche_tasks目录在../，即code root下
## 失败与异常处理

1. **JSON 解析/schedule 格式错误**：立即记录到 `scheduler.log`；修正任务文件后重新加载，无需手工执行补偿。
2. **任务错过执行窗口**：`max_delay_hours` 过期后当日跳过，scheduler.log 标记为 SKIPPED；重要任务应设置更早的 `schedule` 或更长的 `max_delay_hours`。
3. **执行 agent 崩溃**：检查 `done/` 目录是否生成了报告文件；若未生成，scheduler 会判定为未执行，下次窗口再次触发。
4. **报告文件未落盘**：执行过程中必须将报告路径写入 checkpoint，任务结束时必须写到报告文件；缺失时手动补写并记录原因。
5. **时间边界**：跨 DST（夏令时）或系统时间调整时，scheduler 以系统本地时间为准；涉及精确时间触发时优先使用 UTC 或明确时区。
