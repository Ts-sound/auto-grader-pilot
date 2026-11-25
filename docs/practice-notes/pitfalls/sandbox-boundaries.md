---
title: 受限沙箱里哪些操作会静默失败（以及怎么绕）
category: pitfalls
tags: [sandbox, dsh, pip, input-injection, low-integrity]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，开发自动批改脚本时在 Agent 沙箱内逐个撞墙
---

## 场景

在 Agent 的受限终端（低完整性级别 / AppContainer / 受限令牌）里开发或试跑需要"碰系统"的东西：
GUI 自动化、装第三方包、改用户级配置、调 git 凭证。

## 症状对照表

| 操作 | 症状 | 真实原因 |
|---|---|---|
| `SetCursorPos` / `mouse_event` | 返回 False，光标不动，但截图正常 | Low 完整性级别没有交互桌面输入权限 |
| `pyautogui.click()` | 不报错，一次也没点下去 | 同上，注入事件被丢弃 |
| `pip install --target` | `Permission denied: '...\pip-unpack-xxx\*.whl.metadata'`，留下删不掉的 `.tmp` | 临时目录/ACL 受限 |
| `python -m venv` | `ensurepip` 非零退出，之后 `No module named pip` | 同上 |
| `gh config set ...` | `failed to write config to disk: Access is denied` | 写 `%APPDATA%` 被拒 |
| `git` 的凭证 helper | `sh.exe: *** fatal error - couldn't create signal pipe` | 受限环境不允许子进程建管道 |
| `gh auth setup-git` | `could not lock config file ~/.gitconfig` | 写用户目录被拒 |

## 做法

1. **先测能不能，再写逻辑**。GUI 自动化开工前跑一次自检：

```python
def can_control_mouse() -> bool:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return bool(user32.SetCursorPos(pt.x, pt.y))   # 原位设置，成功即有权
```

拿不到控制权就大声告警，别跑完 50 单才发现一次没点。
2. **少依赖 = 少失败点**。装了 8 个包可能只缺 1 个（比如 `openai`），这时用 stdlib `urllib`
   直接打 `/chat/completions` 更划算，省掉一次装包失败。
3. 凭证、配置、临时目录全部落在**工作区内**，别落 `~`、`%APPDATA%`、系统 TEMP。
4. 需要真机交互的步骤（键鼠、装包、改全局配置）交给用户在自己的普通终端里执行，
   Agent 侧只负责生成命令和校验产物。

## 原因

低完整性令牌可以读文件、抓屏（这些走的是会话对象），但写用户目录、控制输入、创建管道都会被内核/沙箱策略拒绝，
而且很多 API 是"返回 False"而不是抛异常 —— 于是错误静默传播到业务逻辑里，表现为"程序不干活"。

## 反例

- 自测脚本里 `pyautogui.moveTo(400,300)` 两次读到的坐标一模一样，却没人当回事，还继续在真机上试。
- 用 `Select-String`/`Get-ChildItem` 遍历目录时突然大量 `Access is denied`，其实是 `.tmp` 里 pip 留下的残留目录 ACL 异常，与业务无关。
- 以为"能截屏 = 能自动化"，结果截图全对、点击全空。
