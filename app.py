import time

import streamlit as st

from agents import build_reader_agent, build_search_agent, critic_chain, writer_chain

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResearchMind",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

:root {
    --bg: #0e0d11;
    --surface: #17151a;
    --line: #2a2630;
    --text: #efe9de;
    --muted: #9a9288;
    --accent: #ff8c32;
    --done: #6fcf97;
}

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--text); }
.stApp { background: var(--bg); }

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 3rem 4rem; max-width: 1200px; }

/* hero */
.hero { padding: 3rem 0 2rem; }
.hero h1 {
    font-family: 'Syne', sans-serif;
    font-size: clamp(2.8rem, 6vw, 4.6rem);
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.03em;
    color: var(--text);
    margin: 0 0 1rem;
}
.hero h1 span { color: var(--accent); }
.hero-sub { font-size: 1.1rem; font-weight: 300; color: var(--muted); max-width: 540px; line-height: 1.65; }

.divider { height: 1px; background: var(--line); margin: 2rem 0; }

/* input */
.stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-size: 1rem !important;
    padding: 0.8rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(255,140,50,0.15) !important;
}
.stTextInput > label { color: var(--muted) !important; font-size: 0.9rem !important; }

/* primary button */
button[data-testid="stBaseButton-primary"] {
    background: var(--accent) !important;
    color: #1a1209 !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.7rem 2rem !important;
    transition: background .15s ease !important;
}
button[data-testid="stBaseButton-primary"]:hover { background: #ffa05a !important; }

/* example chips (secondary buttons) */
button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    color: var(--muted) !important;
    border: 1px solid var(--line) !important;
    border-radius: 999px !important;
    font-size: 0.82rem !important;
    padding: 0.2rem 0.8rem !important;
}
button[data-testid="stBaseButton-secondary"]:hover { color: var(--accent) !important; border-color: var(--accent) !important; }

/* pipeline */
.section-heading { font-family: 'Syne', sans-serif; font-size: 1.25rem; font-weight: 700; margin: 0 0 1rem; }
.step { display: flex; align-items: baseline; gap: .8rem; padding: 1rem 0 1rem 1rem;
        border-left: 3px solid var(--line); margin-bottom: .6rem; }
.step.running { border-left-color: var(--accent); }
.step.done { border-left-color: var(--done); }
.step .title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: .98rem; }
.step .desc { color: var(--muted); font-size: .85rem; margin-top: .15rem; }
.step .status { margin-left: auto; padding-right: 1rem; font-size: .8rem; color: #6c655d; white-space: nowrap; }
.step.running .status { color: var(--accent); }
.step.done .status { color: var(--done); }

/* results */
div[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--line) !important; border-radius: 12px !important; background: var(--surface); }
.panel-label { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 1.05rem; margin-bottom: .6rem; }
.panel-label.orange { color: var(--accent); }
.panel-label.green { color: var(--done); }

details summary { color: var(--muted) !important; }

.notice { color: #6c655d; font-size: .8rem; text-align: center; margin-top: 3rem; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
""",
    unsafe_allow_html=True,
)

# ── Helpers ──────────────────────────────────────────────────────────────────
STEPS = [
    ("search", "Search agent", "Gathers recent web information"),
    ("reader", "Reader agent", "Scrapes the best source for detail"),
    ("writer", "Writer chain", "Drafts the full report"),
    ("critic", "Critic chain", "Reviews and scores the report"),
]
STATUS_LABEL = {"waiting": "waiting", "running": "running…", "done": "done"}


def as_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content)


def pipeline_html(states: dict) -> str:
    rows = []
    for key, title, desc in STEPS:
        s = states.get(key, "waiting")
        rows.append(
            f'<div class="step {s}"><div><div class="title">{title}</div>'
            f'<div class="desc">{desc}</div></div>'
            f'<span class="status">{STATUS_LABEL[s]}</span></div>'
        )
    return '<div class="section-heading">Pipeline</div>' + "".join(rows)


def set_example(text: str):
    st.session_state["topic_input"] = text


st.session_state.setdefault("results", {})

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero">
    <h1>Research<span>Mind</span></h1>
    <p class="hero-sub">
        Four agents work in turn: one searches, one reads the best source,
        one writes the report, and one critiques it.
    </p>
</div>
<div class="divider"></div>
""",
    unsafe_allow_html=True,
)

# ── Layout ───────────────────────────────────────────────────────────────────
col_input, _, col_pipeline = st.columns([5, 0.5, 4])

with col_input:
    topic = st.text_input(
        "What should we research?",
        placeholder="e.g. Quantum computing breakthroughs in 2026",
        key="topic_input",
    )
    run_btn = st.button("Run research", type="primary", use_container_width=True)

    examples = ["LLM agents", "CRISPR gene editing", "Fusion energy progress"]
    chip_cols = st.columns(len(examples))
    for col, ex in zip(chip_cols, examples):
        col.button(ex, key=f"ex_{ex}", on_click=set_example, args=(ex,), use_container_width=True)

with col_pipeline:
    pipeline_slot = st.empty()

# initial pipeline state: all done if a finished run is loaded, otherwise waiting
r = st.session_state["results"]
states = {k: ("done" if k in r else "waiting") for k, _, _ in STEPS}
pipeline_slot.markdown(pipeline_html(states), unsafe_allow_html=True)

# ── Run ──────────────────────────────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.warning("Enter a research topic first.")
    else:
        topic_val = topic.strip()
        results = {}
        states = {k: "waiting" for k, _, _ in STEPS}

        def mark(key: str, value: str):
            states[key] = value
            pipeline_slot.markdown(pipeline_html(states), unsafe_allow_html=True)

        try:
            mark("search", "running")
            sr = build_search_agent().invoke(
                {"messages": [("user", f"Find recent, reliable and detailed information about: {topic_val}")]}
            )
            results["search"] = as_text(sr["messages"][-1].content)
            mark("search", "done")

            mark("reader", "running")
            rr = build_reader_agent().invoke(
                {
                    "messages": [
                        (
                            "user",
                            f"Based on the following search results about '{topic_val}', "
                            f"pick the most relevant URL and scrape it for deeper content.\n\n"
                            f"Search Results:\n{results['search'][:800]}",
                        )
                    ]
                }
            )
            results["reader"] = as_text(rr["messages"][-1].content)
            mark("reader", "done")

            mark("writer", "running")
            results["writer"] = as_text(
                writer_chain.invoke(
                    {
                        "topic": topic_val,
                        "research": f"SEARCH RESULTS:\n{results['search']}\n\n"
                        f"DETAILED SCRAPED CONTENT:\n{results['reader']}",
                    }
                )
            )
            mark("writer", "done")

            mark("critic", "running")
            results["critic"] = as_text(critic_chain.invoke({"report": results["writer"]}))
            mark("critic", "done")

            st.session_state["results"] = results
        except Exception as exc:
            st.error(
                f"The pipeline stopped: {exc}\n\nCheck your API keys in .env and your connection, then try again."
            )

# ── Results ──────────────────────────────────────────────────────────────────
r = st.session_state["results"]

if r:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    if "search" in r:
        with st.expander("Search results (raw)"):
            st.markdown(r["search"])
    if "reader" in r:
        with st.expander("Scraped content (raw)"):
            st.markdown(r["reader"])

    if "writer" in r:
        with st.container(border=True):
            st.markdown('<div class="panel-label orange">Final report</div>', unsafe_allow_html=True)
            st.markdown(r["writer"])
        st.download_button(
            "Download report (.md)",
            data=r["writer"],
            file_name=f"research_report_{int(time.time())}.md",
            mime="text/markdown",
        )

    if "critic" in r:
        with st.container(border=True):
            st.markdown('<div class="panel-label green">Critic feedback</div>', unsafe_allow_html=True)
            st.markdown(r["critic"])

st.markdown(
    '<div class="notice">ResearchMind · LangChain multi-agent pipeline · Streamlit</div>',
    unsafe_allow_html=True,
)
