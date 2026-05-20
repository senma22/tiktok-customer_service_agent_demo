# TikTok Shop Customer Service Agent

An AI-powered customer service agent demo built for a TikTok Shop press-on nail brand. Takes a customer message, classifies it, drafts a brand-voice reply, and flags messages that need human escalation.

Built as a portfolio project — publicly demoable, cost-controlled, and designed around Anthropic's routing agent pattern.

---

## What it does

1. **Classifies** the customer message into a category (shipping, returns, sizing, product question, damaged item, or escalate)
2. **Checks for hard escalation triggers** — legal threats, chargebacks, health & safety — using deterministic keyword matching (no LLM involved)
3. **Drafts a reply** in the brand's voice, referencing the correct SOP from the knowledge base
4. **Returns** the category, drafted reply, escalation flag + reason, and which SOP was used

---

## Tech stack

| Layer | Tool |
|-------|------|
| Language | Python 3.12 |
| LLM — classification | Claude Haiku 4.5 (fast, cheap) |
| LLM — response drafting | Claude Sonnet 4.6 (higher quality) |
| UI | Streamlit |
| Deployment | Streamlit Community Cloud |
| Knowledge base | Local markdown files in `/knowledge` |

---

## Project structure

```
├── app.py                  # Streamlit UI
├── agent.py                # Core pipeline: classify → escalate check → draft
├── knowledge_loader.py     # Loads /knowledge files; builds cached system prompts
├── knowledge/              # Markdown knowledge base
│   ├── brand_overview.md
│   ├── brand_voice.md
│   ├── product_catalog.md
│   ├── sop_returns_refunds.md
│   ├── sop_shipping.md
│   ├── sop_sizing.md
│   ├── sop_price_inquiry.md
│   └── assets_index.md
├── evals/
│   ├── run_evals.py        # Eval runner — reports classification & escalation accuracy
│   └── test_cases.csv      # 31 test cases: happy paths, edge cases, escalation triggers
└── requirements.txt
```

---

## Agent design

Three steps per message, based on Anthropic's routing pattern:

```
customer message
      │
      ▼
check_escalation()   ← pure Python keyword scan, no API call
      │
      ├─ escalate? → skip classification, draft holding message
      │
      ▼
classify_message()   ← Haiku call, returns JSON category
      │
      ▼
draft_response()     ← Sonnet call, full KB as cached context
      │
      ▼
{ category, draft, escalate, escalation_reason, sop_used }
```

**Prompt caching** is enabled on both LLM calls. The knowledge base (~32k chars) is injected into the system prompt once and cached server-side for 5 minutes — cutting token costs by ~90% on repeated calls.

---

## Cost controls

- Haiku for classification (~$0.0001/call)
- Sonnet for drafting with prompt caching (~90% cost reduction on cache hits)
- `max_tokens=200` caps every draft call
- Session-based rate limit (5 requests per browser session)
- Hard monthly spend cap set in the Anthropic console

---

## Local setup

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd <repo-folder>

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API key
cp .env.example .env
# Edit .env and replace 'your_key_here' with your Anthropic API key

# 4. Run the app
streamlit run app.py

# 5. (Optional) Run evals
python evals/run_evals.py
```

---

## Streamlit Cloud deployment

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub account
3. Select this repo, set the main file to `app.py`
4. Under **Settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "your-key-here"
   ```
5. Deploy — Streamlit Cloud injects the secret as an environment variable, which the app reads via `os.getenv()`

---

## Evals

```bash
python evals/run_evals.py
```

Runs 31 test cases and reports classification accuracy, escalation accuracy, and saves all drafted responses to `evals/results/results_TIMESTAMP.csv` for human review. Re-run after any prompt change to catch regressions.

Current baseline: **94% classification accuracy, 100% escalation accuracy**.
