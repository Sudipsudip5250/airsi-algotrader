# API Keys Guide

All API keys are stored in `.env` (copied from `.env.example`).

---

## Telegram Bot (Free)

| Item | How to Get |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 1. Open Telegram → search `@BotFather`<br>2. Send `/newbot` → follow prompts<br>3. Copy the token (format: `123456:ABCdef...`) |
| `TELEGRAM_CHAT_ID` | 1. Start your bot, send it `/start`<br>2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`<br>3. Find `"chat":{"id":123456789}` in the response |

---

## AI provider order (free-first, API-only, no local daemon)

Routine commentary, classification, and research use this order:

1. **Groq** — free tier, primary (`GROQ_API_KEY`, default `GROQ_MODEL=openai/gpt-oss-20b`; `llama-3.1-8b-instant` shut down 08/16/26)
2. **Gemini** — free tier, secondary (`GEMINI_API_KEY`, default `GEMINI_MODEL=gemini-2.5-flash`; `gemini-2.0-flash` shut down 06/01/26)
3. **Hugging Face** — free tier (`HUGGINGFACE_API_KEY`)
4. **OpenRouter** — `OPENROUTER_MODEL=openrouter/free` router (auto-picks a free model) or any `:free` id, unless `AI_ALLOW_PAID=1`
5. **Pollinations keyless** — no key, free-trial last resort (`POLLINATIONS_MODEL=openai`; anon pool is rate-limited and sometimes budget-exhausted, so it is skipped automatically on quota text)
6. **Plain text / deterministic** — always available; the bot keeps running and the strategy fails closed

Set `AI_ALLOW_PAID=1` only for a human-triggered, high-value call. Logs print `provider=` and `cost_class=` (`free` / `low` / `paid`). `OPENROUTER_API_KEY` is currently optional but recommended as failover — without it the chain is Groq → Gemini → HF → Pollinations → deterministic.

---

## AI: Groq (Free — limits per model, no card)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up free (Google/GitHub)
3. Go to API Keys section
4. Click "Create API Key"
5. Copy key (starts with `gsk_...`)

---

## AI: OpenRouter (free models only by default)

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up free
3. Click "Create Key"
4. Copy key
5. Default model: `openrouter/free` (router auto-picks a free model; survives rotation)
6. Pinned alts: `openai/gpt-oss-20b:free`
7. Paid models are skipped unless `AI_ALLOW_PAID=1`
8. Browse models at [openrouter.ai/models](https://openrouter.ai/models)
9. Note: `:free` allowance is 50 req/day, 1000/day after a one-time $10 credit top-up

---

## AI: HuggingFace (Free Tier)

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Sign up free
3. Click "New Token" → role: "read"
4. Copy key
5. Default model: `HuggingFaceH4/zephyr-7b-beta`

---

## AI: Groq (Free Tier, No Card) — primary

Sign up at https://console.groq.com. Set `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-20b`
(quality alts: `openai/gpt-oss-120b`, `qwen/qwen3-32b`).
Add `GEMINI_API_KEY` (`GEMINI_MODEL=gemini-2.5-flash`) as secondary,
`OPENROUTER_API_KEY` with `OPENROUTER_MODEL=openrouter/free` as failover,
Pollinations keyless as last resort. Reasoning models need `max_completion_tokens`
of 1000+ (already set in `classify_news`); tiny limits return reasoning-only
truncations.

---

## Binance Exchange

### Paper Trading (No keys needed)
Leave `EXCHANGE_API_KEY` and `EXCHANGE_API_SECRET` empty in `.env`.

### Live Trading
1. Log in to [Binance](https://www.binance.com)
2. Go to API Management
3. Create new API key
4. **Disable "Withdrawals" permission** (critical for safety)
5. Enable only "Read" and "Trade"
6. Copy API Key and Secret into `.env`

---

## Freqtrade REST API (Local)

These protect your local bot dashboard:

| Variable | Description |
|---|---|
| `FREQTRADE_API_USER` | Choose any username (default: `botuser`) |
| `FREQTRADE_API_PASS` | Choose a strong password |
| `FREQTRADE_JWT_SECRET` | Generate with: `openssl rand -base64 64` |
