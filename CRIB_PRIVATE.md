# ⛔ 底牌卡 — 仅自己看，绝不共享屏幕 ⛔

> Call 时放手机上或第二屏。共享屏幕前确认此文件已关闭。

## 固定话术（背到条件反射）

| 场景 | 说这句 |
|---|---|
| 开场定调 | "I'll drive with the screen — stop me anytime." |
| 没听清 | "Could you type that in the chat? I want to get it exactly right." |
| 答不上 | "Good question — I want to give you a precise answer, not a guess. I'll put it in the recap today." |
| 收尾锁定 | "I'll send a written recap of everything we decided right after this call." |

## 他大概率问的题 + 预写答案

**How long to go live?**
→ "The MVP is basically built. Once I have a read-only key — two or three
hours to wire it live, then a few days watching real data to tune thresholds."

**What do you need from me?**
→ "Two things: a read-only Klaviyo private key, Campaigns and Metrics scope
only — and a Slack webhook for the channel you want."

**Did you build this with AI / how do you work?**
→ 诚实，这是加分题（他 job post 必备技能就写着 claude code）:
"Claude Code writes a lot of the code — I design the architecture, the mock
API approach, and I verify everything end to end. That's where the speed
comes from."

**How many hours / cost?**
→ "The demo took me about a day. Going live and tuning is a few hours more.
After that we scope the next pieces together." （按 proposal $30/hr，别主动谈价）

**Are you available for ongoing work?**
→ "Yes — that's exactly what I'm set up for. Async-first, written updates,
your mornings overlap my evenings for live calls."

**Why the mock API?**
→ "Two reasons: you see the whole flow before sharing any keys, and I get a
test harness I keep using after we go live."

## 顾问牌（只打一句，放在他聊完需求后）

"Bounce alerts are the smoke detector — if deliverability is the real
concern, list hygiene and domain-level tracking are the natural next
pieces. We can go there after the MVP."

之后闭嘴。诊断免费，设计收费（那是下一个 milestone）。

## 流程备忘

1. Call 前 30 分钟：mock server 跑着、n8n 登录好、Slack 频道清干净、
   CALL_NOTES.md 开好、**此文件移出共享屏幕**、Windows Live Captions 开启、
   Upwork Meeting recap 开启。
2. 结构：寒暄 2 分钟 → 共享 CALL_NOTES.md 逐条过、当场打字记他的答案
   （10 分钟）→ 现场改一个阈值重跑 demo（如果气氛需要）→ 顾问牌一句 →
   收尾话术 → 结束。
3. 崩盘协议：听不懂 → 话术第 2 句转文字。绝不装懂。
4. Call 后 1 小时内：把 CALL_NOTES.md 填好的答案整理成英文 recap 发 Upwork。
