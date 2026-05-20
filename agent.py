"""
agent.py
Three-step pipeline:
  1. check_escalation()  — pure Python keyword scan, no API call
  2. classify_message()  — Haiku call, returns a category string
  3. draft_response()    — Sonnet call, returns a brand-voice reply

run_agent() orchestrates all three and returns a single result dict.
"""

import json
import os
import re

import anthropic
from dotenv import load_dotenv

from knowledge_loader import (
    CATEGORY_TO_FILES,
    build_classify_system_prompt,
    build_draft_system_prompt,
    load_knowledge_base,
)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

_client = None

def get_client():
    """Return the Anthropic client, initializing it on first use.

    Lazy initialization ensures the API key is resolved at call time
    rather than at module import time, which fixes Streamlit Cloud
    secret loading order issues.
    """
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

# Load the knowledge base and build both system prompts once when the module
# is first imported. Every subsequent call reuses these strings from memory,
# and the Anthropic API caches them server-side for 5 minutes.
_KB = load_knowledge_base()
_CLASSIFY_SYSTEM = build_classify_system_prompt()
_DRAFT_SYSTEM = build_draft_system_prompt(_KB)


# ── Step 1: Escalation check ─────────────────────────────────────────────────
# These are deterministic hard rules. If any keyword matches, we escalate
# immediately — we don't let the LLM make that call.

_ESCALATION_TRIGGERS = {
    "legal threat":       ["lawyer", "attorney", "sue", "lawsuit", "legal action", "court", "small claims"],
    "payment dispute":    ["chargeback", "dispute", "credit card company", "bank dispute", "paypal claim", "open a case"],
    "platform complaint": ["bbb", "better business bureau", "ftc", "report you", "report your shop"],
    "health & safety":    ["allergic reaction", "rash", "skin reaction", "chemical burn", "injury", "toxic"],
    "fraud / reputation": ["scam", "fraud", "counterfeit", "going to post about this", "warn people", "expose"],
}


def check_escalation(message: str) -> dict:
    """
    Scans the message for hard escalation keywords.
    Returns {"escalate": bool, "reason": str}.
    No API call — runs instantly.
    """
    lowered = message.lower()
    for trigger_type, keywords in _ESCALATION_TRIGGERS.items():
        for kw in keywords:
            if kw in lowered:
                return {"escalate": True, "reason": f"{trigger_type} — '{kw}' detected"}
    return {"escalate": False, "reason": ""}


# ── Step 2: Classification ────────────────────────────────────────────────────

def classify_message(message: str, order_context: str = "") -> str:
    """
    Haiku call — fast and cheap.
    Sends the customer message and asks for a JSON category.
    Returns the category string, falls back to "escalate_other" on any error.
    """
    user_content = f"Customer message: {message}"
    if order_context.strip():
        user_content += f"\nOrder context: {order_context}"

    response = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        system=[
            {
                "type": "text",
                "text": _CLASSIFY_SYSTEM,
                "cache_control": {"type": "ephemeral"},
                # cache_control marks this block as cacheable.
                # After the first call, Anthropic reuses the cached version
                # for 5 minutes — you're only charged ~10% of the token cost.
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw).get("category", "escalate_other")
    except json.JSONDecodeError:
        # Occasionally the model wraps the JSON in prose — extract it
        match = re.search(r'"category"\s*:\s*"([^"]+)"', raw)
        return match.group(1) if match else "escalate_other"


# ── Step 3: Response drafting ─────────────────────────────────────────────────

def draft_response(
    message: str,
    category: str,
    order_context: str = "",
    escalate: bool = False,
) -> str:
    """
    Sonnet call — higher quality, used only for drafting.
    The system prompt contains the full KB (32k chars) and is cached server-side.
    The user message tells Sonnet which category was classified and passes the
    customer message — this is the only part that varies between calls.
    """
    user_parts = [
        f"Customer category: {category}",
        f"Escalation flag: {'YES — this message requires human review after your reply' if escalate else 'no'}",
        f"Customer message: {message}",
    ]
    if order_context.strip():
        user_parts.append(f"Order context: {order_context}")
    user_parts.append(
        "\nDraft a short response (2–3 sentences, no blank lines between them) "
        "following the relevant SOP and LuxePress brand voice. "
        "Never tell the customer to 'DM us' — they are already in a DM conversation. "
        "If escalation is flagged, write a warm 1–2 sentence holding message and let the customer know "
        "a team member will personally follow up."
    )

    response = get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=[
            {
                "type": "text",
                "text": _DRAFT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": "\n".join(user_parts)}],
    )

    return response.content[0].text.strip()


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_agent(message: str, order_context: str = "") -> dict:
    """
    Full pipeline. Returns:
    {
        "category":           str,
        "sop_used":           list[str],
        "escalate":           bool,
        "escalation_reason":  str,
        "draft":              str,
    }
    Skips the Haiku classification call if escalation already fired — saves cost.
    """
    escalation = check_escalation(message)

    if escalation["escalate"]:
        category = "escalate_other"
    else:
        category = classify_message(message, order_context)

    draft = draft_response(
        message=message,
        category=category,
        order_context=order_context,
        escalate=escalation["escalate"],
    )

    return {
        "category":          category,
        "sop_used":          CATEGORY_TO_FILES.get(category, []),
        "escalate":          escalation["escalate"],
        "escalation_reason": escalation["reason"],
        "draft":             draft,
    }


if __name__ == "__main__":
    tests = [
        ("My package was supposed to arrive 3 days ago and tracking hasn't updated.", ""),
        ("The nails are too tight on my fingers, can I get a bigger size?", ""),
        ("I want to sue you people, this is ridiculous.", ""),
    ]

    for msg, ctx in tests:
        print(f"\n{'─'*60}")
        print(f"Message: {msg}")
        result = run_agent(msg, ctx)
        print(f"Category:  {result['category']}")
        print(f"SOP used:  {result['sop_used']}")
        print(f"Escalate:  {result['escalate']} | {result['escalation_reason']}")
        print(f"Draft:\n{result['draft']}")
