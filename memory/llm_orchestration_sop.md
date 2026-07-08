| v2.3 | 2026-07-08 | 模型覆盖盲区补测：4模型×9场景=36格全测(26PASS+10CHECK)；7大发现：①qe L1盲区(思考泄漏检测不了,L1=0.9假象→L2真实0.0-0.2)②cascade需L2才触发③Bandit+Cascade reward归因污染④MoA聚合增益+0.50(内容清洗)⑤Judge稳定公正(方差≤0.002,偏见0)⑥注入鲁棒性差异(glm盲从/kimi+ds-pro拒绝)⑦自动判定需debug真实输出(误判ds-pro) | 用户要求逐模型逐场景补测 | Agent |
| v2.2 | 2026-07-07 | MoA-ORM完整集成闭环（gap1 propose自动orm.record用client.model + gap2 动态clients_provider感知handoff）；集成测试基线建立（6场景全PASS）；MoA从"轻量"升级"完整集成" | 用户要求补成真正闭环,修完重跑验证 | Agent || v1.8 | 2026-07-07 | §14.3 更新：质量估计器+④Cascade 落地（quality_estimator.py 分层评估 L0/L1/L2，9/9；MixinSession 接入 L1 启发式端到端 6/6+routing_log记录）；④⑤共同前提(质量估计器)已补齐 | 用户要求质量估计器真正落地，非标记待后续 | Agent |# LLM 编排与模型选择 SOP
| v1.9 | 2026-07-07 | §14.3 更新：P3 Bandit 自适应路由落地（`bandit_router.py` UCB1，6/6 模块测试 + 端到端收敛 4/4，30 轮 m0:m1=26:4）；MixinSession 数据驱动选模型 | 用户要求 P3 落地，非愿景 | Agent |
| v2.0 | 2026-07-07 | §14.3 更新：⑨ MoA 多智能体聚合落地（`moa.py` 三阶段流水线 5/5 + `do_moa` 真实 dispatch 5/5）；**§14.2 路线图 P0-P3 主体全部落地（9 项改进）**，4 新模块（routing_log/quality_estimator/bandit_router/moa） | 用户要求⑨MoA 落地，路线图主体闭环 | Agent |> 为 Generic Agent 提供大模型调度、路由、故障转移与新模型接入的决策框架，平衡性能、成本、延迟与稳定性。
>
> - 版本：v2.0
> - 最后验证时间：2026-07-07
> - 适用环境：Windows 10/11，Generic Agent 本地运行，当前 LLM 后端为智谱 GLM + Kimi 双模型混合
> - 已知限制：当前未实现动态路由，仍依赖固定顺序故障转移；价格/能力数据随厂商更新，须每 2 周或在接入新模型前复核一次
> - 替代方案：短期可引入 OpenRouter/LiteLLM/Portkey 等统一网关；长期可基于历史偏好数据训练 Router（RouteLLM 思路）或实现动态 cost/quality 路由。
> - v1.6 新增：§13 多智能体协作框架范式、§14 GA 多模型改进路线图（来源 `plan_multiagent_orchestration` 调研报告，8 框架 + 7 论文 + GA 现状探测，双轮对抗验证 PASS）

## 1. 当前编排现状（行动验证）

- **主模型**：`zhipu-glm`（智谱 GLM 系列，具体见代码配置）
- **备模型**：`kimi`（Moonshot Kimi，端点 `https://api.kimi.com/coding/v1`）
- **选择逻辑**：固定顺序故障转移（failover）。优先调用 GLM，失败/超时后切 Kimi。
- **接入位置**：`llm_nos` 列表，新增模型必须手动修改代码并重启/重载，**不会自动接入**。
- **TUI 影响**：修改配置前需确认 TUI 进程 PID 16188 或其他工作线程不受影响。

## 2. 设计原则（来源：Anthropic + Google + 顶级论文）

1. **从简单开始**：先用单模型 + 好提示词；只有在可度量的性能提升时才增加复杂度。
2. **只在必要时用 Agent/Workflow**：Workflow 适合预定义多步任务；Agent 适合动态决策、长程规划和工具调用。
3. **明确成功标准**：延迟、成本、准确率、可用率、用户满意度，至少量化其中 2-3 项。
4. **模型是核心，工具是边界**：模型负责推理与决策；工具（MCP / Function / Extension）扩展其能力边界。
5. **可观测性优先**：记录每个请求的路由模型、延迟、成本、输出质量、失败原因。

## 3. 模型选择维度

| 维度 | 高优先级任务 | 低优先级/可降级任务 |
|------|--------------|--------------------|
| **任务复杂度** | 多步推理、代码、创意写作 | 简单问答、分类、格式化 |
| **代码能力** | 代码生成、Review、Debug、架构设计 | 非代码文本生成 |
| **上下文长度** | 长文档、多轮对话、RAG 大上下文 | 短提示、单轮 |
| **延迟要求** | 交互式 TUI、实时响应 | 后台任务、批处理 |
| **成本预算** | 准确率敏感，可接受高成本 | 成本敏感，可接受略低质量 |
| **稳定性** | 关键路径、失败影响大 | 可重试、非关键路径 |
| **多模态** | 图像理解、文档解析 | 纯文本 |

## 4. 路由策略矩阵

| 策略 | 思想 | 适用场景 | 成本/复杂度 | 参考来源 |
|------|------|----------|------------|----------|
| **固定顺序 Failover** | 主模型优先，失败后切备模型 | 当前 GA 现状；小团队、模型差异大 | 低 | 当前实现 |
| **简单任务降级** | 简单任务用小模型/快模型，困难任务用大模型 | 客服、分类、摘要、通用对话 | 中 | FrugalGPT / Anthropic Routing |
| **LLM Cascade** | 按置信度/评分逐级上更大模型，小模型能答则停 | 批处理、问答、分类 | 中 | FrugalGPT (Chen et al., 2023) |
| **偏好数据 Router** | 用历史数据训练小模型做路由器 | 高频、可收集偏好/反馈的场景 | 高 | RouteLLM (Ong et al., 2024) |
| **OpenRouter Pareto Router** | 基于用户偏好数据学习强/弱模型路由边界 | 已有历史反馈、需要动态 cost/quality trade-off | 高 | OpenRouter, 2024 |
| **LiteLLM Adaptive Router** | 按延迟/TTFT/吞吐量/成本实时选择最优模型 | 多模型池、高并发、对延迟/成本敏感 | 中 | LiteLLM, 2024 |
| **Portkey 统一网关** | Conditional Routing + Load Balancing + Fallbacks + Retries | 多 key/多厂商/多 region，需要高可用与合规治理 | 中 | Portkey, 2024 |
| **MoA（混合智能体）** | 多 Proposer 生成 + Aggregator 综合 | 复杂推理、创意、代码 | 高 | Together AI, 2024 |
| **Workflow 编排** | Prompt Chaining / Routing / Parallelization / Orchestrator-Workers / Evaluator-Optimizer | 预定义多步骤、可拆分、可评估的任务 | 中 | Anthropic, 2024 |
| **Agent 动态编排** | 模型自主决定工具调用、状态转换、重试 | 开放域、目标模糊、需要外部工具 | 高 | Google Agent Whitepaper, 2024 |

## 5. 推荐模型分工（针对当前及拟新增模型）

### 5.1 当前模型

- **智谱 GLM**：通用主模型。综合能力均衡，适合大多数任务。优先使用 **GLM-5.2**（1M 上下文 / 128K 输出，Coding SOTA）处理复杂任务；中等任务用 **GLM-5.1**（200K 上下文 / 128K 输出）；轻量任务可用 **GLM-5**、**GLM-4-Flash** / **GLM-4-Air**。
- **Kimi**：备用模型。特长为长上下文和代码。复杂代码任务用 **kimi-k2.7-code**（256K 上下文）；需要高速输出用 **kimi-k2.7-code-highspeed**（约 180 tokens/s，短上下文可达 260 tokens/s）；多模态/通用任务用 **kimi-k2.6**。当 GLM 失败、超长上下文或代码任务需要第二意见时启用。

### 5.2 拟新增模型

- **DeepSeek API**（https://api.deepseek.com，兼容 OpenAI / Anthropic 协议）：
  - 定位：推理密集型任务首选。主模型为 **deepseek-v4-pro**（MoE，1M 上下文，最大 384K 输出），轻量高并发用 **deepseek-v4-flash**（1M 上下文，最大 384K 输出，并发 2500）。
  - 适用：数学、代码、复杂逻辑、多步推理、长文档理解与生成。
  - 价格（2026-07-07 官方，每 1M tokens）：
    - V4-Pro：输入缓存未命中 $0.435，输出 $0.87；缓存命中 $0.003625；并发 500。
    - V4-Flash：输入缓存未命中 $0.14，输出 $0.28；缓存命中 $0.0028；并发 2500。
  - 注意：默认开启 thinking / reasoning；输出较长，延迟通常高于通用模型；适合非实时后台任务或高质量推理任务。接入时需配置专属 API key，并在 `llm_nos` 中注册 `deepseek-v4-pro` / `deepseek-v4-flash` 及对应端点。

- **阿里云百炼 Coding Plan**（https://coding.dashscope.aliyuncs.com/v1）：
  - 定位：代码/编程工具专用订阅套餐，与按量计费 API key 不互通。仅允许在编程工具（Claude Code、Cursor、Qwen Code、Cline、Codex 等）中使用，**禁止用于自动化脚本或后端批量调用**。
  - 适用：代码生成、代码补全、代码审查、技术文档生成、编程工具场景。
  - 套餐：
    - Pro 套餐：固定月费，支持 qwen3.7-plus、qwen3.6-plus、glm-5.2、kimi-k2.7-code、MiniMax-M2.7、deepseek-v4-pro 等模型；额度按模型调用次数扣除，简单任务 5–10 次、复杂任务 10–30+ 次。具体限制以控制台显示为准。
  - 注意：Lite 套餐已于 2026-04-13 停止新购/续费/升级。需使用专属 API key（`sk-sp-` 开头）和专属 Base URL（`https://coding.dashscope.aliyuncs.com/v1` 或 `https://coding.dashscope.aliyuncs.com/apps/anthropic`），不可与通用百炼 key 混用。若误用通用 key，会按量扣费。接入 GA 时要考虑其使用范围限制，避免违规导致 key 被封。

### 5.3 主流厂商模型矩阵（快速参考）

| 厂商 | 旗舰/主推模型 | 上下文/输出 | 特长 | 适用场景 |
|------|--------------|------------|------|----------|
| **智谱** | GLM-5.2 | 1M / 128K | Coding SOTA、长程稳定 | 复杂工程任务、长文档 |
| **智谱** | GLM-5.1 | 200K / 128K | 推理、Agent 规划 | 中等复杂任务 |
| **智谱** | GLM-5 | 128K / 64K | 通用、均衡 | 通用对话、轻量任务 |
| **智谱** | GLM-5V-Turbo | 多模态 | 视觉 + Coding | 多模态代码、UI 理解 |
| **Kimi** | kimi-k2.7-code | 256K | 旗舰 Coding | 复杂代码、长上下文 |
| **Kimi** | kimi-k2.7-code-highspeed | 短上下文 | 高速输出（约 180T/s） | 快速代码补全 |
| **Kimi** | kimi-k2.6 | 多模态 | 多模态理解 | 图像、视频理解 |
| **DeepSeek** | deepseek-v4-pro | 1M / 384K | 深度推理 | 数学、复杂推理、长文档 |
| **DeepSeek** | deepseek-v4-flash | 1M / 384K | 高并发、低成本 | 批量任务、实时性要求 |
| **阿里云百炼** | qwen3.7-max / plus | 多模态 | 通义旗舰 | 通用多模态任务 |
| **阿里云百炼** | deepseek-v4-pro/flash | 1M | 三方集成 | 在 IDE 等工具中使用 |
| **阿里云百炼** | kimi-k2.7-code / glm-5.2 | 按原厂商 | 三方编程模型 | Coding Plan 专属场景 |

> 价格与速率限制会频繁更新，接入前必须复核官方文档。智谱：https://docs.bigmodel.cn/pricing；Kimi：https://platform.moonshot.cn/docs/models；DeepSeek：https://api-docs.deepseek.com/quick_start/pricing；阿里云百炼：https://help.aliyun.com/zh/model-studio/model-selection。

## 6. 故障转移与重试规则

1. **重试策略**：失败时先对同一模型指数退避重试（最多 2 次），再切换备用模型。
2. **切换触发条件**：HTTP 5xx、超时、速率限制（429）、内容过滤、空响应、JSON 解析失败。
3. **主备恢复**：避免立即回切主模型，至少在当前会话/任务内保持备模型，防止抖动。
4. **降级输出**：当所有模型均失败时，返回友好错误信息并记录日志，不崩溃。
5. **状态监控**：记录失败率、延迟 P95/P99、成本，超过阈值时触发告警或切换默认主模型。

## 6.5 安装与配置验证检查点（新增）

> **目的**：避免“配置看似成功，实际主模型从未被调用”的隐蔽故障。故障转移机制会静默把请求切到备用模型，导致主模型在厂商控制台中显示 **0 调用**。

每次完成安装或修改 `mykey.py` 后，必须执行以下端到端验证：

1. **检查协议类型匹配**：确认 `mykey.py` 中主模型变量类型与 `apibase` 协议一致。
   - 例：智谱 CN Coding Plan（`https://open.bigmodel.cn/api/anthropic`）必须是 `native_claude_config_N`，对应 `NativeClaudeSession`。
   - 反例：端点是 Anthropic 协议，但变量名为 `native_oai_config_N`，会触发 OAI 请求，导致 GLM 调用失败并转移到 kimi。
2. **检查配置名解析**：运行 `from llmcore import resolve_client; resolve_client('zhipu-glm')`，确认不会抛 `Config not in mykey` 或 `Unsupported session type`。
3. **单模型端到端调用**：直接使用 `NativeClaudeSession(cfg).ask(...)` 或 `MixinSession` 向主模型发送一句测试Prompt，确认返回的 `model`/`stop_reason` 正确。
4. **核对厂商控制台**：在智谱/月之暗面等控制台查看近 5 分钟调用记录，确认主模型有 token 消耗，而不是仅备模型有消耗。
5. **检查日志 stop_reason**：主模型返回应出现 `stop_reason=end_turn`（或 `tool_use`），而非连续出现 `fallback to kimi` 或 `fallback to gpt`。
6. **配置向导回归**：修改 `configure_mykey.py` 后，必须用临时 Key 走一次完整配置流程，确认生成的 `mykey.py` 变量前缀与所选协议一致。

## 7. 新模型接入流程

1. **能力评估**：收集官方能力矩阵、定价、上下文长度、速率限制、延迟基准。
2. **分类测试**：用固定任务集（代码、长文本、推理、创意、多轮）测试输出质量与稳定性。
3. **配置接入**：在 `llm_nos` 中注册新模型，设置 API key、端点、模型名、优先级、温度/参数。
4. **路由策略**：决定是作为主模型、备用模型、专项模型（如代码-only）还是动态路由候选。
5. **灰度上线**：先让非关键任务走新模型，观察 1-3 天再扩大流量。
6. **记录归档**：将模型能力、定价、适用场景写入本 SOP 和 `global_mem.txt`。
7. **TUI 保护**：修改前确认 TUI 工作线程（PID 16188 等）不受影响，避免重启/重载打断当前任务。

## 8. 监控与评估指标

| 指标 | 说明 | 目标 |
|------|------|------|
| 请求成功率 | 2xx / 总请求 | > 99% |
| 平均延迟 | 首 token / 完整响应 | 按任务类型设定 |
| 成本 per 1K tokens | 输入+输出费用 | 按预算监控 |
| 用户满意度 | 任务完成率、人工评分 | 持续提升 |
| 路由准确率 | 小模型能答却被路由到大模型的比例 | < 5% |
| 幻觉率 | 事实错误/编造比例 | 关键任务 < 1%，非关键任务 < 5% |

## 9. 安全与合规

- **密钥管理**：API key 不硬编码，使用环境变量或密钥管理工具；禁止读取/移动密钥文件。
- **数据隐私**：含敏感信息的请求优先走可信厂商，避免传输到不可信第三方。
- **内容审查**：对输出进行合规审查，尤其是对外发布的内容。
- **供应商锁定**：避免单点依赖，至少保留 2 个可用后端。

## 10. 关键参考来源与论文要点

- Anthropic: *Building Effective AI Agents* (2024) — 中文翻译 by ArthurChiao
  - 核心观点：从简单开始；先优化提示和单模型，再考虑 Workflow/Agent；明确成功标准；Agent 适合动态决策与工具调用，Workflow 适合预定义多步任务。
- Google: *AI Agent Whitepaper* (2024) — 中文翻译 by ArthurChiao
  - 核心观点：Agent 扩展型与工作流预定义型两种架构；工具调用、多 Agent 协作、状态管理是关键；模型是推理核心，工具扩展能力边界。
- Chen et al.: *FrugalGPT: Efficient LLM Usage via Cascading and Substitution* (2023)
  - 核心观点：通过 LLM 级联（cascade）与替代（substitution）降低成本：先用小模型/便宜模型，若置信度不足再调用更大模型；若模型 A 与 B 在目标区域上能力互补，可互相替代；在保持甚至提升准确率的同时显著降低费用。
- Ong et al.: *RouteLLM: Efficient LLM Routing with Preference Data* (2024)
  - 核心观点：用人类偏好数据训练轻量 router，自动在强模型与弱模型之间做路由；根据用户指定的成本-性能预算动态选择模型；在 11 个基准上平均降低 50% 成本，同时保持强模型 90% 以上的性能。
- Together AI: *Mixture-of-Agents* (2024)
  - 核心观点：多 Proposer 独立生成 + Aggregator 综合，形成迭代 MoA 层；通过多个 LLM 的集体优势提升输出质量；在 AlpacaEval 2.0、MT-Bench、FLASK 上超过 GPT-4 Omni；适合复杂推理、创意、代码等高质量需求。
- OpenRouter: Pareto Router — 基于偏好数据学习强/弱模型路由边界，动态选择 cost/quality trade-off。https://openrouter.ai/docs/pareto-router
- LiteLLM: Adaptive Router — 按延迟/TTFT/吞吐量/成本在多模型池中实时选择最优模型。https://docs.litellm.ai/docs/routing
- Portkey: Conditional Routing, Load Balancing, Fallbacks, Retries — 统一网关治理多厂商/多 key 调用。https://portkey.ai/docs/product/prompts-gateway
- 智谱: 模型概览 https://docs.bigmodel.cn/cn/guide/start/model-overview
- Kimi: 模型列表 https://platform.moonshot.cn/docs/models
- DeepSeek: 定价与模型 https://api-docs.deepseek.com/quick_start/pricing
- 阿里云百炼: 模型选择 https://help.aliyun.com/zh/model-studio/model-selection
- 阿里云百炼 Coding Plan: https://help.aliyun.com/zh/model-studio/coding-plan
- 说明：OpenAI 平台 docs 在 2026-07-07 被 Cloudflare 拦截，未直接访问；其策略思想已通过 Anthropic/Google 论文及行业实践间接覆盖。

## 11. GLM Coding Agent 使用最佳实践（来源：docs.bigmodel.cn）

> 以下最佳实践来自智谱官方 Coding Plan 文档，与 §2 设计原则互补，重点用于提升 Agent 在真实项目中的执行质量。

1. **从足够小的任务开始**  
   先完成单一、可验证的小任务，再逐步扩展范围，避免一次性抛出模糊大目标。

2. **用上下文文件传递项目信息**  
   - 将项目架构、目录约定、构建/测试命令、命名规范、常见流程写入项目级 `project.md`（或 `CLAUDE.md`）。  
   - 规则要具体、可执行，避免模糊口号。  
   - 组织级规则写入 `system.md`（最高优先级，不可被个人设置排除）；个人偏好写入 `user.md`。  
   - `CLAUDE.md` 采用叠加(additive)模式，所有层级都会加载；`.claude/settings.json` 采用覆盖(override)模式，越具体层级优先级越高。

3. **复杂任务先用 Plan Mode 规划**  
   - 对重构、跨模块修改、架构设计等高风险任务，先让 Agent 分析并输出计划。  
   - 在 Claude Code 中可用 `claude --permission-mode plan` 或 `.claude/settings.json` 设置默认模式。  
   - 计划可在文本编辑器中手动修改，确认后再执行。

4. **把任务交给专门的 subagents**  
   - 为测试、文档、代码审查、安全审查等职责建立专门子代理。  
   - 主 Agent 负责协调，避免单个上下文过度膨胀。

5. **用 Skills 沉淀可复用流程**  
   - 将重复性流程（如代码审查、发布 checklist）封装为 Skill。  
   - Skill 是"知识/流程"，MCP 是"外部系统连接"，二者通常配合使用。

6. **通过 MCP 连接外部系统**  
   - 使用 MCP 让 Agent 直接查询 issue、CI 状态、数据库、API 文档等。  
   - 扩展 Agent 的上下文边界，使其从"仓库执行者"转变为"真实研发环境的协作节点"。

7. **将重复流程自动化**  
   - 使用 cron、GitHub Actions、自定义脚本等自动触发 Agent 执行周期性任务（如代码审查、依赖检查、文档同步）。

8. **精心打磨提示词**  
   - 明确目标、约束、输出格式、验收标准，提供具体示例和反例。  
   - 引用文件/目录时使用 `@path/to/file`；引用 MCP 资源时使用 `@github:owner/repo/issues`。

9. **常用工作流模板**  
   - **理解新代码库**：项目概览 → 关键文件 → 架构关系 → 数据流与依赖。  
   - **修复 bug**：复现步骤 → 定位根因 → 最小修复 → 测试验证 → 回归检查。  
   - **重构代码**：Plan Mode 制定迁移计划 → 小步修改 → 持续测试 → 保留回滚点。  
   - **编写测试**：识别未测试代码 → 生成框架 → 添加边界用例 → 运行验证。  
   - **创建 PR**：总结变更 → 生成 PR 描述 → 审查细化。  
   - **处理文档**：识别未记录代码 → 生成文档 → 补充上下文与示例 → 按项目标准审查。

10. **参考文档索引**  
    - 智谱 Coding Plan 文档索引：https://docs.bigmodel.cn/llms.txt  
    - 套餐与概览：https://docs.bigmodel.cn/cn/coding-plan/overview  
    - 最佳实践：https://docs.bigmodel.cn/cn/coding-plan/learning-resources/best-practice  
    - 记忆机制：https://docs.bigmodel.cn/cn/coding-plan/learning-resources/memory-mechanism  
    - 扩展组件：https://docs.bigmodel.cn/cn/coding-plan/learning-resources/agentic-extension  
    - 常用工作流：https://docs.bigmodel.cn/cn/coding-plan/learning-resources/common-workflow

## 12. 模型特定经验教训管理（可裁剪、非万能模板）

> 不同模型有各自的经验和最佳实践，必须按环境、版本、套餐、协议类型裁剪使用，禁止不加验证直接套用。

1. **文档化位置**  
   - 模型特定经验教训统一记录到 `model_lessons_learned.md`（L3 级 SOP）。  
   - 每个模型独立条目，必须包含：适用环境、不适用环境、关键经验、裁剪指引、审计触发条件、相关 SOP、状态。

2. **核心原则**  
   - **不是万能模板**：每条经验只在声明的边界内有效。  
   - **按模型裁剪**：接入新模型或切换套餐时，必须重新评估相关条目是否适用。  
   - **标注边界**：明确记录适用环境与不适用环境，避免模糊泛化。  
   - **审计周期**：每 2 周运行 `memory_lint.py` 并复核本文件；接入新模型/切换套餐前必须审计。

3. **审计流程**  
   - 检查各模型条目是否仍与厂商最新文档、控制台行为、实际调用记录一致。  
   - 发现不一致时，立即标注为“待审计”或“已失效”，并更新对应 SOP 和 global memory。  
   - 审计记录写入 `model_lessons_learned.md` 的审计日志表。

4. **当前已记录模型**  
   - 智谱 GLM（国内 Coding Plan）：配置错配导致静默 fallback 的教训与验证检查点。  
   - Kimi（备用模型）：基本使用方式与边界，待补充更多细节。  
   - 接入 DeepSeek、阿里云百炼等模型时，按同一框架新增条目。

## 13. 多智能体协作框架范式（来源：2026-07 多智能体编排调研，双轮验证 PASS）

> 当单模型路由不足以满足需求，需引入多 Agent 协作时，参考以下 5 大范式（按与 GA 架构契合度排序）。GA 现有 function-calling + `llm_nos` 异构混用，天然适合前两种范式，**无需架构重构**即可激活"组合优势"。

| 范式 | 代表框架 | 核心思想 | GA 契合度 | 适用场景 |
|------|---------|---------|-----------|---------|
| **Handoff 路由** | OpenAI Swarm / Agents SDK | 当前模型主动决定交给哪个模型 | ★★★★★ 改动最小 | 动态分工 |
| **Supervisor-as-tools** | LangChain multi-agent | 模型/能力封装为工具，中心 LLM 调度 | ★★★★★ 最贴近 GA function calling | 统一调度 |
| **状态机编排** | LangGraph | 显式状态图 + 条件边 + checkpoint | ★★★☆☆ | 可恢复长任务 |
| **GroupChat** | AutoGen | 多角色自由对话协商 | ★★☆☆☆ | 创意/协商 |
| **Task 账本** | CrewAI / Magentic-One | Manager 拆解任务 + Worker 执行 + 进度追踪 | ★★★☆☆ | 复杂可拆分任务 |

> 典型坑：GroupChat/状态机范式在模型能力弱时易陷入死循环或状态发散，需设最大轮数与显式终止条件。

## 14. GA 多模型调度改进路线图（来源：同上，GA 现状静态探测 + 8 框架 + 7 论文）

> **现状诊断**：GA 调度 = 固定顺序 Failover，只认 `!!!Error:` 才切换；**答错、超 token、格式损坏都不触发切换** → 多模型当"备用轮胎"，组合优势利用度低（无分工 / 无交叉验证 / 无成本感知）。

### 14.1 能力缺口

| # | 能力 | GA 现状 | 业界/论文已实现 |
|---|------|--------|----------------|
| 1 | 任务→模型路由 | ❌ 无（唯一差异：中英文工具 schema） | Capability Card、可解释路由 |
| 2 | 质量判定反馈环 | ⚠️ 有盲区（只认 Error，答错当成功） | Critic/Verifier 角色 |
| 3 | 并行投票/MoA | ❌ 无（纯串行） | Mixture-of-Agents |
| 4 | 级联分工（弱打底+强攻坚） | ❌ 无 | LLM Cascade |
| 5 | 成本/延迟/配额感知 | ❌ 无（固定顺序，不比较性价比） | Bandit 在线路由 |

### 14.2 改进点与优先级

| 优先级 | 方案 | 复杂度 | 收益 / 为什么先做 |
|--------|------|--------|------------------|
| **P0 立即** | ① 扩展质量判定（超 token / 格式损坏也触发切换） | 低 | 修可靠性 bug，向后兼容，无需架构重构 |
| **P1 本期** | ② Handoff 路由 + ③ Capability Card | 低-中 | 低成本激活"组合优势"，最贴近 GA 架构 |
| **P2 下阶段** | ④ LLM Cascade + ⑤ Planner-Executor | 中 | 成本/质量双优，发挥强弱分工 |
| **P3 愿景** | ⑥ 状态图+持久化 ⑦ Orch-RM ⑧ Bandit ⑨ MoA | 高 | 长期竞争力，需数据/训练投入 |

> - **关键依赖**：质量估计器是 ④⑤⑧ 的共同前提——正是 GA 当前最缺、也最该先补的能力（与 ① 呼应）。
> - **P0 实施红线**：任何 GA 源码改动必须先做风险评估 + 回滚方案（遵循 META-SOP dry-run→验证→保留/回滚 流程），**禁止改崩溃自身运行**；因禁读 `mykey.py`，真实模型组合顺序改前需执行 `/llms` 命令或获授权确认。
> - **可观测性**：同步引入路由日志（选了哪个模型、为什么、结果如何），否则改进效果不可度量。

### 14.3 实施进展（2026-07-07 持续推进）

| 项 | 状态 | 验证 | 落地说明 |
|---|---|---|---|
| P0 ① 质量判定 | ✅ 已实施 | 7/7 真实 | `MixinSession._detect_quality_issue`：max_tokens 截断 / 工具参数格式损坏 → 触发下次切换 |
| P1 ② Handoff 路由 | ✅ 已实施 | 7/7 真实 dispatch | `do_handoff` 工具（编号/名称/model 名匹配）+ `agent_loop` 行59 动态 client + 复用 `next_llm` history 迁移 |
| P1 ③ 能力卡片 | ✅ 已实施 | 4/4 | `_build_capability_card` 注入 sys_prompt（填写优先，无则按 model 名推断；单模型不注入） |
| P2 可观测性 | ✅ 已实施 | 端到端 PASS | `routing_log.py`：`log_routing` 写 `temp/routing_log.jsonl`（quality_switch / handoff 事件，线程安全 + try/except 兜底） |
| P2 ④ Cascade | ✅ 已实施 | 端到端 6/6 | `quality_estimator.py`(L0硬信号+L1启发式[过短/重复/拒绝/空]+L2可选judge，9/9) + `_detect_quality_issue`扩展(L1评估，阈值0.3防误判，`quality_cascade`开关)：软信号低分→升级切换。**judge架构最新**:agentmain _cj优选kimi作judge(temperature=0,commit43e3dc1);双向系统流验证:好输出(LRU)0.50不误判+坏输出(hard)0.20触发cascade;之前deepseek保守(0.1-0.2)因能力局限,prompt调优无效,换更强judge模型解决 |
| P2 ⑤ Planner-Executor | ✅ 已实施(轻量) | 真实 dispatch 4/4 | `do_planner` 工具：提供能力清单(P1a)引导分解+handoff分配；Evaluator 由④覆盖、Executor 由②③覆盖，三部分完整（非完整 plan 架构，属入口级落地） |
| P3 Bandit 自适应路由 | ✅ 已实施 | 收敛 4/4 | `bandit_router.py`(UCB1+状态持久化+线程安全，6/6) + MixinSession 接入(`__init__` 初始化+`_pick` 数据驱动 select+`_raw_ask` reward 反馈)；30 轮收敛 m0:m1=26:4，真正数据驱动选模型，`bandit_switch` 开关 |
| P3 ⑨ MoA 多智能体聚合 | ✅ 已实施+真实质量验证 | 真实质量对比通过 | `moa.py`(三阶段+aggregator prompt优化+过滤QE<0.3防污染)+`do_moa`(orm/动态clients感知handoff)。**真实适用边界**:复杂任务L1分数持平(0.70=0.70)但L2 judge揭示MoA(0.60)<best_solo(0.70)真实更差;多视角任务完整输出验证MoA=best(0.95=0.95)持平(注:截断输出会假报<best,完整输出才可靠);简单任务MoA≤best(aggregator自身缺陷);修复前0.00(refusal)→修复后0.30/0.70(永不更差)。QE分数持平≠无价值,MoA价值在信息综合 |
| 故障鲁棒性验证 | ✅ 加固后6/6+5单元测试 | 注入测试+P0加固 | MoA(P0加固,commit3c0dbf7): join加timeout(90s)/daemon防卡死阻塞+propose加retry(1次)+全失败fallback主模型单答(不再返None);**根因教训**:此前曾因某模型卡住致join无限等待→工具超时→无提示中断(原"无需加固"结论被推翻);5单元测试全绿(正常/retry/fallback/timeout不阻塞)。MixinSession: 全!!!Error→有限重试max_retries不无限循环/空响应不崩溃/主坏备用好→failover级联容错 |
| cost-aware MoA gate | ✅ 已实施+真实验证 | dispatch 4/4 + 真实PASS | `moa_gate.py`(复杂度评估:长度+复杂/简单关键词+very_short,阈值0.3) + `do_moa`前置gate。真实验证:简单任务(你好)gate拒绝省100%API成本,复杂任务(二分查找代码)gate放行MoA QE=0.70不降质 |
| P3 ⑥ 状态检查点 | ✅ 已实施(轻量) | 端到端 PASS | `state_checkpoint.py` save/load/delete(MixinSession session快照) + auto checkpoint(`checkpoint_switch`,质量切换时自动保存至json) |
| P3 ⑦ Orch-RM 资源调度 | ✅ 已实施(轻量) | 8/8 | `orchestrator_rm.py`: 核心编排层 token 预算追踪 + RPM/TPM 限流 + 日预算配额决策（与前端 `cost_tracker` 区分；当前不碰现有流程，作为基础设施，后续 Bandit/Handoff 可调用） |

> **实施红线遵循**：所有改动配字节备份（`temp/*.pre_p*.bak`）；**禁用 `git checkout` 回滚**（工作区含他人未提交改动：configure_mykey/stapp/memory md 等）；改码前 `ast.parse` + `import` 验证，改后真实 dispatch 端到端验证。
> **关键教训**：`do_handoff` 须用 `get_llm_name(b, model=True)`（有参，匹配真实签名 `get_llm_name(self, b=None, model=False)`）；generator 方法边界分支必须 `yield` 后再 `return StepOutcome`（dispatch `yield from` 要求可迭代）；`MixinSession(cfg)` 构造从 `cfg['llm_nos']` 取 session（测试桩须传，否则 `_sessions` 空→断言失败）；`agent_loop` 行59 动态 client 用 `getattr(handler.parent,'llmclient',client)` 兜底（无 parent 时退回原 client，零风险）；emoji 在源码用 `\U0001F504` 写法（非 surrogate pair `\ud83d\udd04`，否则 UTF-8 编码异常）。

---

> **集成测试基线**：`temp/multiagent_integration_test.py`（6场景回归：Cascade+Bandit+checkpoint协同 / handoff+routing_log / MoA+ORM自动record / 动态clients感知handoff / 全事件汇聚）。`python temp/multiagent_integration_test.py` 可重跑验证回归。改动任何编排模块后建议重跑。

## 版本历史

| 版本 | 时间 | 变更内容 | 变更原因 | 验证人 |
|------|------|----------|----------|--------|
| v1.0 | 2026-07-07 | 初始创建：汇总 Anthropic/Google 最佳实践、FrugalGPT/RouteLLM/MoA 论文、厂商模型策略，形成当前 LLM 编排 SOP | 用户需要全网调研并内化大模型编排知识，后续计划新增 DeepSeek API 和阿里云百炼 Coding API | Agent |
| v1.1 | 2026-07-07 | 补充：RouteLLM/FrugalGPT/MoA 论文要点；DeepSeek API 官方模型与定价（V4-Pro/V4-Flash）；阿里云百炼 Coding Plan 套餐、限制、Base URL 与合规要求；OpenAI 文档访问受限说明 | 第二次扫描剩余内容，补充论文与厂商 API 细节，为后续接入 DeepSeek 和阿里云百炼 Coding API 做准备 | Agent |
| v1.2 | 2026-07-07 | 补充：第三方路由平台（OpenRouter Pareto Router、LiteLLM Adaptive Router、Portkey 路由/负载均衡/故障转移）；智谱 GLM-5.2/5.1/5、Kimi k2.7-code/k2.6 等官方模型矩阵；修正 DeepSeek 缓存命中价；新增阿里云百炼模型选择页链接；新增§5.3厂商模型矩阵 | 第三次扫描收尾，内化路由平台与官方模型能力矩阵，为后续接入 DeepSeek 和阿里云百炼 Coding API 做准备 | Agent |
| v1.3 | 2026-07-07 | 新增 §6.5 安装与配置验证检查点；强制安装/修改 mykey.py 后做端到端主模型调用，避免协议类型错配导致主模型零调用并静默 fallback 到备模型；同步修复 configure_mykey.py 中 zhipu 类型继承缺失的 bug | 真实问题：智谱 GLM CN Coding Plan 配置生成后变量前缀为 native_oai_config，但 apibase 是 Anthropic 协议，导致 GLM 请求失败并 fallback 到 kimi，厂商控制台显示 0 调用 | Agent |
| v1.4 | 2026-07-07 | 新增 §11 GLM Coding Agent 使用最佳实践；内化智谱官方文档（docs.bigmodel.cn）中的 8 条最佳实践、3 层记忆机制、Agentic 扩展组件、常用工作流；补充官方文档索引链接；同步提升 GA 使用 GLM 作为主力模型时的项目治理与任务规划能力 | 用户要求深度学习 GLM 官方文档及最佳实践，并沉淀到记忆/SOP | Agent |
| v1.5 | 2026-07-07 | 新增 §12 模型特定经验教训管理；强调经验教训不可做成万能模板，必须按环境、版本、套餐、协议裁剪使用；明确审计周期周期（每 2 周 + 接入新模型/切换套餐前）；新增 model_lessons_learned.md 记录 GLM 国内 Coding Plan 和 Kimi 经验教训 | 用户同意沉淀经验教训，并要求按模型裁剪、标注边界、审计周期 | Agent |
| v1.6 | 2026-07-07 | 新增 §13 多智能体协作框架范式（5 范式 × GA 契合度）、§14 GA 多模型改进路线图（能力缺口诊断 + 9 改进点 P0-P3 优先级矩阵 + P0 实施红线）；来源：plan_multiagent_orchestration 调研报告（8 框架 + 7 论文 + GA 现状静态探测，双轮对抗验证 PASS） | 用户要求将多智能体编排调研成果沉淀为知识基线，指导后续 P0 改进 | Agent |
| v1.7 | 2026-07-07 | §14 新增 14.3 实施进展：P0 质量触发切换（真实 7/7）、P1 Handoff 真实 dispatch 集成（7/7）+ 能力卡片（4/4）、P2 路由可观测性（routing_log.py 端到端 PASS）全部落地验证；新增 routing_log.py 可观测性模块；④⑤ 标记后续（待质量估计器 / plan 架构入口） | 用户要求持续推进并验证到位，不止步于纸面方案 | Agent |