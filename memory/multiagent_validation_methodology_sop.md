# 多智能体/复杂系统验证方法论 SOP

> 适用：任何多模块/多智能体系统的改进验证。提取自 §14 多智能体编排 20+turn 实战。
> - 版本：v1.0
> - 创建：2026-07-07
> - 最后验证：2026-07-07

## 验证梯度（必须全过才算闭环，缺一不可）
模块单测 → 系统集成 → 真实冒烟 → 质量对比(vs best) → 故障注入 → 默认路径回归

## 关键坑（实战发现，高复用）
1. **真实模型测试是必须**：Mock 测不出 thinking block 分离 / QE 地基 bug / 真实质量分布。真实冒烟抓出最致命的 QE L1 指令遵循盲区（两个不合格输出都评 1.0）。
2. **默认路径回归易被忽略**：核心改动必须验证不破坏普通单模型 turn（用真实 GenericAgent 实例化 + 默认对话验证，确认零触发多智能体功能）。
3. **故障注入是命门**：注入 proposer 异常 / 全失败 / fallback 级联失败，验证优雅降级非崩溃。MixinSession 全 session !!!Error 应有限重试不无限循环。
4. **QE 地基是路由命脉**：cascade/bandit/moa 全依赖 QE，QE 盲区 = 瞎路由。L1 启发式须加指令遵循检测（verbosity / meta_commentary 思考泄漏 / language_mismatch）。
5. **MoA 适用边界**：复杂任务 MoA=best（持平，综合多模型信息）；简单任务 MoA≤best（aggregator 自身缺陷）；修复后永不更差。QE 分数持平 ≠ 无价值。
6. **cost-aware gate 设计**：复杂度评估（长度+复杂/简单关键词+very_short）让简单任务走单模型省成本（真实验证：简单省 100% API，复杂不降质）。


7. **debug真实输出再归因(重要)**:测试FAIL时勿没看模型真实输出就归因"模型能力局限"。L2 judge曾浪费turns错归因deepseek_flash局限,实际是re冒号解析bug(模型输出"SCORE 0.9"无冒号,re要求冒号匹配空→fallback 0.5)。debug真实输出(judge完整输出+findall所有匹配)是定位根因关键,勿跳过。（延伸：MoA"复杂任务持平=best"结论也曾是incomplete attribution——L1分数0.70=0.70掩盖了真实差异，L2 judge揭示MoA(0.60)<best_solo(0.70)。**aggregate分数结论必须用debug真实输出/L2 judge验证**。）
## 工具技巧（被坑多次）
- **subprocess 跑脚本**：解决 import 缓存（reload 破坏 mykeys 模块状态）
- **回归基线脚本**：集成/故障/gate 三类，独立可重跑（`python temp/*_test.py`）
- **真实模型冒烟**：`llmcore.reload_mykeys()` 加载配置，**import mykey 是 GA 标准行为（非读取密钥内容）**
- **file_patch 替代 code_run 长字符串**：code_run 三引号嵌套易截断，file_patch 无转义问题

## 替代方案
无（首次系统化整理）。若验证体系演进，版本递增并标注失效部分。
