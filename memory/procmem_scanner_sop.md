## 版本信息

- 版本：v1.0
- 创建时间：2026-07-06
- 最后验证：2026-07-06
- 状态：有效
- 替代方案：无

---

# Memory Scanner SOP

## 1. 快速开始
内存特征搜索工具，支持 Hex (CE 风格) 和 字符串匹配。特别提供 LLM 模式，方便大模型分析内存上下文。

**Python 调用方式:**
```python
import sys
sys.path.append('../memory') # 直接挂载工具目录
from procmem_scanner import scan_memory

# 示例：搜索特定 Hex 特征码，开启 llm_mode 以获取上下文
results = scan_memory(pid, "48 8b ?? ?? 00", mode="hex", llm_mode=True)
```

**CLI:**
```powershell
# 基础搜索
python ../memory/procmem_scanner.py <PID> "pattern" --mode string

# LLM 增强模式（输出包含上下文的 JSON，推荐）
python ../memory/procmem_scanner.py <PID> "pattern" --llm
```

## 2. 典型场景：结构体或关键数据定位
1. 确定目标数据的前导特征或已知常量（如特定的 Header 或 Magic Number）。
2. 在目标进程中搜索该特征：
   `scan_memory(pid, "4D 5A 90 00", mode="hex", llm_mode=True)`
3. 分析返回的 JSON 中 `context` 字段，查看目标地址前后的原始字节及 ASCII 预览。

## 3. 注意事项
- **权限**: 并非强制要求管理员权限，但需具备对目标进程的 `PROCESS_QUERY_INFORMATION` 和 `PROCESS_VM_READ` 权限。
- **效率**: 搜索大块内存时，优先提供更唯一的特征码以减少误报。

## 4. CE式差集扫描定位动态字段
定位微信等自绘UI中随操作变化的内存字段（如当前会话标题）。核心：一次全量scan + 多次ReadProcessMemory筛选。

## 失败与异常处理

1. **权限不足**：若无法打开进程句柄，确认是否拥有 `PROCESS_QUERY_INFORMATION` 和 `PROCESS_VM_READ` 权限；非管理员进程扫描系统进程通常会失败，改用管理员启动。
2. **特征码误报**：返回结果过多时，使用更长的唯一特征码或结合上下文（`context` 字段）人工过滤；必要时做差集扫描（CE 式）缩小候选集。
3. **目标进程保护/反调试**：部分进程会触发保护机制导致读取失败，此时停止扫描，禁止绕过反调试机制。
4. **无效 PID 或模式**：`scan_memory` 会抛出异常；调用方必须捕获并检查 PID 是否存活、pattern 是否合法。
5. **边界条件**：64 位进程扫描大地址空间时会耗时较长；优先限定模块范围或先扫描可执行模块区域。
