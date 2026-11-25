---
title: 本地推理模型接口的回归姿势：分步探测 + 关掉 thinking
category: best-practices
tags: [llm, llama.cpp, regression, testing]
created: 2026-11-25
updated: 2026-11-25
source: 2026-11-18 会话，接 192.168.0.104:8080 上的 Qwen3.8-27B 做读题+评分
---

## 场景

本地起了 llama.cpp / vLLM / LM Studio 之类，提供 OpenAI 兼容接口，要拿它做图像识别或自动评分。
需求是"换模型能快速验收"，以及"它不动了怎么判断是哪一环坏了"。

## 做法

1. **按顺序探测，别跳步**：

```
GET  /v1/models       → 服务在不在、模型 id 对不对
GET  /health          → 模型加载完没有
GET  /slots           → 单 slot 服务是否卡着任务
POST /v1/chat/completions  短 ping（max_tokens 给足）
```

2. 回归脚本做成一条命令 + 可选分步，每步输出即时可见（`print(..., flush=True)`），
   失败时同时打印**实际值**和**期望值**；期望值写死在脚本里当验收标准。
   示例：`probe_llm.py --only models|ping|vision|score`。

3. **推理模型默认关 thinking**。llama.cpp 走 `chat_template_kwargs: {"enable_thinking": false}`；
   其他后端参数名不同，按厂商文档给。关掉之后再谈 JSON 约束。

4. 单 slot 服务上，回归脚本别一次串多个请求；超时的请求在服务端仍在跑，会把后面的全部堵住。

## 原因

- `/v1/models` 秒回只说明 HTTP 活着，不能证明能生成。
- 推理模型先吐 `reasoning_content`，`max_tokens` 给小了就只吐思考、`content` 返回空串 —— 表现是"接口不回话"，不是"接口挂了"。
- 单 slot 排队时所有请求一起变慢，看起来像模型崩了。

## 反例

- `max_tokens=16` + Qwen3.8 思考模式 → `content=''`，`reasoning` 25 字符；同一条请求关 thinking 后 2 个 token、1.3s → 0.7s。
- 一个回归脚本一次打 5 个请求（1 次读图 + 4 次评分），120s 超时后请求仍占着 slot，之后连 `/slots` 都开始超时，误判成"服务死了"。
- 只看 `/health` 返回 `{"status":"ok"}` 就以为没问题 —— 它连模型 id 对不对都不管。
