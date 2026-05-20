"""
knowledge_loader.py
Loads /knowledge markdown files once at startup and builds the text blocks
that get injected into every API call's system prompt.
"""

import os

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")

# Which .md files back each agent category.
# product_question pulls from both the price SOP and the full product catalog.
CATEGORY_TO_FILES = {
    "shipping_inquiry": ["sop_shipping.md"],
    "returns_refunds":  ["sop_returns_refunds.md"],
    "sizing_fit":       ["sop_sizing.md"],
    "product_question": ["sop_price_inquiry.md", "product_catalog.md"],
    "damaged_item":     ["sop_returns_refunds.md"],
    "escalate_other":   [],
}

# Human-readable descriptions fed to Haiku for classification.
CATEGORY_DESCRIPTIONS = {
    "shipping_inquiry":
        "Questions about shipping status, delivery timing, tracking updates, or when an order will ship.",
    "returns_refunds":
        "Customer has opened or wants to open a formal TikTok Shop refund or return request.",
    "sizing_fit":
        "Sizing questions, nails don't fit, requests for a different size, or exchange requests.",
    "product_question":
        "Questions about product specs, materials, toolkit contents, how the nails work, or price differences.",
    "damaged_item":
        "Customer received their package but the product was damaged or broken — no formal return request open yet.",
    "escalate_other":
        "Anything that doesn't fit the above, or messages containing hostile, threatening, or legal language.",
}


def _read(filename: str) -> str:
    path = os.path.join(KNOWLEDGE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_knowledge_base() -> dict:
    """
    Reads every .md file in /knowledge (except review_needed.md which is
    internal housekeeping). Returns {filename: content}.
    """
    kb = {}
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.endswith(".md") and fname != "review_needed.md":
            kb[fname] = _read(fname)
    return kb


def build_classify_system_prompt() -> str:
    """
    Static prompt for the Haiku classification call.
    Tells the model the category list and asks for JSON only.
    Static = same every call = always a cache hit after the first call.
    """
    lines = [
        "You are a message classifier for a TikTok Shop customer service system.",
        "Classify the customer message into exactly one of the categories below.",
        'Return ONLY a JSON object with a single key "category". No other text.',
        "",
        "Categories:",
    ]
    for cat, desc in CATEGORY_DESCRIPTIONS.items():
        lines.append(f'  "{cat}": {desc}')
    return "\n".join(lines)


def build_draft_system_prompt(kb: dict) -> str:
    """
    Large static prompt for the Sonnet drafting call.
    Includes brand voice + all SOPs so it never changes between calls,
    which means it's always a cache hit after the first call.
    The user message tells Sonnet which category was classified.
    """
    return "\n\n".join([
        "You are a customer service agent for LuxePress, a women-owned handcrafted "
        "press-on nail brand selling on TikTok Shop. "
        "Follow the brand voice and SOP guidelines below exactly. "
        "Never invent policies not covered in the SOPs. "
        "Keep replies short — 2 to 3 sentences max per reply, no blank lines between sentences. "
        "Write everything as one compact block of text, no paragraph breaks.",

        "## Brand Voice\n"       + kb.get("brand_voice.md", ""),
        "## Brand Overview\n"    + kb.get("brand_overview.md", ""),
        "## Product Catalog\n"   + kb.get("product_catalog.md", ""),
        "## SOP: Returns & Refunds\n" + kb.get("sop_returns_refunds.md", ""),
        "## SOP: Shipping\n"     + kb.get("sop_shipping.md", ""),
        "## SOP: Sizing & Fit\n" + kb.get("sop_sizing.md", ""),
        "## SOP: Price & Product Questions\n" + kb.get("sop_price_inquiry.md", ""),
    ])


if __name__ == "__main__":
    kb = load_knowledge_base()
    print(f"Loaded {len(kb)} files: {list(kb.keys())}")

    classify_prompt = build_classify_system_prompt()
    draft_prompt = build_draft_system_prompt(kb)

    print(f"\nClassify system prompt: {len(classify_prompt):,} chars")
    print(f"Draft system prompt:    {len(draft_prompt):,} chars")
    print("\nCategory → SOP file mapping:")
    for cat, files in CATEGORY_TO_FILES.items():
        print(f"  {cat}: {files if files else '(catch-all, no SOP)'}")
