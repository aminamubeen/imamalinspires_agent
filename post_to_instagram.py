"""
post_to_instagram.py
--------------------
Posts a carousel (dark + light images as two slides) to Instagram
using the Meta Graph API.

Carousel flow:
    1. Create a child container for each image (image_url must be public)
    2. Create a carousel container referencing both children + caption
    3. Publish the carousel container

Required environment variables:
    IG_USER_ID       - Instagram Business Account user ID
    IG_ACCESS_TOKEN  - Long-lived Page/Instagram access token
"""

import os
import time
import requests


GRAPH_BASE = "https://graph.instagram.com/v21.0"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _user_id() -> str:
    return os.environ["IG_USER_ID"]


def _token() -> str:
    return os.environ["IG_ACCESS_TOKEN"]


def _raise_for_error(resp: requests.Response, context: str):
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        return
    if "error" in data:
        raise RuntimeError(f"{context} failed: {data['error']}")
    resp.raise_for_status()


# ── Step 1 — Create child media containers ───────────────────────────────────
def _create_child_container(image_url: str) -> str:
    """
    Uploads one image as a carousel child container.
    Returns the container ID string.
    """
    url  = f"{GRAPH_BASE}/{_user_id()}/media"
    resp = requests.post(url, params={
        "image_url":     image_url,
        "is_carousel_item": "true",
        "access_token":  _token(),
    })
    _raise_for_error(resp, f"Child container for {image_url}")
    container_id = resp.json()["id"]
    print(f"  ✓ Child container created: {container_id}")
    return container_id


# ── Step 2 — Create carousel container ───────────────────────────────────────
def _create_carousel_container(
    child_ids: list[str],
    caption: str,
    hashtags: str,
) -> str:
    """
    Creates a carousel container referencing the child IDs.
    Returns the carousel container ID.
    """
    full_caption = f"{caption}\n\n{hashtags}"

    url  = f"{GRAPH_BASE}/{_user_id()}/media"
    resp = requests.post(url, params={
        "media_type":    "CAROUSEL",
        "children":      ",".join(child_ids),
        "caption":       full_caption,
        "access_token":  _token(),
    })
    _raise_for_error(resp, "Carousel container")
    carousel_id = resp.json()["id"]
    print(f"  ✓ Carousel container created: {carousel_id}")
    return carousel_id


# ── Step 3 — Publish ─────────────────────────────────────────────────────────
def _publish_container(container_id: str) -> str:
    """
    Publishes a ready carousel container.
    Returns the published media ID.
    """
    url  = f"{GRAPH_BASE}/{_user_id()}/media_publish"
    resp = requests.post(url, params={
        "creation_id":  container_id,
        "access_token": _token(),
    })
    _raise_for_error(resp, "Publish carousel")
    media_id = resp.json()["id"]
    print(f"  ✓ Published! Media ID: {media_id}")
    return media_id


# ── Public function ───────────────────────────────────────────────────────────
def post_carousel(
    instagram_dark_url:  str,
    instagram_light_url: str,
    caption:             str,
    hashtags:            str,
) -> str:
    """
    Full carousel post flow:
        dark image (slide 1) + light image (slide 2)

    Returns the published Instagram media ID.
    """
    print("\nPosting Instagram carousel...")

    # 1. Create child containers
    print("  Creating child containers...")
    dark_id  = _create_child_container(instagram_dark_url)

    # Small delay to avoid rate-limit edge cases
    time.sleep(2)

    light_id = _create_child_container(instagram_light_url)
    time.sleep(2)

    # 2. Create carousel container
    print("  Creating carousel container...")
    carousel_id = _create_carousel_container(
        child_ids = [dark_id, light_id],
        caption   = caption,
        hashtags  = hashtags,
    )
    time.sleep(3)

    # 3. Publish
    print("  Publishing carousel...")
    media_id = _publish_container(carousel_id)

    print(f"\n✓ Carousel posted successfully to @imamalinspires")
    return media_id


# ── Entry point (for testing standalone) ─────────────────────────────────────
if __name__ == "__main__":
    # Requires env vars + real public image URLs to test
    test_dark  = "https://YOUR_R2_PUBLIC_URL/quotes/instagram_test_dark.jpg"
    test_light = "https://YOUR_R2_PUBLIC_URL/quotes/instagram_test_light.jpg"
    test_caption  = "Every hardship carries within it the seed of relief. 🌙\n\n*Do not let your difficulties fill you with anxiety.*\n\nSave this as a reminder 🤍"
    test_hashtags = "#ImamAli #IslamicQuotes #Wisdom #Patience #NahjAlBalagha"

    post_carousel(test_dark, test_light, test_caption, test_hashtags)
