import os
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

load_dotenv()

# ─────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

nvidia_openai_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_OPENAI_API_KEY")
)

# ─────────────────────────────────────────
# MODELS
# model_name → (provider, model_id)
# ─────────────────────────────────────────

MODELS = {
    "llama-3":  ("groq",          "llama-3.3-70b-versatile"),
    "nemotron": ("nvidia",        "nvidia/llama-3.1-nemotron-nano-8b-v1"),
    "gpt-oss":  ("nvidia-openai", "openai/gpt-oss-20b"),
}


def ask_model(model_name, question, system_prompt="You are a helpful assistant."):
    """
    model_name = key from MODELS dict, e.g. "llama-3"
    question   = what to ask
    system_prompt = behavior instructions

    Returns: string, the model's answer
    """
    provider, model_id = MODELS[model_name]

    try:
        if provider == "groq":
            response = groq_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": question}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content

        elif provider == "nvidia":
            # Nemotron — streaming with reasoning_content support
            completion = nvidia_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": question}
                ],
                temperature=0,
                top_p=0.95,
                max_tokens=1000,
                stream=True
            )
            result = ""
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    result += reasoning
                if delta.content is not None:
                    result += delta.content
            return result

        elif provider == "nvidia-openai":
            # GPT-OSS — streaming
            completion = nvidia_openai_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": question}
                ],
                temperature=1,
                top_p=1,
                max_tokens=1000,
                stream=True
            )
            result = ""
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    result += reasoning
                if delta.content is not None:
                    result += delta.content
            return result

    except Exception as exc:
        error_message = str(exc)
        if "model_not_found" in error_message or "does not exist" in error_message:
            return f"[Unavailable model: {model_id}]"
        raise


def run_debate(question):
    """
    Asks every model in MODELS the same question.
    Returns: {model_name: answer_text}
    """
    answers = {}

    for name in MODELS:
        print(f"🤖 Asking {name}...")
        answers[name] = ask_model(name, question)
        print(f"✅ {name} responded!")

    return answers


if __name__ == "__main__":
    q = "Explain Python list comprehensions with 3 examples."
    results = run_debate(q)

    for model, answer in results.items():
        print(f"\n{'='*60}")
        print(f"🧠 MODEL: {model}")
        print(f"{'='*60}")
        print(answer[:400] + "...")