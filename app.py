import streamlit as st
from debate import run_debate, MODELS
from judge import judge_debate
from parse_judge import extract_json
from elo import update_elo

# ─────────────────────────────────────────
# PROVIDER BADGES
# ─────────────────────────────────────────

PROVIDER_LABELS = {
    "groq":          "🟢 Groq",
    "nvidia":        "🔵 NVIDIA NIM",
    "nvidia-openai": "🔴 NVIDIA NIM",
}

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = []

if "ratings" not in st.session_state:
    st.session_state.ratings = {name: 1500 for name in MODELS}

# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────

st.title("⚖️ Jurex")
st.subheader("Same prompt → GPT, LLaMA, Nemotron → they debate → a judge ranks them")

# Model info table
with st.expander("🤖 Competing Models", expanded=False):
    for name, (provider, model_id) in MODELS.items():
        st.markdown(f"**{name}** — `{model_id}` &nbsp; {PROVIDER_LABELS[provider]}")

question = st.text_area(
    "Enter your question:",
    "What is the time complexity of quicksort?"
)

if st.button("🚀 Start Debate"):
    with st.spinner("Models are debating..."):
        # Step 1: Get all answers
        answers = run_debate(question)

        # Step 2: Judge evaluates
        raw_judgment = judge_debate(question, answers)
        judgment = extract_json(raw_judgment)

        # Step 3: Update ELO ratings
        rankings = judgment.get("rankings", [])

        for i in range(len(rankings) - 1):
            winner = rankings[i]["model"]
            loser  = rankings[i + 1]["model"]

            # Guard: only update if both models are in ratings
            if winner in st.session_state.ratings and loser in st.session_state.ratings:
                new_winner, new_loser = update_elo(
                    st.session_state.ratings[winner],
                    st.session_state.ratings[loser]
                )
                st.session_state.ratings[winner] = new_winner
                st.session_state.ratings[loser]  = new_loser

        # Step 4: Save to history
        st.session_state.history.append({
            "question": question,
            "answers":  answers,
            "judgment": judgment
        })

    st.success("Debate complete!")

    # ── Show this debate's verdict immediately ──
    if rankings:
        st.header("🏅 Judge's Verdict")
        for entry in rankings:
            medal = ["🥇", "🥈", "🥉"][entry["rank"] - 1] if entry["rank"] <= 3 else "🎖️"
            st.markdown(
                f"{medal} **{entry['model']}** — Score: `{entry.get('score', 'N/A')}`  \n"
                f"> {entry.get('verdict', '')}"
            )
        st.markdown(f"**Reasoning:** {judgment.get('reasoning', '')}")

# ─────────────────────────────────────────
# RATINGS
# ─────────────────────────────────────────

st.header("🏆 ELO Rankings")

sorted_ratings = sorted(
    st.session_state.ratings.items(),
    key=lambda x: x[1],
    reverse=True
)

cols = st.columns(len(sorted_ratings))
for col, (model, rating) in zip(cols, sorted_ratings):
    provider = MODELS[model][0]
    col.metric(label=f"{PROVIDER_LABELS[provider]}  {model}", value=int(rating))

# ─────────────────────────────────────────
# DEBATE HISTORY
# ─────────────────────────────────────────

if st.session_state.history:
    st.header("📜 Debate History")

    for i, debate in enumerate(reversed(st.session_state.history)):
        with st.expander(f"Debate {len(st.session_state.history) - i}: {debate['question'][:60]}..."):

            # Each model's answer
            for model, answer in debate["answers"].items():
                provider = MODELS[model][0]
                st.markdown(f"**{PROVIDER_LABELS[provider]} — {model}**")
                st.code(answer[:400] + ("..." if len(answer) > 400 else ""))

            # Judgment
            st.markdown("**🧑‍⚖️ Judge's Verdict:**")
            st.json(debate["judgment"])