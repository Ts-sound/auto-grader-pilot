---
title: 自动化时自家窗口抢焦点，截图抓到的是自己
category: pitfalls
tags: [windows, focus, electron, screenshot]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，代理窗口遮住目标页面导致多轮误判
---

## 场景

在 Agent / Electron 应用（或任何会主动 `focus()` 的宿主程序）的终端里驱动另一个窗口：
截图、点按钮、发键盘。表现是"目标程序没反应"或"截图里是聊天窗口"。

## 做法

1. 激活窗口用 `SwitchToThisWindow(hwnd, true)`，比 `SetForegroundWindow` 顶用：

```python
user32.SwitchToThisWindow(hwnd, True)
if user32.GetForegroundWindow() != hwnd:
    keybd_event(0x12, 0, 0, 0); keybd_event(0x12, 0, 2, 0)  # 敲一下 ALT 拿到前台权限
    user32.SetForegroundWindow(hwnd)
```

2. 鼠标点击**本身**就能激活窗口，所以"先点一下再操作"通常够用；键盘注入不同，注入前必须校验 `GetForegroundWindow()`。
3. 截图前把自家窗口挪出屏幕：`SetWindowPos(hwnd, 0, -3000, -3000, 0, 0, SWP_NOSIZE|SWP_NOZORDER)`，截完再挪回来。
   更省事的写法：截图脚本提供一个 `--focus <窗口标题片段>`，先拉目标再抓。
4. `PrintWindow` 对 Chromium 系窗口无效（实测 flag 0/1/2/3 全黑，平均亮度 0），别指望后台截屏。

## 原因

Windows 前台锁会静默拒绝 `SetForegroundWindow`；宿主每次重渲染都可能抢回焦点。
此时截图拿到的是最上层窗口，键盘事件也全发给宿主 —— 于是"目标不响应输入"是个假象。

## 反例

- 自定义 region 截图，抓出来是宿主对话窗口的内容；`answer.png` 里全是聊天记录。
- `GetForegroundWindow()` 返回 `65960`，一查是 `Shell_TrayWnd`（任务栏）—— 目标窗口被最小化，谁都没焦点。
- 同一套点击脚本，前半程能切 tab，后半程全无反应：差别只在宿主有没有抢回前台。
- 连续几轮把越界的截图送去识别，模型照样给出"看起来合理"的答案 —— 假数据比报错更难发现。
