# Klaviyo Bounce Monitor — Call Notes · Jul 9

## MVP decisions

**1. Thresholds** — fixed (hard 0.5% / soft 2% / total 2%), or auto-baseline
   per account (trailing 30-day average + margin)?
   →

**2. Alert cadence** — every run (every 12h), or one daily digest? Quiet hours?
   →

**3. Slack** — which channel? @-mention anyone on red (hard-bounce) alerts?
   →

**4. Next metric after bounces** — spam complaints / unsubscribes /
   deliverability by domain (Gmail vs Outlook vs Yahoo)?
   →

## Going live

**5. n8n hosting** — your existing instance / n8n cloud / I set one up?
   →

**6. Klaviyo API key** — read-only, scoped to Campaigns + Metrics only.
   Share whenever ready.
   →

**7. Slack webhook** for the real alerts channel.
   →

## Working together

**8. Updates** — async recaps here + Loom at milestones, or also a weekly
   live window? (Your mornings = my evenings, that works.)
   →

**9. Next builds** — you hand me a spec, or you describe the problem and
   I propose the approach?
   →

**10. What's next in your automation queue?**
   →
