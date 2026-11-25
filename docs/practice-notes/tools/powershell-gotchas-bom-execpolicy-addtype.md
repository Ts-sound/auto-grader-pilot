---
title: PowerShell 的静默坑：BOM、执行策略、Add-Type 警告、中文输出
category: tools
tags: [powershell, encoding, bom, add-type]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，用 PowerShell 做屏幕抓图/裁剪/写配置时逐个踩到
---

## 场景

用 PowerShell 驱动 Python 脚本、编译 C# 小工具（`Add-Type`）、写 JSON/YAML 配置，
或者只是想在控制台看中文输出。

## 做法

1. **执行策略禁止 dot-source `.ps1`** 时，用字符串执行绕过：

```powershell
Invoke-Expression (Get-Content -Raw -Encoding UTF8 $scriptPath)
```

`-Encoding UTF8` 不能省 —— 不写它会按系统 ANSI（GBK）读，中文窗口标题变 `涓婃渤鍙`，
拿去匹配窗口永远匹配不到。

2. **写文件避免 BOM**。PS 5.1 的 `Set-Content -Encoding UTF8` 会带 `EF BB BF`，
   Python `json.load` 直接报 `Unexpected UTF-8 BOM (decode using utf-8-sig)`。
   两个方向都做一层：写用 .NET，读用 `utf-8-sig`。

```powershell
[System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($false)))
```

```python
json.loads(Path(p).read_text(encoding="utf-8-sig"))
```

3. **`Add-Type` 把 C# 警告当错误**（warnaserror）。类里声明了没用的局部变量就编译失败，
   报错行看着跟错误无关。删掉未使用变量即可。

4. **中文控制台**：`[Console]::OutputEncoding = [Text.Encoding]::UTF8` + `$env:PYTHONIOENCODING="utf-8"`；
   或干脆写文件再 `Get-Content -Encoding UTF8` 看。

5. 判断 native 程序成功与否，**看输出内容，别看 `$LASTEXITCODE`**：管道里混入 stderr 会让
   PowerShell 抛 `NativeCommandError`，退出码不可靠。

## 原因

这几条都不会"报错退出"，只会给出错误的结果：乱码、多一个不可见字符、编译不过、退出码假阳性。
排查时人会先怀疑业务逻辑，浪费很多轮。

## 反例

- `answers.json` 被 PS 写进 BOM，程序能读（因为用了 `utf-8-sig`），但 `git diff` 显示首行被改，差点当成"内容变更"提交。
- 用 GBK 读脚本 → 中文窗口标题变成 `涓婃渤鍙`，`EnumWindows` 按标题找窗口永远返回空，误判"窗口不存在"。
- `Add-Type` 编译失败，报的是某行 C# 代码，实际原因是另一段里一个没用到的 `bool ok = false;`。
