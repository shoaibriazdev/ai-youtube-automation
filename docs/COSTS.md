# Costs and approvals

## The rule

**No paid API call happens without your approval.** Before a pipeline run, the platform estimates the cost
of the selected providers. If it is above the threshold (default **$0.00**, i.e. anything paid), the run
pauses with status *awaiting cost approval* and shows a table like:

| Stage | Provider | Units | Est. |
|---|---|---|---|
| script | claude-opus-5-5 | 11,000 tokens | $0.140 |
| images | openai | 7 images | $0.420 |
| video | runway | 30 seconds | $1.500 |
| voice | elevenlabs | 900 characters | $0.180 |

Approving allows spending up to that amount for that video. After the script is written (when the real number
of scenes is known) the estimate is checked again; if it grew beyond what you approved, it pauses again.

Change the threshold and monthly budget in **API Settings → Budget & spend**. Actual Claude token usage
and estimated provider costs are logged in the spend log.

## Typical cost per video (estimates, Nov 2026)

| Setup | Approx. per Short |
|---|---|
| All free (offline writer, storyboard/Pollinations, Ken Burns, Edge voices) | **$0** |
| Claude Opus 5.5 + free media | ~$0.15–0.30 |
| Claude Sonnet 5.5 + Replicate FLUX images + Edge voices | ~$0.10 |
| Claude + OpenAI images + ElevenLabs | ~$0.60–1.00 |
| Claude + images + Runway clips for 6 scenes | ~$2–4 |

Prices change. The table used for estimates is in `ytauto/costs.py`; override any value in
`data/pricing.json`, e.g.:

```json
{"image": {"openai": 0.05}, "video": {"runway": 0.05}, "tts": {"elevenlabs": 0.30}}
```

## Paid subscriptions to know about

- **Anthropic API**: pay-as-you-go credits. *Claude Pro/Max subscriptions do not include API usage.*
- **ElevenLabs**: free tier has a small monthly character allowance; regular use needs a paid plan.
- **Runway / Luma / Stability**: pre-paid credits.
- **OpenAI / Replicate**: pay-as-you-go.
- **YouTube Data / Analytics API**: free, limited by daily quota.
- **Pollinations / Edge voices**: free, no guarantees.
