# Git 连接与仓库清理检查点

> 创建时间：2026-07-06
> 最后更新：2026-07-06
> 任务：为本地 GenericAgent 仓库建立 GitHub SSH 连接，清理重复/空 .git 目录，并确认记忆系统 Lint 状态

## 当前状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 本地仓库 | ✅ 已提交 | 已有本地 commit，配置好 user.name/email |
| Fork | ✅ 已创建 | `https://github.com/Innerpeace1990/GenericAgent` |
| 本地 SSH 密钥 | ✅ 已生成 | `C:\Users\wangx\.ssh\id_github_genericagent` |
| SSH 配置与权限 | ✅ 已修复 | 仅当前用户可访问私钥、config、known_hosts |
| Git 可用 SSH 客户端 | ✅ 已确认 | `D:\Git\usr\bin\ssh.exe` (OpenSSH 10.3) 支持 GitHub 新 KEX 算法 |
| GitHub 公钥添加 | ✅ 已完成 | 用户通过 GitHub Mobile 完成 sudo 确认 |
| origin 改为 SSH | ✅ 已完成 | `git@github.com:Innerpeace1990/GenericAgent.git` |
| 推送到 fork | ✅ 已完成 | `main -> main`，已设置 upstream tracking |
| 重复 .git 清理 | ✅ 已完成 | 已删除 `D:\generic-agent\GenericAgent`（空目录）和 `D:\generic-agent\temp\storm_repo`（5.10 MB 独立克隆） |
| 记忆系统 Lint | ✅ 当前无问题 | `memory/memory_lint.py` 报告「未发现 Schema 违规问题」 |

## 完成记录

- **目标仓库**：`D:\generic-agent`（主仓库）
- **Git 配置**：`core.sshCommand = D:/Git/usr/bin/ssh.exe`
- **origin**：`git@github.com:Innerpeace1990/GenericAgent.git`
- **GitHub 公钥 title**：`GenericAgent-Windows-SSH`
- **推送结果**：`main -> main`，`branch 'main' set up to track 'origin/main'`
- **本地状态**：`On branch main`, `Your branch is up to date with 'origin/main'`, `nothing to commit, working tree clean`
- **重复克隆清理**：`D:\generic-agent\GenericAgent` 和 `D:\generic-agent\temp\storm_repo` 已删除，主仓库下仅剩 `D:\generic-agent\.git`

## 已尝试的关键步骤与发现

1. **fork 创建**：通过浏览器在 GitHub 上创建 fork 成功，目标为 `Innerpeace1990/GenericAgent`。
2. **SSH 密钥生成**：本地已生成 ed25519 密钥对 `id_github_genericagent` / `.pub`，并配置 `~/.ssh/config`：
   ```
   Host github.com
       HostName github.com
       User git
       IdentityFile C:\Users\wangx/.ssh\id_github_genericagent
       IdentitiesOnly yes
   ```
3. **权限修复**：Windows 默认权限导致 SSH 客户端报错。使用 `icacls` 去除继承权限，仅保留当前用户 `XUDONG\wangx` 对 `.ssh` 目录、config、私钥的完全控制。
4. **Windows 系统 OpenSSH 版本过低**：系统自带 `C:\Windows\System32\OpenSSH\ssh.exe` 为 9.5，不支持 GitHub 的新 KEX 算法 `sntrup761x25519-sha512@openssh.com`，直接 `ssh -T git@github.com` 会超时或失败。
5. **Git for Windows 的 OpenSSH 可用**：`D:\Git\usr\bin\ssh.exe` 版本为 OpenSSH 10.3，可正常与 GitHub 22 端口握手；连接返回 `Permission denied (publickey)`，符合预期（公钥尚未加入 GitHub）。
6. **GitHub 网页提交公钥**：在 `https://github.com/settings/ssh/new` 填写 title `GenericAgent-Windows-SSH` 和公钥后提交，页面跳转到 `session-authentication` 的 sudo 确认页，需要用户输入密码或使用 GitHub Mobile 验证。该步骤无法由 Agent 自动完成。
7. **重复 .git 目录排查**：发现 `D:\generic-agent\GenericAgent` 只包含空 `.git` 目录，`git` 命令实际回退到主仓库；`D:\generic-agent\temp\storm_repo` 是一个独立的 5.10 MB 克隆。两者已安全删除。

## 关键经验教训

- Windows 系统 OpenSSH 9.5 与 GitHub 最新 KEX 不兼容；本环境应使用 `D:\Git\usr\bin\ssh.exe`。
- GitHub 添加 SSH key 属于 sudo 操作，Agent 无法绕过，必须用户参与或 PAT。
- `.ssh` 目录及文件权限清理是 Windows 上 SSH 客户端正常工作的必要步骤；特别是 `known_hosts` 在追加后会被 PowerShell `Out-File -Append` 重置权限，需要重新用 `icacls` 授权。
- 使用 `form.querySelector('button[type="submit"]')` 而非文本匹配，可避免误触页面上的 "Submit feedback" 按钮。
- Git 在 Windows 上默认使用系统 SSH，需通过 `core.sshCommand` 显式指向 Git for Windows 的 ssh 才能使用新的 OpenSSH 版本。
- PowerShell 通过 `2>&1 | Out-String` 捕获 git 的 stderr 时，即使 git 操作成功，也可能把信息输出包装成 `RemoteException` 并返回非零 exit code，因此判断结果应以 git 自身的文本输出为准。
- `temp/` 目录被 `.gitignore` 忽略，检查点文件不应长期存放在此；需要迁移到仓库跟踪目录（如 `memory/`）才能提交。
- 在删除子目录前，应先确认 `.git` 是独立仓库还是空目录/工作树，避免误删主仓库的 git 元数据。
