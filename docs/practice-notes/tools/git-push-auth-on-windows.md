---
title: Windows 上 git push 认证：schannel、GCM、gh helper、SSH 四层坑
category: tools
tags: [git, ssh, gh, credentials, windows]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，首次 push auto-grader-pilot 时连续踩穿
---

## 场景

Windows + Git for Windows + GitHub CLI 已登录，`gh repo create` 建出来的仓库 remote 是 https，
第一次 `git push` 却认证失败。

## 症状链（会依次出现）

```
1) schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)
2) fatal: could not read Username for 'https://github.com': terminal prompts disabled
3) sh.exe: fatal error - couldn't create signal pipe, Win32 error 5
```

## 做法

按从快到稳的顺序：

1. **先换 TLS 后端**，确认真的是认证问题而不是 TLS：

```powershell
git -c http.sslBackend=openssl push origin main
```

2. **凭证 helper 在受限环境会挂**（走 shell）。要么用 `gh auth token` 拿 token 内联推一次：

```powershell
$tok = gh auth token
git -c http.sslBackend=openssl push "https://x-access-token:$tok@github.com/<owner>/<repo>.git" main
```

要么（推荐）**改成 SSH**：

```powershell
git remote set-url origin git@github.com:<owner>/<repo>.git
git config --local core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe"
ssh -T git@github.com    # 应回 "Hi <user>! You've successfully authenticated..."
```

3. `core.sshCommand` 这步别省：git 自带的 `usr/bin/ssh.exe` 在受限环境同样会
   `couldn't create signal pipe`，而 Windows 自带 OpenSSH 可以。

## 原因

- `git_protocol` 是 gh 自己的配置（`gh config list`），`gh repo create` 按它生成 remote，
  所以 remote 是 https 不是你选的。
- schannel 后端在部分机器上直接拿不到客户端凭证；GCM（credential.helper=manager）在没有交互桌面时也弹不出登录框。
- 受限终端里 helper 需要 spawn shell，而管道创建被禁。

## 反例

- `gh auth status` 显示已登录、token 有 `repo` 权限，但 push 仍然失败 —— 认证和 TLS 是两层，别混为一谈。
- `gh auth setup-git` 报 `could not lock config file ~/.gitconfig`，改用仓库级 `--local` 配置或一次性命令行参数才通。
- 内联 token 推成功后忘了它出现在命令行里一次（进程列表可见）；敏感环境建议直接走 SSH。
