# API Keys Guide

All API keys are stored in `.env` (copied from `.env.example`).

---

## Telegram Bot (Free)

| Item | How to Get |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 1. Open Telegram → search `@BotFather`<br>2. Send `/newbot` → follow prompts<br>3. Copy the token (format: `123456:ABCdef...`) |
| `TELEGRAM_CHAT_ID` | 1. Start your bot, send it `/start`<br>2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`<br>3. Find `"chat":{"id":123456789}` in the response |

---

## AI: Groq (Free — 14,400 requests/day)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up free (Google/GitHub)
3. Go to API Keys section
4. Click "Create API Key"
5. Copy key (starts with `gsk_...`)

---

## AI: OpenRouter (Free Tier)

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up free
3. Click "Create Key"
4. Copy key
5. Default model: `deepseek/deepseek-chat` (free)
6. Browse models at [openrouter.ai/models](https://openrouter.ai/models)

---

## AI: HuggingFace (Free Tier)

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Sign up free
3. Click "New Token" → role: "read"
4. Copy key
5. Default model: `mistralai/Mistral-7B-Instruct-v0.3`

---

## AI: Ollama (Local, No Key Needed)

Run on the same machine or a VPS. See [local-ai-setup.md](local-ai-setup.md).

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
| `SESSION_SECRET` | Generate with: `openssl rand -base64 32` |
