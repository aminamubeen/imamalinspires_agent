"""
main.py
-------
Orchestrates the full daily quote pipeline with:
  - Random delay within a per-day, per-slot time window (IST)
    → skipped automatically when triggered manually via workflow_dispatch
  - Telegram preview + human approval before posting
  - Claude-generated caption + hashtags
  - Pillow image rendering
  - Cloudflare R2 upload
  - Instagram carousel post (dark first in morning, light first in evening)

Triggered by GitHub Actions twice daily.
Slot is passed via environment variable: SLOT=morning or SLOT=evening
"""

import os
import sys
import time
import random

from generate_image    import generate
from claude_routine    import generate_caption_and_hashtags
from upload_to_r2      import upload_images
from post_to_instagram import post_carousel
from telegram_approval import request_approval, notify_posted, notify_error

# IST = UTC+5:30
# Windows below are in IST. The workflow triggers at window_start (UTC),
# then we sleep a random duration within the window before posting.

# Structure: day_of_week (0=Mon) -> { "morning": (start_hr, end_hr), "evening": (...) }
SCHEDULE_IST = {
    0: {"morning": (7,  9),  "evening": (19, 21)},   # Monday
    1: {"morning": (7,  9),  "evening": (19, 21)},   # Tuesday
    2: {"morning": (7,  9),  "evening": (19, 21)},   # Wednesday
    3: {"morning": (7,  9),  "evening": (19, 21)},   # Thursday
    4: {"morning": (6,  8),  "evening": (20, 22)},   # Friday
    5: {"morning": (8,  10), "evening": (18, 20)},   # Saturday
    6: {"morning": (8,  10), "evening": (18, 20)},   # Sunday
}


def random_sleep_within_window(slot: str):
    """
    Sleeps a random duration so the actual post lands at a random
    time within the window for today's slot.
    """
    from datetime import datetime, timezone, timedelta

    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    day = now.weekday()

    window        = SCHEDULE_IST[day][slot]
    sleep_minutes = random.randint(5, 30)

    print(f"  Day    : {now.strftime('%A')}")
    print(f"  Slot   : {slot}")
    print(f"  Window : {window[0]}:00 – {window[1]}:00 IST")
    print(f"  Sleeping {sleep_minutes} min before running pipeline...")

    time.sleep(sleep_minutes * 60)


def run():
    slot = os.environ.get("SLOT", "morning").lower()
    if slot not in ("morning", "evening"):
        print(f"ERROR: SLOT must be 'morning' or 'evening', got '{slot}'")
        sys.exit(1)

    print("=" * 55)
    print(f"  @imamalinspires  —  Daily Quote Pipeline ({slot})")
    print("=" * 55)

    try:
        # ── Random delay within window ────────────────────────────────────────
        print("\n[0/5] Calculating random delay within window...")
        random_sleep_within_window(slot)

        # ── Step 1: Generate images ───────────────────────────────────────────
        print("\n[1/5] Generating images with Pillow...")
        result = generate()
        quote  = result["quote"]

        print(f'\n  Quote : "{quote["text"][:70]}..."')
        print(f'  Source: {quote["source"]}, {quote["saying_ref"]}')

        image_paths = {
            "instagram_dark":  result["instagram_dark"],
            "instagram_light": result["instagram_light"],
            "pinterest_dark":  result["pinterest_dark"],
            "pinterest_light": result["pinterest_light"],
        }

        # ── Step 2: Claude generates caption + hashtags ───────────────────────
        print("\n[2/5] Calling Claude for caption and hashtags...")
        content  = generate_caption_and_hashtags(quote)
        caption  = content["caption"]
        hashtags = content["hashtags"]

        # ── Step 3: Telegram approval ─────────────────────────────────────────
        print("\n[3/5] Requesting Telegram approval...")
        decision = request_approval(
            image_paths = image_paths,
            caption     = caption,
            hashtags    = hashtags,
            quote       = quote,
        )

        if not decision["approved"]:
            print("\n  Post skipped. Pipeline complete.")
            sys.exit(0)

        # Use potentially edited caption
        final_caption  = decision["caption"]
        final_hashtags = decision["hashtags"]

        # ── Step 4: Upload all images to R2 ──────────────────────────────────
        print("\n[4/5] Uploading images to Cloudflare R2...")
        urls = upload_images(image_paths)

        if "instagram_dark" not in urls or "instagram_light" not in urls:
            raise RuntimeError("Instagram images failed to upload to R2.")

        # ── Step 5: Post carousel to Instagram ───────────────────────────────
        # Morning → dark first (deep slate, calm start to the day)
        # Evening → light first (warm cream, soft end to the day)
        print("\n[5/5] Posting carousel to Instagram...")

        if slot == "morning":
            first_url  = urls["instagram_dark"]
            second_url = urls["instagram_light"]
            print("  Order: dark → light (morning)")
        else:
            first_url  = urls["instagram_light"]
            second_url = urls["instagram_dark"]
            print("  Order: light → dark (evening)")

        media_id = post_carousel(
            instagram_dark_url  = first_url,
            instagram_light_url = second_url,
            caption             = final_caption,
            hashtags            = final_hashtags,
        )

        # ── Notify success ────────────────────────────────────────────────────
        notify_posted(media_id, quote)

        print("\n" + "=" * 55)
        print("  ✓ Pipeline complete!")
        print(f"  Instagram Media ID : {media_id}")
        print(f"  R2 (IG dark)       : {urls.get('instagram_dark')}")
        print(f"  R2 (IG light)      : {urls.get('instagram_light')}")
        print(f"  R2 (Pin dark)      : {urls.get('pinterest_dark', 'N/A')}")
        print(f"  R2 (Pin light)     : {urls.get('pinterest_light', 'N/A')}")
        print("=" * 55)

    except Exception as e:
        error_msg = str(e)
        print(f"\n✗ Pipeline failed: {error_msg}")
        notify_error(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    run()
