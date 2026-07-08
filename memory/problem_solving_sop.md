## 版本信息

- 版本：v1.1
- 创建时间：2026-07-06
- 最后验证：2026-07-06
- 状态：有效
- 替代方案：无

## 版本历史

| 版本 | 时间 | 变更内容 | 变更原因 | 验证人 |
|------|------|----------|----------|--------|
| v1.0 | 2026-07-06 | 初始创建：问题解决、持续学习、信息源推荐 | 用户需求：建立统一的问题处理流程 | Agent |
| v1.1 | 2026-07-06 | 新增第 5 节：修改既有 SOP/工具时的 dry-run → 真实任务验证 → 保留/回滚流程 | 用户要求按 darwin-skill 经验落地，避免优化破坏既有能力 | Agent |

---

# 问题解决与持续学习 SOP

> Generic Agent 作为用户电脑的"手和脚"，必须持续提升能力。遇到任何技术问题，优先通过官方/权威来源寻找解决方案，并主动检索 GitHub 优秀案例。

## 1. 核心原则
1. **先探测，再搜索**：失败时先充分获取日志、状态、上下文，把问题定位到最小范围，避免用模糊关键词搜索。
2. **官方/权威优先**：优先查看官方文档、官方 issue、官方 changelog，其次看权威社区/博客，最后看论坛碎片信息。
3. **GitHub 案例优先**：对于代码实现类问题，优先在 GitHub 搜索真实仓库、可运行的示例、star 较高的方案。
4. **交叉验证**：不轻信摘要，必须进入详情页、代码片段、README、测试用例中核实。
5. **学以致用**：把验证成功的方案沉淀到 L3 SOP 或工具脚本中，避免重复踩坑。

## 2. 搜索优先级金字塔

```
第一层：官方文档 / 官方 Wiki / API 文档
   - 例如 Microsoft Learn、Python docs、Chrome DevTools docs、Selenium docs

第二层：官方 Issue Tracker / 论坛 / 邮件列表
   - 例如 GitHub Issues、Chromium bug tracker、Stack Overflow 官方标签

第三层：GitHub 优秀仓库 / Gist / 示例代码
   - 搜索关键词：`awesome-<topic>`、`python-<topic>`、`<topic>-examples`
   - 优先看最近更新、有测试、有 CI、star/fork 较高的项目

第四层：权威技术博客 / 社区文章
   - 例如 Real Python、Mozilla Hacks、Google Developers Blog

第五层：通用搜索引擎摘要（仅作线索，不直接采信）
```

## 3. 搜索技巧

### 3.1 Google 精确搜索
- `site:github.com python mouse wheel sendinput`：只在 GitHub 中搜索
- `site:docs.python.org ctypes SendInput`：只在官方文档中搜索
- `"win32api.mouse_event" scroll not working`：精确匹配报错/关键词
- `filetype:pdf "SendInput" mouse wheel`：搜索 PDF 文档

### 3.2 GitHub 内搜索
- 使用 GitHub 搜索语法：`topic:python stars:>100 mouse wheel`
- 查看 Issues 时加 `label:bug` 或 `label:enhancement`
- 关注 `README`、`examples/`、`tests/` 目录

### 3.3 官方文档定位
- 用 `site:docs.*.com` 或 `site:learn.*.com` 限定
- 对 Windows API，优先 MSDN / Microsoft Learn
- 对 Python 库，优先 ReadTheDocs 或该库官方文档

## 4. 验证与落地流程

```
问题出现
  │
  ▼
步骤1：探测（日志、状态、环境版本、错误堆栈）
  │
  ▼
步骤2：定位（最小复现、缩小范围）
  │
  ▼
步骤3：搜索（官方文档 → GitHub Issues → 优秀仓库 → 博客）
  │
  ▼
步骤4：验证（进入详情页，阅读代码/测试，必要时本地运行）
  │
  ▼
步骤5：应用（写入脚本、更新工具、修复问题）
  │
  ▼
步骤6：沉淀（更新 L3 SOP / 工具脚本 / 全局记忆）
```

## 5. 修改既有 SOP/工具时的防退化流程

解决问题过程中若需要修改 L1/L2/L3 SOP 或高复用工具脚本，必须遵循 **dry-run → 真实任务验证 → 保留/回滚** 机制，避免“优化”破坏既有能力。

| 阶段 | 动作 | 失败处理 |
|------|------|----------|
| **dry-run** | 在副本或隔离环境运行修改后的规则/脚本；对 SOP 修改做思维推演 | 回滚并重新设计 |
| **真实任务验证** | 用 1-2 个典型真实任务验证修改效果；对 lint/工具脚本运行原测试集 | 回滚并记录失败原因 |
| **保留/回滚** | 验证通过则正式提交；退化则回滚到上一有效版本 | 在版本历史中明确写“保留”或“回滚” |

> 详见 `memory_management_sop.md` 的“SOP 修改的 dry-run 与回滚流程”。

## 6. 不同场景下的信息源推荐

| 场景 | 首选来源 | 次选来源 |
|------|----------|----------|
| Windows API / 键鼠模拟 | Microsoft Learn (win32 API) | GitHub `pywin32` / `SendInput` 示例 |
| Python 库使用 | 官方 ReadTheDocs / GitHub README | Real Python / 库作者博客 |
| Chrome 扩展 / CDP | Chrome Developers Docs / Chromium blog | GitHub `chrome-extension-samples` |
| 自动化/爬虫 | Selenium / Playwright 官方文档 | GitHub `awesome-web-scraping` |
| 错误排查 | 官方 GitHub Issues（搜索相同错误信息） | Stack Overflow 高赞答案 |

## 6. 避免的低效行为

- 不读官方文档，直接凭印象尝试。
- 只看搜索结果摘要，不点进详情页。
- 重复搜索相同关键词，没有新信息。
- 找到方案后不复现、不验证，直接用于生产环境。
- 没有把成功经验沉淀到记忆/SOP。

## 7. 持续学习机制

- 每完成一次较复杂任务，回顾：哪些坑是新发现的？哪些技巧可复用？
- 将可复用的代码片段、参数、步骤写入 L3 SOP 或工具脚本。
- 按固定周期回顾 L3 SOP，删除过时内容，合并重复内容。
- 对高频使用的外部工具，维护一份"环境配置速查"。

---

## 8. 深度调研机制与模型选择决策（P3 新增）

> **依据**：第一性原理 + 多智能体/swarm 协同（学术：LLM-powered MAS, cited 47；工程：OpenAI Swarm handoff、Together AI MoA）。
> **原则**：选模型/模式要看任务本质，不凭直觉。专业知识可能过时，复杂问题应并行研究多视角。

### 8.1 模型/模式选择决策矩阵

| 任务特征 | 推荐模式 | 理由 |
|---|---|---|
| 简单直接（1-2步、明确） | **单模型**（当前会话模型） | 低成本、快 |
| 中等复杂（需权衡/创意/多角度） | **moa**（多模型聚合） | 多视角抗偏见、质量更优；**已加固容错**（P0: timeout/retry/fallback） |
| 超复杂/超大信息量/需并行检索 | **swarm 模式**（多 Agent 分工+聚合） | 并行检索+分工+综合，类似蜂群 |
| 纯编码/确定性 | 单模型（带工具） | 不需多视角 |

### 8.2 moa 使用要点（P0 加固后）
- moa 已具备 timeout(90s)/retry(1次)/fallback（主模型单答），**可放心用于复杂研究**。
- 某模型卡住不再阻塞整体：超时跳过，全失败退主模型。
- 调用后检查返回 meta：`{'mode':'best'|'aggregate'}` 正常，`{'reason':'fallback_single_model'}` 说明有模型失败但已降级。

### 8.3 何时必须深度调研（非凭固有知识）
- 用户明确要求"借鉴外部/权威/最佳实践"。
- 涉及领域新知识/模型新能力（固有知识可能过时）。
- 设计规则/SOP/架构（影响面大，需实证支撑）。

### 8.4 深度调研方法
- 学术：Semantic Scholar API / arXiv（注意查询语法，避免 OR/+ 导致空结果；被限流429时换源或间隔重试）。
- 工程：GitHub API（搜高 star 标杆项目，验证成熟度）。
- 官方：官方文档/Release notes/官方推荐流程。
- 交叉验证：多源对比，禁信单一摘要。

### 8.5 遇阻处置（不轻易放弃并行研究）
- 工具失败 → 查根因 → 评估是否值得修复（参见 failure_handling_sop §10.3）。
- 修复优先于绕过；实在不可行，记录"已尝试 + 不可行原因"后换源。
