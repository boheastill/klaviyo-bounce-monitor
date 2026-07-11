# Written outline to send Filip before the call

> 目的：兑现"call 前发 outline + demo"的承诺。短、人话、零 AI 腔。
> 发送时直接复制下面英文正文；可按需删减。附件建议:slack_preview.html 的截图
> (Slack 消息效果图) + n8n 画布截图(7 个节点全绿)。

---

Hi Filip,

As promised, here's the outline before our call. I went ahead and built the MVP so we have something concrete to look at.

**What's working now (I'll screen-share it live):**

- One n8n workflow: schedule trigger → pull Klaviyo campaigns from the last 3 days → delivery stats → hard vs soft bounce split → check against thresholds → Slack summary.
- Thresholds are in a single Config node: hard > 0.5%, soft > 2%, total > 2% to start. Changing them is editing one value, no code.
- The Slack message flags problem campaigns first (red for hard-bounce breaches since those hurt sender reputation, orange for soft/total), with healthy campaigns in a one-line footer.

**One thing I did differently on purpose:** I wrote a small mock of the Klaviyo API (same endpoints, same JSON shapes) and the workflow runs against it end to end. So you can see the whole thing working before sharing any API keys. Going live is pasting your private key and a Slack webhook into the Config node — nothing else changes.

**What I'd need from you to go live:** a Klaviyo private API key with read access to Campaigns + Metrics, and a Slack incoming webhook URL for the channel you want alerts in.

**Good questions for the call:** fixed thresholds vs per-account baseline (trailing 30-day average), alert every run vs daily digest, and which metric you'd want next (spam complaints and unsubscribes are the natural ones — same reporting API).

Talk soon,
Bohea

---

## Call script (给自己的,中文)

1. 开场 30 秒:感谢 + 直接说"我先把东西跑给你看,有问题随时打断"。
2. 屏幕共享顺序:
   a. n8n 画布 — 指一遍 7 个节点的数据流向(照着 sticky note 讲)。
   b. 点 Execute workflow — 全绿。点开 Evaluate 节点给他看 Block Kit JSON。
   c. 打开 slack_preview.html — "真实 Slack 里长这样"。
   d. 点开 Config 节点 — "你要改阈值,就是改这里,这就是 configurable 的意思"。
   e. 点开 mock server 终端 — "这是我仿的 Klaviyo API,所以今天不需要你任何密钥;
      切真实环境就是 Config 里换 3 个值"。
3. 抛决策问题(上面 Good questions 三条),让他说,记下来 — 这是"iterate together"。
4. 结尾:问密钥怎么给(建议只读权限的 private key),约下一个里程碑。
5. 不主动谈价;他问就按 proposal 的 $30/hr。

## 风险备忘

- Klaviyo 真实 API 的 statistic 名称/bounce_type 维度可能与 mock 有出入 —
  README 已声明"first live run validates payloads"。别在 call 上说死,说
  "shapes are mirrored from the current API revision, I validate on first live run"。
- 客户 job post 里埋了 AI 检测陷阱("wizard")— 所有发给他的文字都要过一遍人味检查,
  短句、有立场、别用 AI 套话。
