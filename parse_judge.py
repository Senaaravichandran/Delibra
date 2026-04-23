import json
import re


def extract_json(text):
    """
    LLMs sometimes wrap JSON in markdown: ```json {...} ```
    Or add explanatory text. This extracts clean JSON.

    Returns a dict. Falls back to a safe default if no JSON found,
    so the app never crashes on malformed judge output.
    """

    # Try greedy match: find outermost { ... }
    match = re.search(r'\{.*\}', text, re.DOTALL)

    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Fallback: return a safe default so the app keeps running
    print(f"⚠️  Warning: Could not parse JSON from judge output. Raw:\n{text[:300]}")
    return {
        "rankings": [],
        "reasoning": "Could not parse judge output."
    }


if __name__ == "__main__":
    dirty_json = """Here is my evaluation:
```json
{"rankings": [{"model": "llama-3", "rank": 1, "score": 90, "verdict": "Best answer."}], "reasoning": "Clear and complete."}
```
"""
    result = extract_json(dirty_json)
    print(result)