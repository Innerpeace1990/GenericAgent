# Git 推送策略 SOP（自动推送标准）

> - 版本：v1.0
> - 创建时间：2026-07-09
> - 最后验证时间：2026-07-09
> - 适用环境：Generic Agent 本地主仓库 `D:\generic-agent`，remote `origin` 指向用户私有 fork `Innerpeace1990/GenericAgent`，`upstream` 指向官方仓库 `lsdefine/GenericAgent`
> - 状态：有效
> - 替代方案：无
> - 制定依据：
>   - 内部：`code_upgrade_sop`（变更分类/门禁、可回滚）、`memory_management_sop`（行动验证）、`failure_handling_sop`（记录与复盘）
>   - 外部：GitHub/Git Flow 分支保护、Trunk-based Development、DevOps 持续集成门禁、ITIL 4 Change Enablement、GitOps 声明式版本控制

---

## 1. 核心原则

1. **只推自己的 fork**：自动推送仅允许目标为 `origin`（用户私有 fork），**绝不自动推送到 `upstream` 官方仓库**。
2. **先验证再推送**：任何自动推送必须通过 §3 的验证门禁，没有验证的 commit 不推。
3. **小步快跑**：鼓励把已验证的 commit 及时推送到 fork，避免本地堆积，减少单点丢失风险。
4. **可观测可回滚**：每次自动推送产生一条记录，保留回滚路径（fork 远端历史）。
5. **不推不可撤销的**：凡涉及核心框架、上游 merge、force push 等必须人工确认。

---

## 2. 变更分类（与 code_upgrade_sop 对齐）

每次推送前，对本地未推送的 commit 进行分类：

| 类型 | 判定标准 | 推送方式 |
|---|---|---|
| **标准变更（Standard）** | 仅涉及用户自有资产（memory、scripts、SOP、文档、配置、小修小补），且 §3 验证门禁全通过 | **自动推送，无需确认** |
| **正常变更（Normal）** | 涉及核心框架文件（agent_loop、llmcore、ga.py、agentmain、tools_schema、fsapp 等），或改动行数较大，或可能引入行为变化 | **必须人工确认后再推送** |
| **紧急变更（Emergency）** | 安全漏洞、严重 bug 修复，需立即推送 | 走紧急流程，但尽量不自动推 upstream |
| **禁止推送** | 未验证、有冲突、含敏感信息、force push、目标为 upstream | **不推送，并说明原因** |

> 判定核心：**是否只修改用户完全拥有且可独立验证的文件**。

---

## 3. 自动推送的验证门禁（必须全部通过）

### 3.1 目标与分支检查
- [ ] 目标 remote 是 `origin`（`git remote -v` 确认）
- [ ] 目标分支是本地 `main`（或用户当前已检出的分支）
- [ ] 不是 `upstream` 官方仓库
- [ ] 不是 force push（`--force` / `--force-with-lease`）

### 3.2 变更范围检查
- [ ] 未推送 commit 只涉及**用户自有资产**类别之一：
  - 文档/SOP：`memory/*.md`, `docs/`, `README.md`
  - 脚本/工具：`scripts/*`, `backups/*`, `tools/*`
  - 用户配置：`mykey*.py`, `config*.py`, `.env.example`
  - 小修小补：`fix`, `chore`, `docs` 类型的 commit
- [ ] **不涉及**核心框架文件（除非已单独验证通过）：
  - `agent_loop.py`, `llmcore.py`, `ga.py`, `agentmain`, `tools_schema.py`
  - `frontends/fsapp.py`, `frontends/tuiapp*.py` 等主入口
- [ ] 不包含从 `upstream` 的 merge 或 rebase 操作

### 3.3 技术验证
- [ ] Python 文件通过 `py_compile` 语法检查（如修改了 `.py`）
- [ ] PowerShell 文件通过语法检查（如修改了 `.ps1`）
- [ ] 关键文件能正常读取、无编码损坏
- [ ] 无敏感信息泄露（扫描是否含密钥、token、私钥等）
- [ ] 无未跟踪的临时文件被错误提交

### 3.4 工作区状态
- [ ] `git status` 工作区干净，无未提交改动
- [ ] 无未解决的 merge 冲突
- [ ] 无 stash 依赖

### 3.5 运行影响检查
- [ ] 不依赖未保存的运行中进程状态
- [ ] 推送不会打断正在执行的后台任务（如 fsapp 等）

---

## 4. 自动推送执行流程

```
Step 1: 检查 remote/branch（必须是 origin/main）
Step 2: 列出未推送 commit（git log origin/main..HEAD）
Step 3: 对 commit 做变更分类（标准/正常/紧急/禁止）
Step 4: 执行 §3 验证门禁
Step 5: 决策
  ├─ 全部通过 + 标准变更 → 自动 git push origin main
  ├─ 正常/紧急变更 → 暂停，向用户报告原因，请求确认
  └─ 任一门禁失败 → 不推送，报告失败项
Step 6: 推送后记录（incident_log / git log）
```

---

## 5. 明确不推送的情况

遇到以下任一情况，**不自动推送**，并说明原因：

1. 目标不是 `origin`（例如 `upstream` 官方仓库）。
2. 需要 force push（`--force` / `--force-with-lease`）。
3. 涉及核心框架文件且未单独验证。
4. 包含 upstream 的 merge 或 rebase。
5. 工作区不干净（有未提交改动）。
6. 存在未解决的 merge 冲突。
7. 技术验证失败（语法检查、敏感信息扫描等）。
8. 用户明确说“先不推”、“等等”、“确认后再推”。
9. 推送会影响正在运行且无法恢复的后台任务。
10. commit 消息含糊或包含 `WIP` / `DO NOT PUSH` 等标记。

---

## 6. 记录与复盘

- 每次自动推送后，记录到 `incident_log`（category=`git`，severity=`info`）：
  - 推送时间、目标、commit 数、commit 列表摘要
  - 验证门禁结果
- 每次拒绝推送时，记录原因（category=`git`，severity=`warn`），便于发现流程阻塞点。
- 每 30 天回顾一次推送日志，检查是否过度推送或漏推。

---

## 7. 版本历史

| 版本 | 时间 | 变更内容 | 变更原因 | 验证人 |
|------|------|----------|----------|--------|
| v1.0 | 2026-07-09 | 初始制定自动推送标准 | 用户要求明确推送/不推送条件，并授权自动执行 | Agent |
