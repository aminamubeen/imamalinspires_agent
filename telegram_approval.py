"""
telegram_approval.py
--------------------
Sends a preview of the quote images + caption to the owner via Telegram,
waits for approval, and returns the final decision.

Flow:
    1. Send both images (dark + light) as a media group
    2. Send caption + hashtags as text
    3. Send inline keyboard: [✅ Post] [❌ Skip] [✏️ Edit Caption]
    4. If Edit Caption → ask for new caption, then re-confirm
    5. Return { "approved": bool, "caption": str, "hashtags": str }

Timeout: 15 minutes. If no response, auto-skips and notifies.

Required environment variables:
    TELEGRAM_BOT_TOKEN   - From @BotFather
    TELEGRAM_CHAT_ID     - Your personal chat ID (get from @userinfobot)
"""

import os
import time
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
TIMEOUT_SECONDS = 15 * 60   # 15 minutes
POLL_INTERVAL   = 3         # seconds between polling updates

APPROVE_CB = "action_approve"
SKIP_CB    = "action_skip"
EDIT_CB    = "action_edit"
CONFIRM_CB = "action_confirm_edit"
REVERT_CB  = "action_revert_edit"


# ── Telegram API helpers ──────────────────────────────────────────────────────
def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]

def _chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]

def _api(method: str, **kwargs) -> dict:
    url  = f"https://api.telegram.org/bot{_token()}/{method}"
    resp = requests.post(url, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _send_message(text: str, reply_markup: dict = None) -> int:
    """Sends a text message. Returns message_id."""
    payload = {
        "chat_id":    _chat_id(),
        "text":       text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _api("sendMessage", json=payload)
    return result["result"]["message_id"]


def _edit_message(message_id: int, text: str, reply_markup: dict = None):
    """Edits an existing message."""
    payload = {
        "chat_id":    _chat_id(),
        "message_id": message_id,
        "text":       text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        _api("editMessageText", json=payload)
    except Exception:
        pass  # Ignore if message hasn't changed


def _send_media_group(image_paths: list[str], caption: str) -> list[int]:
    """Sends up to 10 images as a single media group. Returns list of message_ids."""
    media = []
    files = {}
    for i, path in enumerate(image_paths):
        key = f"photo{i}"
        media.append({
            "type":    "photo",
            "media":   f"attach://{key}",
            "caption": caption if i == 0 else "",
            "parse_mode": "Markdown",
        })
        files[key] = open(path, "rb")

    payload = {
        "chat_id": _chat_id(),
        "media":   __import__("json").dumps(media),
    }
    resp = requests.post(
        f"https://api.telegram.org/bot{_token()}/sendMediaGroup",
        data  = payload,
        files = files,
    )
    for f in files.values():
        f.close()
    resp.raise_for_status()
    return [m["message_id"] for m in resp.json()["result"]]


def _answer_callback(callback_query_id: str, text: str = ""):
    """Acknowledges a callback query (removes loading spinner)."""
    _api("answerCallbackQuery", json={
        "callback_query_id": callback_query_id,
        "text": text,
    })


def _delete_message(message_id: int):
    try:
        _api("deleteMessage", json={"chat_id": _chat_id(), "message_id": message_id})
    except Exception:
        pass


# ── Keyboard builders ─────────────────────────────────────────────────────────
def _main_keyboard() -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Post",         "callback_data": APPROVE_CB},
            {"text": "❌ Skip",         "callback_data": SKIP_CB},
            {"text": "✏️ Edit Caption", "callback_data": EDIT_CB},
        ]]
    }

def _confirm_keyboard() -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Post with new caption", "callback_data": CONFIRM_CB},
            {"text": "↩️ Revert",               "callback_data": REVERT_CB},
        ]]
    }


# ── Polling ───────────────────────────────────────────────────────────────────
def _get_updates(offset: int) -> list:
    try:
        result = _api("getUpdates", json={
            "offset":  offset,
            "timeout": POLL_INTERVAL,
            "allowed_updates": ["callback_query", "message"],
        })
        return result.get("result", [])
    except Exception:
        return []


def _latest_update_id() -> int:
    """Gets the current latest update ID so we ignore old callbacks."""
    updates = _get_updates(offset=-1)
    if updates:
        return updates[-1]["update_id"] + 1
    return 0


# ── Main approval flow ────────────────────────────────────────────────────────
def request_approval(
    image_paths: dict,
    caption:     str,
    hashtags:    str,
    quote:       dict,
) -> dict:
    """
    Sends the preview to Telegram and waits for owner approval.

    Returns:
        {
            "approved": True/False,
            "caption":  final caption string,
            "hashtags": hashtags string,
        }
    """
    print("\nSending Telegram preview for approval...")

    # ── Send images ───────────────────────────────────────────────────────────
    preview_caption = (
        f"📸 *Quote Preview*\n\n"
        f"_{quote['text']}_\n\n"
        f"— {quote['author']}\n"
        f"_{quote['source']}, {quote['saying_ref']}_"
    )

    ig_images = [image_paths["instagram_dark"], image_paths["instagram_light"]]
    _send_media_group(ig_images, preview_caption)

    # ── Send caption preview ──────────────────────────────────────────────────
    caption_preview = (
        f"*📝 Caption:*\n{caption}\n\n"
        f"*#️⃣ Hashtags:*\n`{hashtags[:120]}...`"
    )
    ctrl_msg_id = _send_message(caption_preview, reply_markup=_main_keyboard())

    print(f"  Preview sent. Waiting up to 15 minutes for approval...")

    # ── Poll for response ─────────────────────────────────────────────────────
    offset       = _latest_update_id()
    deadline     = time.time() + TIMEOUT_SECONDS
    current_cap  = caption
    editing_mode = False
    pending_cap  = None

    while time.time() < deadline:
        updates = _get_updates(offset=offset)

        for update in updates:
            offset = update["update_id"] + 1

            # ── Callback button tapped ────────────────────────────────────────
            if "callback_query" in update:
                cb   = update["callback_query"]
                data = cb["data"]
                cb_id = cb["id"]

                # Only respond to callbacks from our chat
                if str(cb["message"]["chat"]["id"]) != str(_chat_id()):
                    continue

                _answer_callback(cb_id)

                if data == APPROVE_CB:
                    _edit_message(ctrl_msg_id, "✅ *Approved! Posting now...*")
                    print("  ✓ Approved by owner.")
                    return {"approved": True, "caption": current_cap, "hashtags": hashtags}

                elif data == SKIP_CB:
                    _edit_message(ctrl_msg_id, "❌ *Skipped. No post today for this slot.*")
                    print("  ✗ Skipped by owner.")
                    return {"approved": False, "caption": current_cap, "hashtags": hashtags}

                elif data == EDIT_CB:
                    editing_mode = True
                    _edit_message(
                        ctrl_msg_id,
                        "✏️ *Edit mode*\n\nSend me the new caption as a message.\n\n"
                        "_Tip: You can use *bold* and _italic_ markdown._",
                    )

                elif data == CONFIRM_CB and pending_cap:
                    current_cap  = pending_cap
                    editing_mode = False
                    pending_cap  = None
                    _edit_message(
                        ctrl_msg_id,
                        f"*📝 Updated Caption:*\n{current_cap}\n\n"
                        f"*#️⃣ Hashtags:*\n`{hashtags[:120]}...`",
                        reply_markup=_main_keyboard(),
                    )

                elif data == REVERT_CB:
                    editing_mode = False
                    pending_cap  = None
                    _edit_message(
                        ctrl_msg_id,
                        f"*📝 Caption (original):*\n{current_cap}\n\n"
                        f"*#️⃣ Hashtags:*\n`{hashtags[:120]}...`",
                        reply_markup=_main_keyboard(),
                    )

            # ── Text message (new caption) ────────────────────────────────────
            elif "message" in update and editing_mode:
                msg = update["message"]
                if str(msg["chat"]["id"]) != str(_chat_id()):
                    continue
                if "text" in msg:
                    pending_cap = msg["text"]
                    _delete_message(msg["message_id"])
                    _edit_message(
                        ctrl_msg_id,
                        f"*📝 New Caption Preview:*\n{pending_cap}\n\n"
                        f"*#️⃣ Hashtags:*\n`{hashtags[:120]}...`",
                        reply_markup=_confirm_keyboard(),
                    )

        time.sleep(POLL_INTERVAL)

    # ── Timeout ───────────────────────────────────────────────────────────────
    _edit_message(
        ctrl_msg_id,
        "⏰ *No response in 15 minutes — post skipped for this slot.*"
    )
    print("  ⏰ Timeout — auto-skipped.")
    return {"approved": False, "caption": current_cap, "hashtags": hashtags}


# ── Notification helpers ──────────────────────────────────────────────────────
def notify_posted(media_id: str, quote: dict):
    _send_message(
        f"✅ *Posted successfully!*\n\n"
        f"_{quote['text'][:80]}..._\n\n"
        f"Instagram Media ID: `{media_id}`"
    )

def notify_error(error: str):
    _send_message(f"🚨 *Pipeline error:*\n\n`{error}`")
