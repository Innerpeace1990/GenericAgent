## 版本信息

- 版本：v1.0
- 创建时间：2026-07-06
- 最后验证：2026-07-06
- 状态：有效
- 替代方案：无

---

# Incubator SOP — 远程部署GA实例
自我复制到任意节点的agent网络。每个节点有独立记忆，通过编辑memory干预它们的行为

## 文件清单
```
GARoot/*.py
GARoot/assets/*.txt *.json
mykey.py
GARoot/memory/      
```
memory下大部分文件不适合分发，不要复制 memory 下未被 gitignore 白名单的文件！
不要复制 memory 下的L1/L2文件(global_mem(_insight).txt)，会自动初始化

打包红线：严格按上面4行清单执行，`*` 是 glob 全匹配，不得擅自改成“必要文件/可启动闭包”。
- `GARoot/*.py` 必须包含根目录所有 `.py`。
- `GARoot/assets/*.txt *.json` 必须包含 assets 顶层所有 `.txt`/`.json`。
- `GARoot/memory/` 只取 `.gitignore` 白名单/已允许分发文件；排除 `global_mem.txt`、`global_mem_insight.txt`、`__pycache__/`、`*.pyc`。
- 按当前清单实测压缩包约153KB/55文件；正常不应超过200KB，文件数不应超过60。

## 依赖
requests beautifulsoup4
优先复用远端已有python/venv

## 通信
1. **首选** 阅读 `assets/ga_httpapp.py`（HTTP API，~50行自解释）
2. 备选：subagent.md 文件协议 或 reflect worker + bbs

## 干预记忆
直接编辑远端 memory/ 下的文件（SOP/全局记忆）

## 失败与异常处理

1. **打包体积/文件数超限**：超过 200KB 或 60 文件 → 立即检查是否误打包了 `memory/` 下非白名单文件、`__pycache__/`、或 `*.pyc`。
2. **远端部署后无法启动**：确认远端 Python 版本 ≥ 3.10；检查 `assets/*.txt *.json` 是否已完整上传；密钥文件 `mykey.py` 是否按远端路径配置。
3. **依赖缺失**：远端没有 `requests`/`beautifulsoup4` 时，使用远端 pip 安装；若无法安装，则改用 `subagent.md` 文件协议或 reflect worker + bbs 作为备选通信。
4. **通信中断**：HTTP 不通时启用 `subagent.md` 文件协议；文件协议也不通时启用 BBS/reflect worker。
5. **记忆干预失败**：远端 `memory/` 文件无写权限时，先检查文件所有者；禁止直接覆盖 `global_mem.txt`/`global_mem_insight.txt`。
