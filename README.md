# auto-grader-pilot

网上阅卷台的半自动批改助手：**截图 → 视觉识别 → 比对算分 → 点分提交 → 等下一份**。
PyAutoGUI 管鼠标键盘，pynput 管全局热键，OpenAI 兼容的视觉模型管"看题"。

## 现在这套坐标从哪来

`config.yaml` 里的 region / 控件坐标是照这台机器实测的：**2560×1600，系统缩放 175%，Edge 最大化**。

> 关键坑：缩放 175% 下，非 DPI 感知的进程只能看到 1463×914 的逻辑坐标，截出来的图也是残缺的。
> 脚本启动第一件事就是 `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`，所以配置里写的是**物理像素**。

换机器 / 改分辨率 / 改缩放了：`python scripts/region_picker.py` 拖框重新取坐标。

## 界面元素

| 名字 | 位置（物理像素） | 模板图 |
|---|---|---|
| 答题卡 | (413,482) 1705×663 | — |
| 送模型的整页 | (0,140) 2130×1230 | — |
| 题号/已阅/密号 | (1670,151) 874×80 | — |
| 打分板数字 0~7 | 见 `controls.digits` | `digit_0..7.png` |
| 满分 / 零分 / 问题卷 | (2181,316) / (2257,316) | `btn_full_marks.png` 等 |
| 满分7分 输入框 | (2255,452) | `input_score.png` |
| ✓ / ✗ | (2381,452) / (2441,452) | `btn_ok.png` / `btn_no.png` |
| 提交分数 | (2424,733) | `btn_submit.png` |

模板图在 `assets/templates/`，从 2.5K 截图切出来的，`locateOnScreen(confidence=0.85)` 命中不了会退回坐标。

## 安装

```powershell
py -m pip install -e .          # 依赖：pyautogui pynput pillow opencv-python pyyaml
$env:PYTHONPATH = "src"; py -m unittest discover -s tests -t tests   # 25 个用例

# 默认配置就指向本机 llama.cpp（无 key）：http://192.168.0.104:8080/v1
# 换云服务时才需要这些环境变量
# $env:AGP_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# $env:AGP_MODEL    = "qwen-vl-max"
# $env:AGP_API_KEY  = "sk-..."
```

装完后也可以直接用 `agp` 命令代替 `python -m agp.cli`。

## 场景 A：单份测试（人工确认后才提交）

```powershell
python scripts\snapshot_regions.py --focus 上河口 --open   # ① 先看 answer.png 截得对不对
python -m agp.cli --once --confirm --dry-run               # ② 干跑：只打分，不点鼠标
python -m agp.cli --once --confirm                         # ③ 真跑一份，回车才提交
```

① 抓完会弹输出目录，`answer.png` 应该只剩答题卡白纸（不带右侧打分板、不缺边缘）。
偏了就 `python scripts\region_picker.py` 拖框重新取坐标，填进 `config.yaml` 的 `regions.answer`。

③ 会停在：

```text
====================================================
  题号 3    得分 5 / 7
  (2)   3/3  命中: 夏季、昼长夜短、公转
  (3)   2/4  答出增加当地农民收入一条采分点，得2分
====================================================
  [Enter] 提交   [数字] 改分后提交   s 跳过这份   q 退出
提交 5 分? >
```

| 输入 | 行为 |
|---|---|
| 回车 | 按建议分提交：先点打分板数字，再点「提交分数」 |
| `4` | 改成 4 分再提交，超出 0~满分自动夹住 |
| `s` | 这份不提交，继续等下一份 |
| `q` | 停止整个循环 |

提示走终端 stdin，敲键盘要切回运行脚本的那个终端窗口。

## 场景 B：连续批改（不用人工确认）

```powershell
python -m agp.cli                  # 起来后按 F8 开始
python -m agp.cli --max-rounds 20  # 批 20 份自动停
```

热键（全局，不抢焦点）：

| 键 | 作用 |
|---|---|
| F8 | 开始 / 暂停后继续 |
| F9 | 只跑一轮 |
| F10 | 跳过当前这份（不填分） |
| Esc | 停止 |

## 其它参数

| 参数 | 作用 |
|---|---|
| `--dry-run` | 只记「会点哪、会填几分」，不动鼠标 |
| `--once` | 跑一份就退 |
| `--confirm` | 打印分数，人工确认后再提交 |
| `--debug` | DEBUG 日志：每次定位、每次点击 |
| `--max-rounds N` | 批 N 份停 |
| `-c other.yaml` | 换配置文件 |


安全：鼠标甩到屏幕左上角触发 PyAutoGUI FAILSAFE，进程退出并写日志。

## 答案文件

`answers.json`，按「题号」索引，题号从标题栏由视觉模型读出：

```json
{
  "questions": {
    "3": {
      "full_marks": 7,
      "subs": [
        {"label": "(2)", "points": 3, "mode": "each",
         "keys": ["夏季", "昼长夜短|昼夜长短", "公转"]},
        {"label": "(3)", "points": 4, "mode": "ai", "per_key": 2,
         "rubric": "每答对一条得 2 分，满分 4 分，任意两条即满分……"}
      ]
    }
  }
}
```

| mode | 判分方式 |
|---|---|
| `each` / `all` / `any` | 关键词命中（填空题用这个，一个采分点 1 分，错别字不算） |
| `ai` | 把 `rubric` + OCR 文本发给模型，模型直接给 0~`points` 分（整数），返回「分数 + 理由」 |

- `per_key: N`：按「条」给分，答对一条 N 分，封顶 `points`（AI 评分失败时的关键词兜底也遵守这个）。
- `keys` 里 `A|B|C` 是同义说法，命中任一即得这一分。
- `mode: ai` 打的是**同一个接口的纯文本请求**，每份卷多一次调用；模型挂了自动退回关键词命中（日志 WARN + `result.json` 里带 `fallback`），不会因此卡死或丢卷。
- 分数一律取**整数**（四舍五入），高于 `full_marks` 会被截断。
- 题号查不到 → 暂停，不乱填分。`"*"` 可作兜底题号（慎用，容易全员同分）。

## 换模型 / 换服务的回归测试

```powershell
py scripts/probe_llm.py --only models   # 1. 列模型，确认 config 里的 model 在列表里
py scripts/probe_llm.py --only ping     # 2. 一句话往返（0.6s 左右）
py scripts/probe_llm.py --only vision   # 3. 送样图读题，打印提取到的 (2)(3)
py scripts/probe_llm.py --only score    # 4. 四种卷面打分，带期望值断言
py scripts/probe_llm.py                 # 全套，退出码 0 = 全过
py scripts/probe_llm.py --live          # 不用样例图，直接截当前屏幕 page 区域
```

失败会打印 `实际 x` vs `期望 y`，便于判断是模型不行还是提示词要调。
`SCORE_CASES` 里的期望值就是验收标准，换题组时改这张表。

**推理模型注意**：本地 Qwen3.8 默认先吐一长串 `reasoning_content`，把 token 吃光后 `content` 就是空的，
看起来像"接口挂了"。所以 `vision.disable_thinking: true`（发 `chat_template_kwargs.enable_thinking=false`），
顺带快 1.5~4 倍。换成不支持这个参数的模型时把它设成 false 即可。

## 每轮产物

```
runs/2026-11-18T11-40-00/
  0001/answer.png  page.png  response.json  result.json
  run.log
  events.jsonl
```

`response.json` 是模型原始结构化返回，`result.json` 是算分明细（每子题命中/漏掉的关键词）。
规则改完拿历史数据离线重算，不用重新截图：

```powershell
py scripts/regrade.py runs/2026-11-18T11-40-00
```

## 调试开关

| 开关 | 作用 |
|---|---|
| `--dry-run` | 只记「会点哪、会填几分」，不动鼠标 |
| `--once` | 跑一份就退 |
| `--debug` | DEBUG 日志：每次定位、每次点击坐标 |
| `--max-rounds N` | 跑 N 份停 |
| `runs/*/events.jsonl` | 一行一轮，好 jq / pandas 统计 |
| `scripts/region_picker.py` | 拖框取坐标 |

## 注意

- 识别质量 = 手写体 + 视觉模型能力。`置信度` 低于 0.6 或出现 `[?]` 的卷子建议人工复核（配 `review_below`）。
- 翻页/换卷靠答题区像素差异检测（`change_ratio`），页面加载慢就调大 `settle_s`。
- 只处理「一份卷一道（组）题、右侧打分板可见」的界面；打分板收起时数字按钮点不到，会退回输入框打字。


