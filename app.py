"""
app.py
LuxePress Customer Service Agent — Streamlit UI
"""

import os

import streamlit as st

# Ensure API key is available before agent module is imported
if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

from agent import run_agent

# ── Config ────────────────────────────────────────────────────────────────────

MAX_REQUESTS = 5

EXAMPLE_MESSAGES = [
    ("📦 Where's my order?",    "My package was supposed to arrive 3 days ago and tracking hasn't updated at all."),
    ("📏 Wrong size",           "The nails are way too tight on my fingers. Can I get a bigger size?"),
    ("💔 Damaged item",         "I just got my package and one of the nails arrived completely cracked."),
    ("💰 Price question",       "I saw the same set for 35% off during your live. Why did I pay full price?"),
]

# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LuxePress CS Agent",
    page_icon="💅",
    layout="centered",
)

st.title("💅 LuxePress Customer Service Agent")
st.caption(
    "AI-powered TikTok Shop CS demo · "
    "Classifies messages · Drafts brand-voice replies · Flags escalations"
)
st.divider()

# ── Example message buttons ───────────────────────────────────────────────────

st.markdown("**Try an example:**")
cols = st.columns(len(EXAMPLE_MESSAGES))
for i, (label, msg) in enumerate(EXAMPLE_MESSAGES):
    if cols[i].button(label, use_container_width=True):
        st.session_state["prefill_msg"] = msg

# ── Input fields ──────────────────────────────────────────────────────────────

message = st.text_area(
    "Customer message",
    value=st.session_state.get("prefill_msg", ""),
    height=120,
    placeholder="Paste or type a customer message...",
)

order_context = st.text_area(
    "Order context *(optional)*",
    height=80,
    placeholder="e.g. Order #12345, placed 5 days ago, 2 sets of square nails in Medium",
)

# ── Rate limit display ────────────────────────────────────────────────────────

if "request_count" not in st.session_state:
    st.session_state["request_count"] = 0

remaining = MAX_REQUESTS - st.session_state["request_count"]
st.caption(f"Requests remaining this session: **{remaining} / {MAX_REQUESTS}**")

# ── Generate button ───────────────────────────────────────────────────────────

clicked = st.button(
    "Generate response",
    type="primary",
    disabled=not message.strip() or remaining <= 0,
)

if remaining <= 0:
    st.warning("Session limit reached (5 requests). Open a new tab to continue.", icon="⚠️")

if clicked and message.strip() and remaining > 0:
    with st.spinner("Thinking..."):
        result = run_agent(message.strip(), order_context.strip())

    st.session_state["request_count"] += 1

    st.divider()

    # ── Results ───────────────────────────────────────────────────────────────

    col1, col2 = st.columns(2)
    col1.metric("Category", result["category"].replace("_", " ").title())
    col2.metric(
        "SOP used",
        result["sop_used"][0].replace(".md", "") if result["sop_used"] else "—",
    )

    if result["escalate"]:
        st.error(f"🚨 **Escalate to human** — {result['escalation_reason']}", icon="🚨")
    else:
        st.success("✅ No escalation needed")

    st.markdown("### Drafted reply")
    # Render formatted preview
    st.markdown(
        f"""<div style="background:#f9f5ff;border-left:4px solid #c084fc;
        padding:16px 20px;border-radius:6px;white-space:pre-wrap;
        font-size:0.95rem;line-height:1.6">{result["draft"]}</div>""",
        unsafe_allow_html=True,
    )

    # Copyable plain-text version
    with st.expander("Copy plain text"):
        st.code(result["draft"], language=None)
