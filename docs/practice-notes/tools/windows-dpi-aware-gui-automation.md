---
title: Windows 高分屏 GUI 自动化：先开 DPI 感知再谈坐标
category: tools
tags: [windows, dpi, pyautogui, screenshot, automation]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，auto-grader-pilot 首轮校准（2560x1600 @175%）
---

## 场景

用 pyautogui / PIL / 模板匹配做 Windows 桌面自动化，目标机是高分辨率 + 缩放（2.5K@175%、4K@150%）。
症状是"截图缺一块""坐标全偏""明明有按钮却找不到"。

## 做法

1. 进程启动第一件事声明 DPI 感知，**必须在任何截图/取坐标之前**：

```python
import ctypes
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_V2
except (AttributeError, OSError):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
```

PowerShell/Add-Type 侧同理，不然后面算出来的坐标和截图根本不是一个坐标系。

2. 此后 `GetSystemMetrics`、`VirtualScreen`、`pyautogui.screenshot()` 全部是**物理像素**。
   region、模板图、点击坐标统一按物理像素记录，并且**截图尺寸必须等于 region 宽高**，不等就是缩放/分辨率变了。

3. 自查手段：脚本里断言 `img.size == (region.width, region.height)`；模板 `locateOnScreen` 找不到时，先怀疑缩放，再怀疑窗口位移。

## 原因

非 DPI 感知进程被 DWM 虚拟化：看到的是逻辑像素，`CopyFromScreen` 也只覆盖逻辑区域对应的左上角一块。
于是页面右侧的内容"凭空消失"，人却会以为 UI 本来就没有那个面板。

## 反例

- 2560x1600 @175% 的机器上，`GetSystemMetrics` 报 `1463x914`（= 2560/1.75）。按这个尺寸截出来的图，页面右边的「分数 / 提交分数」被裁掉，白找了半小时"隐藏面板"。
- 同一台机器，PowerShell 加 `SetProcessDpiAwarenessContext(-4)` 前后分别报 `1463x914` 和 `2560x1600`；截图的模板随即从"对不上"变成"一次命中"。
- 混用两个解释器时更隐蔽：一个进程感知、一个不感知，同一组坐标在两边差 1.75 倍，点哪儿哪儿不对。
