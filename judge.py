from debate import ask_model  # Reuse routing logic

# ─────────────────────────────────────────
# JUDGE PROMPT ENGINEERING
# ─────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator of AI responses.

Your task: Compare 3 answers to the same question and rank them from BEST to WORST.

Evaluation criteria (in order of importance):
1. CORRECTNESS: Is the answer factually accurate?
2. CLARITY: Is it easy to understand? Well-structured?
3. COMPLETENESS: Does it cover all important aspects?
4. CONCISENESS: Is it appropriately brief? No fluff?

For each answer, provide:
- Rank (1st, 2nd, 3rd)
- Score (0-100)
- Strengths (2 bullet points)
- Weaknesses (2 bullet points)
- One-sentence verdict

Format your response as JSON:
{
    "rankings": [
        {"model": "name", "rank": 1, "score": 95, "verdict": "..."},
        ...
    ],
    "reasoning": "Why you ranked them this way"
}
"""


def judge_debate(question, answers_dict):
    """
    answers_dict = {"llama-3": "...", "nemotron": "...", "gpt-oss": "..."}
    Returns: raw string from judge (JSON expected)
    """

    # Build the formatted prompt with all 3 answers
    sections = []
    for i, (model_name, answer) in enumerate(answers_dict.items(), start=1):
        sections.append(f"--- ANSWER {i} ({model_name}) ---\n{answer}")

    judge_prompt = f"Question: {question}\n\n" + "\n\n".join(sections) + \
        "\n\nNow evaluate and rank all 3 answers. Return valid JSON only."

    # llama-3 via Groq acts as judge — reliable and fast
    raw_judgment = ask_model(
        "llama-3",
        judge_prompt,
        system_prompt=JUDGE_SYSTEM_PROMPT
    )

    return raw_judgment


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    test_answers = {
        "llama-3":  "Quicksort is O(n log n) average case...",
        "nemotron": "Quicksort has O(n²) worst case but O(n log n) average...",
        "gpt-oss":  "Quicksort: divide and conquer, O(n log n) average, O(n²) worst..."
    }

    judgment = judge_debate("Explain quicksort time complexity", test_answers)
    print(judgment)