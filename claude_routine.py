"""
claude_routine.py
-----------------
Calls the Anthropic API to generate a peaceful Instagram caption
and relevant hashtags for a given Imam Ali (AS) quote.

Required environment variables:
    ANTHROPIC_API_KEY
"""

import os
import json
import anthropic


# ── Client ───────────────────────────────────────────────────────────────────
def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY environment variable not set.")
    return anthropic.Anthropic(api_key=api_key)


# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a calm, spiritual social media writer for the Instagram page @imamalinspires,
which shares wisdom from Imam Ali ibn Abi Talib (AS). Your writing style is:
- Simple, warm, and deeply peaceful
- Reflective but easy to understand for any reader
- Never preachy, never overly formal
- Invites the reader to pause, breathe, and reflect
- Feels like a gentle reminder, not a lecture

You always respond with valid JSON only. No preamble, no markdown fences, no extra text.
"""

USER_PROMPT_TEMPLATE = """\
Write an Instagram caption and hashtags for this quote:

Quote: "{text}"
Author: {author}
Source: {source}, {saying_ref}
Category: {category}

Return ONLY this exact JSON structure with no extra text:
{{
  "caption": "2 to 3 short peaceful sentences reflecting on the quote's meaning. Then on a new line, the quote itself wrapped in asterisks like *quote here*. End with one gentle soft call-to-action such as 'Save this as a reminder 🤍' or 'Let this sit with you today ✨'",
  "hashtags": "exactly 30 hashtags as a single space-separated string. Mix: Islamic wisdom, Imam Ali, spiritual wellness, motivation, mindfulness, and general inspirational tags."
}}
"""


# ── Main function ─────────────────────────────────────────────────────────────
def generate_caption_and_hashtags(quote: dict) -> dict:
    """
    Given a quote dict, calls Claude and returns:
        {
            "caption":  "...",
            "hashtags": "#ImamAli #Wisdom ..."
        }
    """
    client = _get_client()

    prompt = USER_PROMPT_TEMPLATE.format(
        text       = quote["text"],
        author     = quote.get("author", "Imam Ali (AS)"),
        source     = quote["source"],
        saying_ref = quote["saying_ref"],
        category   = quote.get("category", "wisdom"),
    )

    print("Calling Claude API to generate caption and hashtags...")

    message = client.messages.create(
        model      = "claude-opus-4-5",
        max_tokens = 1024,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON:\n{raw}") from e

    if "caption" not in result or "hashtags" not in result:
        raise ValueError(f"Claude response missing expected keys:\n{result}")

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
