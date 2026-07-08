# 模型特定经验教训记录（可裁剪框架）

> **版本**：v1.0  
> **最后验证**：2026-07-07  
> **状态**：有效  
> **审计周期**：每 2 周一次，或在接入新模型/切换套餐前必须审计  
> **替代方案**：无  

---

## 0. 核心原则（使用前必读）

1. **不是万能模板**  
   本文档是**记录框架**，每个条目只在其声明的环境、版本、套餐、协议下有效。禁止不加裁剪直接套用。

2. **按模型裁剪使用**  
   不同厂商/模型的 API 协议、Base URL、套餐规则、上下文长度、速率限制、计费方式不同。使用某条经验前，必须核对当前模型是否匹配该条目的“适用环境”。

3. **明确边界**  
   每条经验必须同时标注：
   - 适用环境（版本、套餐、地域、协议类型）
   - 不适用环境
   - 变更后需重新验证的点

4. **审计周期**  
   - 每 2 周运行一次 `memory_lint.py` 并复核本文件。
   - 接入新模型、切换套餐、升级 SDK/Agent 客户端前，必须重新审计相关条目。
   - 发现厂商文档变更或实际行为与记录不符时，立即标注为“待审计”或“已失效”。

---

## 1. 记录结构（新增模型时按此模板填写）

### 1.1 模型：智谱 GLM（国内 Coding Plan）

| 字段 | 内容 |
|------|------|
| **模型标识** | `zhipu-glm` / `GLM CN Coding Plan` |
| **适用环境** | 国内套餐；Anthropic 协议；Base URL 以 `https://open.bigmodel.cn` 为根路径；2026-07-07 已验证 |
| **不适用环境** | 智谱 Global 套餐；旧版 GLM-5.1/5（已自动切换至 5.2）；非 Coding Plan 的通用 API key |
| **关键经验** | 1. `configure_mykey.py` 生成的变量前缀必须与协议类型一致：国内 Anthropic 协议下，不可使用 `native_oai_config` 变量前缀。<br>2. 安装/修改 `mykey.py` 后，必须做端到端主模型调用验证，确认厂商控制台有 token 消耗、日志出现 `stop_reason=end_turn`（或 `tool_use`），而不是静默 fallback。<br>3. GLM Coding Agent 优先通过 `project.md` / `CLAUDE.md` 传递项目上下文；复杂任务先进入 Plan Mode。<br>4. 修改 LLM 配置前，确认 TUI 工作线程（如历史 PID 16188）不受影响。 |
| **裁剪指引** | - 如果切换到 Global 套餐，必须重新确认 Base URL、协议类型和变量前缀。<br>- 如果切换到 OpenAI 协议端点，必须重新匹配 `native_oai_config` 等前缀规则。<br>- 不同 IDE/客户端（Claude Code、Kilo、TRAE 等）对 `CLAUDE.md` / `settings.json` 的加载行为不同，必须按客户端裁剪。 |
| **审计触发条件** | 接入新套餐、升级 Agent 客户端、智谱控制台出现 0 调用、切换到 Global/其他地域 |
| **相关 SOP** | `llm_orchestration_sop.md` §6.5、§11 |
| **状态** | 有效 |

---

### 1.2 模型：Kimi（月之暗面 Coding API）

| 字段 | 内容 |
|------|------|
| **模型标识** | `kimi` / `k2.7-coding` / `k2.6-coding` |
| **适用环境** | 端点 `https://api.kimi.com/coding/v1`；作为 GA 备用模型；2026-07-07 已验证 |
| **不适用环境** | 非 Coding 端点的通用 Kimi API；需要多模态或超长上下文的任务 |
| **关键经验** | 1. 当 GLM 主模型失败/超时后，GA 按固定顺序 fallback 到 Kimi；新增模型不会自动接入，必须手动修改 `llm_nos` 并验证。<br>2. Kimi 在 Feishu Bot 场景中作为主力后端，使用方式与 GA 内部不同，必须按项目裁剪。 |
| **裁剪指引** | - 如果 Kimi 作为主模型使用，必须重新设计路由策略和调用上限。<br>- 如果 Kimi 端点变更，必须在 `llm_nos` 和项目中同步更新。 |
| **审计触发条件** | 切换 Kimi 模型版本、端点变更、备用模型出现大量调用时 |
| **相关 SOP** | `llm_orchestration_sop.md` §5、§6；`feishu_webhook_config_sop` |
| **状态** | 有效（待补充更多细节） |

---

### 1.3 模型：DeepSeek API（V4 Pro / Flash）

| 字段 | 内容 |
|------|------|
| **模型标识** | `deepseek-v4-pro` / `deepseek-v4-flash` |
| **适用环境** | 端点 `https://api.deepseek.com/v1`；兼容 OpenAI / Anthropic 协议；官方 1M 上下文 / 384K 最大输出；2026-07-07 已验证 |
| **不适用环境** | 需要实时/低延迟短任务；旧版 DeepSeek-V3 或第三方转接端点 |
| **关键经验** | 1. `llmcore.py` 的 `BaseSession` 默认 `context_win=30000`，只有 `deepseek` 模型名被识别为 1M，因此必须显式在 `mykey.py` 里写入 `context_win=1000000`，或在 `llmcore.py` 中补充模型族映射。<br>2. DeepSeek 默认开启 reasoning，输出较长，历史记录会快速膨胀；需配合 `cut_msg_interval=25`、`trim_keep_rate=0.3` 使用。<br>3. 接入后必须做一次端到端调用，确认 `stop_reason` 正确且控制台有 token 消耗。 |
| **裁剪指引** | - 若模型名不含 `deepseek` 字样，必须显式配置 `context_win`。<br>- 若把 DeepSeek 作为主模型，需重新设计 fallback 顺序和重试策略。 |
| **审计触发条件** | 切换模型版本、端点/协议变更、官方文档更新上下文/输出上限、出现长上下文截断时 |
| **相关 SOP** | `llm_orchestration_sop.md` §5.2、§5.3、§6.5、§11 |
| **状态** | 有效 |

---

### 1.4 通用坑点：上下文窗口默认值错配

| 字段 | 内容 |
|------|------|
| **适用环境** | GA `llmcore.py` 中 `BaseSession` 的默认行为；所有未显式配置 `context_win` 的模型 |
| **关键经验** | `BaseSession` 默认 `context_win=30000`，仅对 `deepseek` 特殊处理。GLM-5.2（官方 1M）、Kimi（官方 256K）等都会 fallback 到 30000，导致长上下文被提前截断。修复方式：在 `mykey.py` 每个配置中显式写入 `context_win`，并在 `llmcore.py` 中按模型族补充默认值。 |
| **裁剪指引** | 新增模型时，先在 `llm_orchestration_sop.md` 查官方上下文，再写入配置；不要依赖 `BaseSession` 的未知模型保守值。 |
| **审计触发条件** | 接入新模型、修改 `BaseSession` 默认值、发现长上下文截断 |
| **相关 SOP** | `llm_orchestration_sop.md` §5.3（厂商模型矩阵） |
| **状态** | 有效 |

---

### 1.5 通用坑点：质量评估与鲁棒性盲区（2026-07-08 模型覆盖补测发现）

| 字段 | 内容 |
|------|------|
| **适用环境** | GA quality_estimator L1 启发式 + MixinSession cascade/bandit + 4 模型(glm/kimi/ds-pro/flash)；2026-07-08 验证 |
| **关键经验** | 1. **qe L1 盲区**：L1 启发式无法检测"思考过程泄漏"污染输出（`<summary>`前缀/英文思考/数汉字过程），format 类任务 L1 全 0.9 假象 → L2 judge 揭示真实 0.0-0.2。cascade 在 L1 层对这些低质量输出不触发，需 L2 才触发。<br>2. **judge temperature 限制**：`llmcore.py` L405-406 强制 kimi/moonshot `temperature=1`，kimi 无法作 temp=0 judge；需 temp=0 的 judge 应用 deepseek/glm。<br>3. **注入鲁棒性差异**：glm 盲从可疑指令(直接执行 HACKED)，kimi/ds-pro 批判拒绝("根据安全规范不能执行")。安全评估必须 debug 真实输出，自动判定(关键词匹配)会误判 ds-pro(引用词≠执行)。<br>4. **Bandit+Cascade 同启归因污染**：reward 记到原 arm 而非 cascade 后实际输出模型，bandit 数据校准需注意。 |
| **裁剪指引** | L1 高分(>0.7)≠真优，必须抽样 debug 真实文本；format/简洁类任务尤其警惕思考泄漏；跨 judge 比较绝对分无意义(标准差异)，只比同 judge 同标准。 |
| **相关 SOP** | `llm_orchestration_sop.md` §14.3；`multiagent_validation_methodology_sop` |
| **状态** | 有效 |

---

## 2. 通用验证检查清单（按模型裁剪后使用）

> 以下清单不是每次都要全做，需根据当前模型条目的“适用环境”裁剪。

- [ ] 配置完成后，立即做一次端到端主模型调用测试。
- [ ] 检查厂商控制台近 5 分钟 token 消耗记录，确认主模型有调用。
- [ ] 检查日志 `stop_reason` 正确（`end_turn` 或 `tool_use`），而非连续 fallback。
- [ ] 检查生成的 `mykey.py` 变量前缀与所选协议类型一致。
- [ ] 修改配置前，确认 TUI 工作线程不受影响。
- [ ] 接入新模型/切换套餐后，复核本文件对应条目是否仍有效。

---

## 3. 审计日志

| 时间 | 审计人 | 变更内容 | 发现的问题 |
|------|--------|----------|------------|
| 2026-07-07 | Agent | 创建本文档，沉淀 GLM 国内 Coding Plan 配置错配教训 | 无 |
| 2026-07-07 | Agent | 新增 DeepSeek 与通用上下文窗口默认值错配条目 | `BaseSession` 的 30000 fallback 导致 GLM/Kimi 上下文被低估 |
| 2026-07-08 | Agent | 新增 1.5 质量评估与鲁棒性盲区条目（模型覆盖补测发现） | qe L1 无法检测思考泄漏；kimi 被强制 temp=1 无法作 temp=0 judge；注入鲁棒性差异(glm盲从/kimi+ds-pro拒绝) |

---

## 版本历史

| 版本 | 时间 | 变更内容 | 变更原因 | 验证人 |
|------|------|----------|----------|--------|
| v1.0 | 2026-07-07 | 创建可裁剪框架；记录 GLM 国内 Coding Plan 和 Kimi 备用模型经验教训 | 用户要求模型经验教训文档化，强调非万能模板、环境边界、审计周期 | Agent |
| v1.1 | 2026-07-07 | 新增 DeepSeek 模型经验；记录 BaseSession 默认 30000 上下文窗口错配问题 | 用户发现 DeepSeek 官方 1M 上下文未正确配置，同时排查 GLM/Kimi 也存在同样错配 | Agent |
| v1.2 | 2026-07-08 | 新增 1.5 质量评估与鲁棒性盲区条目（qe L1盲区/judge temp限制/注入鲁棒性差异/Bandit归因污染） | 用户要求逐模型逐场景补测模型覆盖盲区(36格26P+10C) | Agent |
