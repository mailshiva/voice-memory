# Voice memory bot

Record a voice note (or type a note) in Telegram, and later ask questions
about it. Everything runs on free tiers:

- **Telegram** — free bot API, handles the mobile recording UI for you
- **faster-whisper** — local, free speech-to-text
- **sentence-transformers (MiniLM)** — local, free embeddings
- **Supabase (pgvector)** — free-tier hosted vector database
- **Groq** — free-tier LLM API for the final answer

## Setup

1. **Telegram bot** — via BotFather on your iPhone, get a token.
2. **Supabase** — create a free project, run `schema.sql` in the SQL editor,
   copy the project URL and the **service_role** key from Project Settings > API.
3. **Groq** — free key from https://console.groq.com/keys
4. **Install**:
   ```bash
   brew install ffmpeg python
   cd voice-memory
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Storing secrets in macOS Keychain (instead of .env)

`config.py` checks Keychain first and only falls back to `.env` if a secret
isn't found there. All four secrets live under a single `voice-memory-bot`
Keychain service; store them once from your activated virtualenv:

```bash
python3 - <<'EOF'
import keyring
keyring.set_password("voice-memory-bot", "telegram_bot_token", "PASTE_TOKEN_HERE")
keyring.set_password("voice-memory-bot", "supabase_url", "PASTE_URL_HERE")
keyring.set_password("voice-memory-bot", "supabase_key", "PASTE_SERVICE_ROLE_KEY_HERE")
keyring.set_password("voice-memory-bot", "groq_api_key", "PASTE_GROQ_KEY_HERE")
EOF
```

Use the **service_role** key for `supabase_key` — it bypasses Row Level
Security entirely, which is why `schema.sql` doesn't need any RLS policies
beyond RLS being enabled (the default from the SQL editor dialog).

That's it — you can leave `.env` untouched (or not create it at all) on your
Mac. Keychain will prompt you to allow access the first time the bot reads
from it; choose "Always Allow" so it doesn't ask every run.

Note: Keychain only exists on macOS. If you later deploy to a Linux cloud
server, that box has no Keychain, so `config.py`'s fallback to `.env` /
environment variables is what kicks in there instead — you'll set the same
four values as plain environment variables on the server.

## Running locally

```bash
python bot.py
```

- Send a **voice note** → transcribed and saved automatically, with a memory
  id shown in the reply (e.g. `Saved (id 101): "..."`).
- Send `/mem <text>` → saved as a typed memo, no transcription needed, same
  id shown in the reply.
- Send **any other text message** → treated as a question; the bot searches
  your saved memories and answers based on what it finds.
- Say or type **"erase 101"** or **"erase id 101"** → deletes that memory by
  id. Works both as a voice note (Whisper transcribes it, the bot recognizes
  the erase pattern) and as typed text.
- In a **voice note**, start with the word **"question"** to ask instead of
  save — e.g. "question, where did I park the car?" The bot strips the
  "question" prefix and treats the rest as a search query instead of a new
  memory. (Typed messages don't need this prefix — any text that isn't
  `/mem` or an erase command is already treated as a question.)

## Deploying to the cloud instead of running on your Mac

Since `bot.py` uses long-polling (`run_polling()`), it only ever makes
*outbound* connections to Telegram's servers — it never needs a public IP,
open ports, or port-forwarding. That makes hosting options simpler than a
typical web app. Options roughly by cost, cheapest first:

1. **Raspberry Pi at home (~$0/month after a one-time ~$60–100 device)**
   Plug it into your home network, run the bot as a `systemd` service. Because
   of the polling model above, you don't need to expose it to the internet at
   all — it just needs outbound access, which any home router allows by
   default. Cheapest option long-term if you're open to owning the hardware.

2. **Oracle Cloud "Always Free" tier (~$0/month, no hardware)**
   A genuinely free-forever ARM VM. Note that Oracle reduced the Always Free
   ARM allowance in 2026 from 4 OCPU/24GB down to 2 OCPU/12GB — still
   comfortably enough to run this bot (Whisper's `base` model + a small
   Python process needs a fraction of that). Two caveats worth knowing:
   provisioning a free instance can hit "out of capacity" errors in busy
   regions, and Oracle can reclaim instances that show near-zero CPU/network
   activity for a long stretch — a bot that's actually being used shouldn't
   trigger that.

3. **A cheap always-on VPS (~$4–6/month)**
   Providers like Hetzner offer small VMs at low fixed prices with no
   capacity/reclamation headaches. Worth it if Oracle's setup friction isn't
   worth saving a few dollars a month to you.

For any of these, the deployment itself is the same: copy the project over,
install dependencies, set the four secrets as environment variables (or a
`.env` file) since there's no Keychain on Linux, and run `bot.py` under
`systemd` (or `screen`/`tmux` as a quick-and-dirty alternative) so it keeps
running after you disconnect.

## Keeping the Supabase free project awake

Free Supabase projects pause after 7 days with no API activity. If you don't
use the bot daily, add a small scheduled job (e.g. a GitHub Actions cron
hitting your Supabase REST endpoint every few days) to keep it alive.

## Notes

- The embedding model (`all-MiniLM-L6-v2`) produces 384-dimensional vectors,
  which is why `schema.sql` declares `vector(384)`. If you switch embedding
  models, update both places to match.
- Whisper's `base` model is used for speed on CPU. Swap to `small` or
  `medium` in `stt.py` for better transcription accuracy if your server has
  the CPU headroom.
- The LLM model in `llm.py` is `openai/gpt-oss-20b`, one of Groq's currently
  active free-tier models. Groq periodically deprecates older models (this
  project originally used `llama-3.1-8b-instant`, since retired) — if you
  hit a `model_not_found` error again in the future, check
  https://console.groq.com/docs/models for the current list. `openai/gpt-oss-120b`
  is a larger, higher-quality alternative also on the free tier if you want
  better answers at the cost of a bit more latency.
