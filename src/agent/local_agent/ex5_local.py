from __future__ import annotations

from rich.console import Console
from ollama import chat

console = Console()
MODEL = "qwen2.5-coder:7b"

BASE_SYSTEM = (
    "You are a Python coding assistant. "
    "Answer clearly and concisely. "
    "If the user asks to create/modify/delete files, first ask for explicit confirmation."
)

def pick_effort(user_text: str) -> str:
    t = user_text.lower()
    if any(k in t for k in ["simple", "быстро", "кратко", "short"]):
        return "low"
    if any(k in t for k in ["hard", "сложно", "deep", "prove", "доказ"]):
        return "high"
    return "medium"

def run_ex5_local(user_text: str):
    user_text = (user_text or "").strip()
    effort = pick_effort(user_text)
    system = BASE_SYSTEM + f" Reasoning effort: {effort}."

    resp = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    )
    meta = {
        "model": MODEL,
        "input_tokens": resp.get("prompt_eval_count", "—"),
        "output_tokens": resp.get("eval_count", "—"),
    }
    return resp["message"]["content"], meta

def main() -> None:
    console.print("Exercise 5 local. Type 'exit' to quit.")
    while True:
        user = console.input(">> ").strip()
        if user.lower() in {"exit", "quit"}:
            return

        effort = pick_effort(user)
        system = BASE_SYSTEM + f" Reasoning effort: {effort}."

        resp = chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        console.print(resp["message"]["content"])

if __name__ == "__main__":
    main()