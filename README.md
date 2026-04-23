# ⚖️ Jurex - Multi-LLM Debate Arena

> **Same prompt → three AI models debate each other → a fourth LLM judges the winner.**  
> Built to explore how different language models reason, argue, and compare on identical questions.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203-orange)
![NVIDIA NIM](https://img.shields.io/badge/NVIDIA%20NIM-Nemotron%20%7C%20GPT--OSS-76b900?logo=nvidia&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🧠 What Is Jurex?

Jurex is an **AI debate arena** — you type one question and three state-of-the-art LLMs answer it independently. A fourth model then **judges and ranks** their responses using a structured rubric, outputting scores, strengths, weaknesses, and a verdict for each. ELO ratings accumulate across debates to track which model performs best over time.

**The name** comes from *"Jury"* + *"Apex"* — the apex jury of AI models.

---

## 🏗️ Architecture

```
User Question
      │
      ▼
┌─────────────────────────────────────────┐
│               debate.py                 │
│                                         │
│  llama-3    ──► Groq API               │
│  nemotron   ──► NVIDIA NIM             │
│  gpt-oss    ──► NVIDIA NIM             │
└──────────────────┬──────────────────────┘
                   │  3 answers
                   ▼
┌─────────────────────────────────────────┐
│               judge.py                  │
│                                         │
│  llama-3 (Groq) evaluates all 3        │
│  → ranks by correctness, clarity,      │
│    completeness, conciseness           │
└──────────────────┬──────────────────────┘
                   │  JSON verdict
                   ▼
┌─────────────────────────────────────────┐
│               elo.py                    │
│  ELO ratings update based on rank      │
│  (same formula as competitive chess)   │
└─────────────────────────────────────────┘
                   │
                   ▼
           Streamlit UI (app.py)
```

---

## 🤖 Models Used

| Alias | Model ID | Provider |
|---|---|---|
| `llama-3` | `llama-3.3-70b-versatile` | 🟢 Groq |
| `nemotron` | `nvidia/llama-3.1-nemotron-nano-8b-v1` | 🔵 NVIDIA NIM |
| `gpt-oss` | `openai/gpt-oss-20b` | 🔴 NVIDIA NIM |
| **Judge** | `llama-3.3-70b-versatile` | 🟢 Groq |

---

## ✨ Features

- 🗣️ **Multi-model debate** — Three LLMs answer the same question simultaneously
- 🧑‍⚖️ **Structured judging** — The judge scores each answer on correctness, clarity, completeness, and conciseness
- 📊 **ELO leaderboard** — Chess-style ratings track model performance across debates
- 🌀 **Streaming responses** — NVIDIA models stream output in real-time
- 🔒 **Secure config** — API keys loaded from `.env`, never hardcoded
- 📜 **Debate history** — Every debate is saved and reviewable in-session

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Senaaravichandran/jurex.git
cd jurex
```

### 2. Create a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up API keys
```bash
cp .env.example .env
```
Then open `.env` and fill in your keys:

| Key | Where to get it |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `NVIDIA_API_KEY` | [build.nvidia.com](https://build.nvidia.com) |
| `NVIDIA_OPENAI_API_KEY` | [build.nvidia.com](https://build.nvidia.com) |

### 5. Run the app
```bash
streamlit run app.py
```

---

## 📁 Project Structure

```
jurex/
├── app.py            # Streamlit UI — main entry point
├── debate.py         # Multi-provider model routing + debate logic
├── judge.py          # Judge prompt engineering + evaluation
├── elo.py            # ELO rating system
├── parse_judge.py    # Robust JSON extraction from LLM output
├── requirements.txt  # Python dependencies
├── .env.example      # API key template
├── .gitignore
│
└── test_groq.py           # Groq API sanity check
└── test_nvidia_llama.py   # NVIDIA Nemotron sanity check
└── test_nvidia_openai.py  # NVIDIA GPT-OSS sanity check
```

---

## 🛠️ Tech Stack

- **[Streamlit](https://streamlit.io/)** — Interactive web UI with zero frontend boilerplate
- **[Groq](https://groq.com/)** — Ultra-fast LLaMA 3 inference (used for debater + judge)
- **[NVIDIA NIM](https://build.nvidia.com/)** — Access to Nemotron and GPT-OSS via OpenAI-compatible API
- **[OpenAI Python SDK](https://github.com/openai/openai-python)** — Used as a universal client for NVIDIA NIM endpoints
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Secure environment variable management

---

## 💡 How the Judge Works

The judge (LLaMA 3 via Groq) receives all three answers and evaluates them on a rubric:

1. **Correctness** — Is the answer factually accurate?
2. **Clarity** — Is it well-structured and easy to follow?
3. **Completeness** — Does it cover all important aspects?
4. **Conciseness** — No fluff, appropriately scoped?

It outputs structured JSON with ranks, scores (0–100), strengths, weaknesses, and a one-sentence verdict per model.

---

## 📈 ELO Rating System

Borrowed from competitive chess — models start at **1500 ELO**. After each debate:
- The 1st-place model gains points from the 2nd-place model
- The 2nd-place model gains points from the 3rd-place model
- The magnitude of change depends on how surprising the outcome was

This lets you track which model consistently produces better answers over time.

---

## 🔮 Future Ideas

- [ ] Add more models (Gemini, Claude, Mistral)
- [ ] Persist ELO ratings to a database across sessions
- [ ] Export debate history as PDF / Markdown
- [ ] Side-by-side diff view of answers
- [ ] Graph ELO trends over time

---

## 👤 Author

**Sena** — built as a personal project to compare frontier LLMs in a structured, reproducible way.  
Feel free to open issues or PRs!

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
