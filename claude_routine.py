"""
claude_routine.py
-----------------
Calls the Google Gemini API to generate a peaceful Instagram caption
and relevant hashtags for a given Imam Ali (AS) quote.

Required environment variables:
    GEMINI_API_KEY   - From https://aistudio.google.com/app/apikey (free)
"""

import os
import json
import google.genai as genai


# ── Client ────────────────────────────────────────────────────────────────────
def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


# ── Prompt ────────────────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """\
You are a calm, spiritual social media writer for the Instagram page @imamalinspires,
which shares wisdom from Imam Ali ibn Abi Talib (AS). Your writing style is:
- Simple, warm, and deeply peaceful
- Reflective but easy to understand for any reader
- Never preachy, never overly formal
- Invites the reader to pause, breathe, and reflect
- Feels like a gentle reminder, not a lecture

Write an Instagram caption and hashtags for this quote:

Quote: "{text}"
Author: {author}
Source: {source}, {saying_ref}
Category: {category}

Return ONLY this exact JSON structure with no extra text, no markdown fences:
{{
  "caption": "2 to 3 short peaceful sentences reflecting on the quote meaning. Then on a new line the quote itself wrapped in asterisks like *quote here*. End with one gentle call-to-action such as Save this as a reminder 🤍 or Let this sit with you today ✨",
  "hashtags": "exactly 30 hashtags as a single space-separated string. Mix Islamic wisdom, Imam Ali, spiritual wellness, motivation, mindfulness, and general inspirational tags."
}}
"""


# ── Main function ─────────────────────────────────────────────────────────────
def generate_caption_and_hashtags(quote: dict) -> dict:
    """
    Given a quote dict, calls Gemini and returns:
        {
            "caption":  "...",
            "hashtags": "#ImamAli #Wisdom ..."
        }
    """
    model = _get_model()

    prompt = PROMPT_TEMPLATE.format(
        text       = quote["text"],
        author     = quote.get("author", "Imam Ali (AS)"),
        source     = quote["source"],
        saying_ref = quote["saying_ref"],
        category   = quote.get("category", "wisdom"),
    )

    print("Calling Gemini API to generate caption and hashtags...")

    response = model.generate_content(prompt)
    raw      = response.text.strip()

    # Strip accidental markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON:\n{raw}") from e

    if "caption" not in result or "hashtags" not in result:
        raise ValueError(f"Gemini response missing expected keys:\n{result}")

    print("✓ Caption and hashtags generated.")
    print(f"  Preview: {result['caption'][:90]}...")

    return result


# ── Entry point (for testing standalone) ─────────────────────────────────────
if __name__ == "__main__":
    test_quote = {
        "id":         1,
        "text":       "Do not let your difficulties fill you with anxiety; "
                      "after all, it is only the dark of night that produces the dawn.",
        "author":     "Imam Ali (AS)",
        "source":     "Nahj al-Balagha",
        "saying_ref": "Saying 21",
        "category":   "patience",
    }

    output = generate_caption_and_hashtags(test_quote)
    print("\nFull Caption:\n")
    print(output["caption"])
    print("\nHashtags:\n")
    print(output["hashtags"])
