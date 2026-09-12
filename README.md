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
- Type `/upd <id> <wrong text>: <correct text>` → fixes a transcription typo
  in an already-saved memory, e.g. `/upd 101 said: side`. Every occurrence
  of the given text is replaced, so add a surrounding word or two (e.g.
  `/upd 101 said hello: side hello`) if the typo'd word appears more than
  once and you only mean one spot. The memory's embedding is regenerated
  after the fix, so search stays accurate. Typed only — not recognized in
  voice notes, since the exact wording and colon it depends on are exactly
  what Whisper tends to garble.
- Send a **photo** of anything with text in it (an invite, a sign, a
  screenshot) → a Groq vision model reads the text and saves it as a
  memory, e.g. `Saved (id 102): "..."`. No caption needed — an uncaptioned
  photo is saved as the text read from it, as-is. Add a caption and it's
  no longer just stapled on: a second Groq call reads the caption
  alongside the photo's text and writes the actual memory, so an
  instruction like "store the b'day, boy's name, and whose son he is" on
  a screenshot of birthday wishes for "Dhanwin" from "Smitha" produces
  something like `"Smitha's son Dhanwin's birthday is September 12"` —
  resolving "today"/"many happy returns" against the date the photo was
  actually sent, not left vague. A plain caption like "remember this"
  still degrades gracefully to roughly the old behavior (the photo's text,
  with the caption kept as a short prefix). If no legible text is found in
  the image, nothing is saved and the bot says so.
- In a **voice note**, start with the word **"question"** to ask instead of
  save — e.g. "question, where did I park the car?" The bot strips the
  "question" prefix and treats the rest as a search query instead of a new
  memory. (Typed messages don't need this prefix — any text that isn't
  `/mem` or an erase command is already treated as a question.)

## Deploying to Oracle Cloud "Always Free"

Since `bot.py` uses long-polling (`run_polling()`), it only ever makes
*outbound* connections to Telegram's servers — it never needs a public IP
opened for inbound traffic, port-forwarding, or a domain name. That keeps
this deployment much simpler than a typical web app.

**1. Create your Oracle Cloud account**
Go to https://www.oracle.com/cloud/free/ and sign up. Oracle requires a
credit card for identity verification even for the free tier, but Always
Free resources are not billed unless you explicitly upgrade to a paid plan.

**2. Create the compute instance**
- In the console: **Compute → Instances → Create Instance**
- Name it something like `voice-memory-bot`
- Image: **Ubuntu** (latest LTS) — simplest for this stack
- Shape: click **Change shape**, select **Ampere (ARM)**, choose **VM.Standard.A1.Flex**, and set it to an Always Free-eligible size (currently up to 2 OCPU / 12GB total across your Always Free instances — this bot needs only a fraction of that)
- Networking: leave the defaults, just confirm **"Assign a public IPv4 address"** is checked (needed for outbound internet access)
- SSH keys: let Oracle generate a key pair for you and **download the private key** (or paste in your own public key if you already have one)
- Click **Create** and wait for the instance to reach "Running"

**3. Connect to it**
From your Mac:
```bash
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<your-instance-public-ip>
```
(The public IP is shown on the instance's detail page in the console.)

**4. Install dependencies on the VM**
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg git
```

**5. Copy your project over**
From your Mac, in a new terminal tab (not the SSH session):
```bash
scp -i ~/Downloads/ssh-key-*.key -r /path/to/voice-memory ubuntu@<your-instance-public-ip>:~/
```

**6. Set up the project on the VM**
Back in your SSH session:
```bash
cd ~/voice-memory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**7. Set your secrets — this VM has no Keychain, so use `.env`**
`config.py` detects it isn't running on macOS and reads straight from
environment variables / `.env` — no code changes needed on your end, just
create the file:
```bash
cp .env.example .env
nano .env
```
Fill in the same four values you stored in Keychain on your Mac
(`TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY` — the service_role
key, `GROQ_API_KEY`), save with Ctrl+O then Enter, exit with Ctrl+X.

Lock the file down since it holds real secrets:
```bash
chmod 600 .env
```

**8. Test it**
```bash
python3 bot.py
```
You should see `Bot running. Press Ctrl+C to stop.` Test a voice note and a
question from Telegram as before. **Important:** stop the bot on your Mac
first (Ctrl+C) if it's still running there — Telegram's API rejects two
simultaneous long-polling connections using the same bot token, so only one
copy of `bot.py` can be running at a time, anywhere.

**9. Keep it running permanently**
Ctrl+C to stop the test run, then set it up as a background service so it
survives you disconnecting and restarts automatically if it crashes or the
VM reboots:
```bash
sudo tee /etc/systemd/system/voice-memory-bot.service > /dev/null <<EOF
[Unit]
Description=Voice memory Telegram bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/voice-memory
ExecStart=/home/ubuntu/voice-memory/venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now voice-memory-bot
```

Check it's running and see live logs:
```bash
sudo systemctl status voice-memory-bot
journalctl -u voice-memory-bot -f
```

From here, the bot runs whether or not your Mac is on, and survives VM
reboots automatically.

## Deploying to Google Cloud "Always Free" (e2-micro)

Like the Oracle guide above, this bot only makes outbound connections
(long-polling), so no public-facing ports or domain are needed here either.

**1. Create your Google Cloud account**
Go to https://console.cloud.google.com and sign up (a card is required for
verification, but the Always Free e2-micro instance itself isn't billed).

**2. Create a project**
In the console, click the project dropdown (top bar) → **New Project** →
give it a name like `voice-memory-bot` → Create.

**3. Create the VM**
- Go to **Compute Engine → VM instances → Create Instance**
- Name it `voice-memory-bot`
- **Region/Zone — this is the part that must be exact to stay free**: choose
  `us-west1`, `us-central1`, or `us-east1`. Any other region will incur
  charges.
- Machine type: **e2-micro** (under the "E2" series, shared-core)
- Boot disk: click **Change**, select **Ubuntu 24.04 LTS**, keep the disk
  at **30GB standard persistent disk** (this size and type stays free —
  don't switch to "Balanced" or "SSD" disks, which cost extra)
- Firewall: leave both **Allow HTTP** and **Allow HTTPS traffic** unchecked
  — the bot doesn't need inbound web traffic, only outbound API calls
- Click **Create**. Provisioning is typically instant — no capacity queue
  like Oracle's ARM tier.

**4. Connect to it**
Google gives you built-in browser SSH — no key management needed:
- On the VM instances list, click the **SSH** button next to your instance
- A terminal opens right in your browser, already authenticated

**5. Install dependencies**
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg git
```

**6. Copy your project over**
Easiest path from the browser SSH window: use `nano` to recreate each file,
or upload via the SSH window's built-in **Upload file** button (gear icon,
top right of the SSH terminal) to upload a zip of your `voice-memory`
folder, then:
```bash
unzip voice-memory.zip
cd voice-memory
```

**7. Set up the project**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**8. Set your secrets**
Same as the Oracle setup — no Keychain on Linux, so `config.py` reads from
`.env`:
```bash
cp .env.example .env
nano .env
```
Fill in `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY` (service_role),
and `GROQ_API_KEY`. **Also set `WHISPER_MODEL=tiny`** — e2-micro's ~1GB RAM
is too tight for the `base` model alongside everything else running. Save
with Ctrl+O, Enter, exit with Ctrl+X, then:
```bash
chmod 600 .env
```

**9. Add swap space (recommended)**
With only ~1GB RAM, transcription can still occasionally run out of memory
even on `tiny`. A swap file gives it breathing room:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**10. Test it**
```bash
python3 bot.py
```
Stop the bot anywhere else it's running first (Mac or Oracle) — only one
instance of `bot.py` can hold Telegram's long-poll connection at a time.

**11. Keep it running permanently**
Same `systemd` approach as Oracle:
```bash
sudo tee /etc/systemd/system/voice-memory-bot.service > /dev/null <<EOF
[Unit]
Description=Voice memory Telegram bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now voice-memory-bot
```

Check status and logs:
```bash
sudo systemctl status voice-memory-bot
journalctl -u voice-memory-bot -f
```

The browser SSH window can be closed after this — the bot keeps running as
a background service.

## Running via GitHub Actions instead of a persistent server

If you'd rather not keep any server running continuously, `poll_once.py`
does a single check for new Telegram messages, processes them, and exits —
designed to run as a GitHub Actions job instead of `bot.py`'s always-on
`run_polling()`. Rather than reinstalling every dependency and
re-downloading model weights on each run (slow), this project builds a
Docker image with everything baked in once, and each poll run just uses
that prebuilt image.

**Trade-off to understand first:** since the job only runs when triggered,
replies aren't instant. If you only use manual triggering, you'll record a
voice note in Telegram, then separately trigger a run (GitHub app or web
UI) to have it processed — a two-step flow, not a live chat. Adding a
scheduled trigger closes that gap to "within N minutes" instead of instant.

**How the two workflows fit together:**
- `.github/workflows/build-image.yml` — builds the Docker image (from
  `Dockerfile`) and pushes it to GitHub Container Registry (GHCR) whenever
  you change the code (or you trigger it manually). This is the slow one
  (a couple minutes, mostly installing dependencies and downloading model
  weights), but it only runs when something actually changed.
- `.github/workflows/poll.yml` — pulls that already-built image and runs
  `poll_once.py` inside it. This is the fast, frequent one — no install
  step, no model download, just pull (mostly cached after the first time)
  and run.

**Setup:**

1. Push this project to a GitHub repository.
2. Go to **Settings → Actions → General → Workflow permissions** and select
   **"Read and write permissions"** — needed so the build workflow can push
   the image to GHCR.
3. Go to **Settings → Secrets and variables → Actions** and add four
   repository secrets: `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`
   (service_role), `GROQ_API_KEY`.
4. Re-run `schema.sql` in Supabase's SQL editor if you haven't already —
   it now also creates a small `bot_state` table the poller uses to
   remember which messages it's already processed between runs.
5. Push to `main` (or trigger `build-image.yml` manually from the Actions
   tab) to build the image the first time. Check the Actions tab to confirm
   it succeeds — it should produce a package under your repo's **Packages**
   tab.
6. Once the image exists, go to **Actions → "Poll voice memory bot" → Run
   workflow** to trigger a poll manually any time (also works from the
   GitHub mobile app: Actions tab → workflow → Run workflow).

**Note on repo naming:** GHCR requires lowercase image tags. If your GitHub
username or repo name has uppercase letters, the `ghcr.io/${{
github.repository }}:latest` tag in both workflow files will fail to
push/pull — lowercase the repo name, or replace that expression with a
literal lowercase tag if renaming isn't an option.

**Public vs. private repo — this affects cost if you keep the schedule:**
`poll.yml` includes a `schedule:` trigger running every 15 minutes by
default. On a **public** repo, GitHub Actions minutes are unlimited and
free — the trade-off is your code (not your secrets, and not your stored
memories, which live in Supabase) is visible to anyone. On a **private**
repo, you get 2000 free minutes/month; since each poll run is now fast
(no install step), this schedule should use far fewer minutes than the
non-Docker approach did, but delete the `schedule:` block in `poll.yml`
and rely on manual triggering only if you want to be certain of staying
free.

**Important:** don't run `poll_once.py` (via Actions) and `bot.py`
(continuously, e.g. on a VM) at the same time — Telegram only allows one
consumer of `getUpdates` per bot token, and running both causes `Conflict`
errors. Pick one mode.

**When you change the bot's code:** push to `main` so `build-image.yml`
rebuilds the image before your next poll run — otherwise `poll.yml` keeps
using the old image.

**Faster manual triggering from your phone:** beyond the GitHub app, you
can trigger `workflow_dispatch` via GitHub's REST API with a personal
access token — this makes it possible to set up an iOS Shortcut (or
Android equivalent) that triggers a run with one tap/Siri phrase, without
opening the GitHub app at all. Ask if you want help setting that up.

**Live session mode, for a burst of near-instant replies:** `poll.yml`'s
schedule closes the gap to "within N minutes," but each run still only
processes one poll's worth of messages. For a stretch of actual
back-and-forth (asking a question, then a follow-up a few seconds later),
trigger **Actions → "Live session (voice memory bot)" → Run workflow**
instead. It runs `live_session.py`, which long-polls Telegram in a loop —
processing anything new every few seconds — for `duration_minutes`
(default 15) before exiting back to the normal schedule.

While a live session is running, it holds a lock (a timestamp in the same
`bot_state` table used for the offset) that `poll_once.py` checks first and
skips itself if the lock hasn't expired — otherwise both processes would
try to hold Telegram's `getUpdates` connection at once, which Telegram
rejects with a `Conflict` error. The lock releases itself as soon as the
session ends (or, worst case, expires on its own a little after the
requested duration), so there's no way to leave the bot stuck refusing to
poll.

## Keeping the Supabase free project awake

Free Supabase projects pause after 7 days with no API activity. If you don't
use the bot daily, add a small scheduled job (e.g. a GitHub Actions cron
hitting your Supabase REST endpoint every few days) to keep it alive.

## Notes

- The embedding model (`all-MiniLM-L6-v2`) produces 384-dimensional vectors,
  which is why `schema.sql` declares `vector(384)`. If you switch embedding
  models, update both places to match.
- Whisper's `base` model is used by default for speed on CPU. Set
  `WHISPER_MODEL=tiny` in `.env` on low-RAM hosts (like GCP's e2-micro), or
  `small`/`medium` for better accuracy on hosts with CPU/RAM to spare.
- The LLM model in `llm.py` is `openai/gpt-oss-20b`, one of Groq's currently
  active free-tier models. Groq periodically deprecates older models (this
  project originally used `llama-3.1-8b-instant`, since retired) — if you
  hit a `model_not_found` error again in the future, check
  https://console.groq.com/docs/models for the current list. `openai/gpt-oss-120b`
  is a larger, higher-quality alternative also on the free tier if you want
  better answers at the cost of a bit more latency.