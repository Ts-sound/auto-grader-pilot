# 实践笔记

过程知识沉淀：下次遇到同类任务，读一篇少走一段弯路。一条一个文件，分类目录见下。

| 标题 | 分类 | tags | 路径 | 更新时间 |
|---|---|---|---|---|
| 本地推理模型接口的回归姿势：分步探测 + 关掉 thinking | best-practices | llm, llama.cpp, regression, testing | [best-practices/local-llm-endpoint-regression.md](best-practices/local-llm-endpoint-regression.md) | 2026-11-25 |
| 自动化时自家窗口抢焦点，截图抓到的是自己 | pitfalls | windows, focus, electron, screenshot | [pitfalls/windows-focus-stealing-during-automation.md](pitfalls/windows-focus-stealing-during-automation.md) | 2026-11-25 |
| 受限沙箱里哪些操作会静默失败（以及怎么绕） | pitfalls | sandbox, dsh, pip, input-injection, low-integrity | [pitfalls/sandbox-boundaries.md](pitfalls/sandbox-boundaries.md) | 2026-11-25 |
| Windows 高分屏 GUI 自动化：先开 DPI 感知再谈坐标 | tools | windows, dpi, pyautogui, screenshot, automation | [tools/windows-dpi-aware-gui-automation.md](tools/windows-dpi-aware-gui-automation.md) | 2026-11-25 |
| PowerShell 的静默坑：BOM、执行策略、Add-Type 警告、中文输出 | tools | powershell, encoding, bom, add-type | [tools/powershell-gotchas-bom-execpolicy-addtype.md](tools/powershell-gotchas-bom-execpolicy-addtype.md) | 2026-11-25 |
| Windows 上 git push 认证：schannel、GCM、gh helper、SSH 四层坑 | tools | git, ssh, gh, credentials, windows | [tools/git-push-auth-on-windows.md](tools/git-push-auth-on-windows.md) | 2026-11-25 |

## 分类约定

- `workflow/` 流程、顺序、协作约定
- `best-practices/` 推荐做法、可复用模式
- `pitfalls/` 易错点、反例
- `tools/` 命令、参数、环境配置

跨类内容归主类，其余靠 tags 关联。新增条目必须进本表。
