# @imamalinspires — Daily Quote Automation

A fully automated, human-in-the-loop pipeline that wakes up every morning and evening, picks a wisdom quote from Imam Ali (AS), renders beautifully styled images, writes a peaceful caption using Claude, and asks for your approval on Telegram before posting a carousel to Instagram — all on a randomised schedule so it never looks like a bot.

---

## How It Works

```
GitHub Actions triggers (start of time window)
            ↓
  Sleep random minutes within window
            ↓
  Pick quote → Render 4 images (Pillow)
            ↓
  Claude writes caption + hashtags
            ↓
  Telegram sends you a preview:
  [dark image] [light image]
  [✅ Post] [❌ Skip] [✏️ Edit Caption]
            ↓
  You approve (or edit) on your phone
            ↓
  Upload all images to Cloudflare R2
            ↓
  Post dark + light as Instagram carousel
            ↓
  Telegram confirms: ✅ Posted!
```

---

## Project Structure

```
├── main.py                        # Orchestrates the full pipeline
├── generate_image.py              # Pillow image renderer (dark + light themes)
├── claude_routine.py              # Calls Anthropic Claude API for caption + hashtags
├── telegram_approval.py           # Sends preview, waits for your approval
├── upload_to_r2.py                # Uploads all 4 images to Cloudflare R2
├── post_to_instagram.py           # Posts dark + light as carousel via Graph API
├── quotes.json                    # Quote library (id, text, author, source, used)
├── requirements.txt
├── assets/
│   ├── fonts/
│   │   ├── Lora.ttf
│   │   ├── Lora-Italic.ttf
│   │   ├── Poppins-Regular.ttf
│   │   ├── Poppins-Medium.ttf
│   │   └── Poppins-Bold.ttf
│   └── backgrounds/               # Optional: category-named JPEGs for backgrounds
│       └── patience.jpg           # Used when quote category = "patience"
├── output_images/                 # Generated images saved here (gitignored)
└── .github/
    └── workflows/
        └── daily_quote.yml        # Cron job — runs twice daily per schedule
```

---

## Image Output

Each run produces four images:

| File | Dimensions | Theme |
|------|-----------|-------|
| `instagram_{ref}_{date}_dark.jpg`  | 1080 × 1080 | Deep slate gradient |
| `instagram_{ref}_{date}_light.jpg` | 1080 × 1080 | Warm cream gradient |
| `pinterest_{ref}_{date}_dark.jpg`  | 1000 × 1500 | Deep slate gradient |
| `pinterest_{ref}_{date}_light.jpg` | 1000 × 1500 | Warm cream gradient |

The Instagram dark + light pair is posted as a two-slide carousel so followers can swipe between themes. All four images are archived in R2.

---

## Posting Schedule (IST)

Posts twice daily at a **random time within a window**, so the posting pattern never looks automated.

| Day | Morning window | Evening window |
|-----|---------------|---------------|
| Monday – Thursday | 7:00 – 9:00 AM | 7:00 – 9:00 PM |
| Friday | 6:00 – 8:00 AM | 8:00 – 10:00 PM |
| Saturday – Sunday | 8:00 – 10:00 AM | 6:00 – 8:00 PM |

GitHub Actions triggers at the start of each window. `main.py` then sleeps a random number of minutes before running — so the Telegram approval message arrives at an unpredictable time within the window.

---

## Telegram Approval Flow

Before anything is uploaded or posted, you receive a Telegram preview:

1. **Two images** — dark and light Instagram renders sent as a photo group
2. **Caption + hashtags** — the Claude-generated text
3. **Three inline buttons:**

| Button | Action |
|--------|--------|
| ✅ Post | Proceeds — uploads to R2 and posts the carousel |
| ❌ Skip | Skips this slot, no post made |
| ✏️ Edit Caption | Bot prompts you to type a new caption; shows a preview with Confirm / Revert buttons |

**Timeout:** If there is no response within **30 minutes**, the slot is **automatically posted with the original Claude-generated caption** and you receive a timeout notification. This applies even if you were mid-edit when the timeout hit — your in-progress edit is discarded and the original caption is used. To actively cancel a slot, tap **❌ Skip**.

---

## quotes.json Format

```json
[
  {
    "id": 1,
    "text": "Do not let your difficulties fill you with anxiety; after all, it is only the dark of night that produces the dawn.",
    "author": "Imam Ali (AS)",
    "source": "Nahj al-Balagha",
    "saying_ref": "Saying 21",
    "category": "patience",
    "used": false
  }
]
```

- **`category`** — optionally maps to a background image in `assets/backgrounds/`. If no match is found, a themed gradient is used.
- **`used`** — set to `true` after the quote is posted. When all quotes are used, the cycle resets automatically.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your fonts

Download [Lora](https://fonts.google.com/specimen/Lora) and [Poppins](https://fonts.google.com/specimen/Poppins) from Google Fonts and place the `.ttf` files in `assets/fonts/`.

### 4. Create a Telegram bot

1. Message [@BotFather](https://t.me/botfather) → `/newbot` → follow the steps
2. Copy the **bot token** it gives you
3. Message [@userinfobot](https://t.me/userinfobot) to get your **personal chat ID**
4. Start a conversation with your new bot (send it any message) so it can message you back

### 5. Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in → **Settings → API Keys → Create Key**
3. Copy the key (you'll only see it once)
4. Add a small amount of credit under **Settings → Billing** — the pipeline uses Claude Haiku, which is inexpensive (a few cents per month at twice-daily posting)

### 6. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add all of the following:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |
| `R2_ACCOUNT_ID` | Cloudflare dashboard → R2 |
| `R2_ACCESS_KEY_ID` | R2 → Manage R2 API Tokens |
| `R2_SECRET_ACCESS_KEY` | Same as above |
| `R2_BUCKET_NAME` | Your R2 bucket name |
| `R2_PUBLIC_URL` | Public URL of your bucket e.g. `https://pub-xxxx.r2.dev` |
| `IG_USER_ID` | Instagram Business Account ID |
| `IG_ACCESS_TOKEN` | Long-lived token from Meta Graph API Explorer (valid 60 days) |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | From @userinfobot |

> **Note:** Your R2 bucket must have **public access enabled**. The Instagram API fetches images by URL when creating the carousel, so uploaded files must be publicly readable.

> **Note:** The Instagram access token expires every **60 days**. Set a calendar reminder to refresh it via the Meta Graph API Explorer before it expires.

### 7. Run locally to test

```bash
export ANTHROPIC_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export R2_ACCOUNT_ID=your_id
export R2_ACCESS_KEY_ID=your_key
export R2_SECRET_ACCESS_KEY=your_secret
export R2_BUCKET_NAME=your_bucket
export R2_PUBLIC_URL=https://pub-xxxx.r2.dev
export IG_USER_ID=your_id
export IG_ACCESS_TOKEN=your_token

SLOT=morning python main.py
```

### 8. Do a manual GitHub Actions test

1. Go to your repo → **Actions** tab
2. Click **Daily Quote Post** → **Run workflow**
3. Choose `morning` → click **Run workflow**
4. Watch the logs in real time
5. Approve on Telegram when the preview arrives
6. Confirm the post appears on Instagram

---

## Customisation

**Change the posting schedule** — edit `SCHEDULE_IST` in `main.py` and update the cron expressions in `.github/workflows/daily_quote.yml` accordingly (convert IST → UTC by subtracting 5 hours 30 minutes).

**Change the approval timeout** — edit `TIMEOUT_SECONDS` at the top of `telegram_approval.py`:
```python
TIMEOUT_SECONDS = 30 * 60   # change to e.g. 15 * 60 for 15 minutes
```
Note: on timeout, the pipeline auto-posts with the original Claude caption rather than skipping. If you'd prefer the old "skip on timeout" behavior, change the timeout branch in `request_approval()` to return `{"approved": False, ...}`.

**Switch default theme** — edit `THEME` in `generate_image.py`:
```python
THEME = LIGHT_THEME   # or DARK_THEME
```

**Add background images** — drop a JPEG named after a quote category into `assets/backgrounds/`. For example, `patience.jpg` will automatically be used as the background for any quote with `"category": "patience"`.

**Change the handle** — update `HANDLE` at the top of `generate_image.py`:
```python
HANDLE = "@imamalinspires"
```

**Trigger manually** — go to Actions → Daily Quote Post → Run workflow, and choose `morning` or `evening`. Useful for testing without waiting for the cron.

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Image generation | [Pillow](https://python-pillow.org/) |
| AI caption writing | [Anthropic Claude](https://www.anthropic.com) (claude-haiku-4-5) |
| Human approval | [Telegram Bot API](https://core.telegram.org/bots/api) |
| Object storage | [Cloudflare R2](https://developers.cloudflare.com/r2/) |
| Social posting | [Meta Graph API](https://developers.facebook.com/docs/instagram-api/) |
| Automation | [GitHub Actions](https://docs.github.com/en/actions) |

---

## License

MIT — free to fork and adapt for your own quote page.

---

*Built with patience, for those who need a reminder that after every dark night, the dawn arrives.*
