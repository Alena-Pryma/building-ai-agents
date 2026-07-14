from rich.console import Console
from ollama import chat

#---------Main---------

console = Console()

MODEL = "qwen2.5-coder:7b"
SYSTEM = (
    "You are a Python coding assistant. "
    "Write clear, correct, and minimal Python code."
)
def run_ex1_local(user_text: str):
    user_text = (user_text or "").strip()
    resp = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
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
    user = console.input(">> ").strip()
    resp = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    console.print(resp["message"]["content"])

if __name__ == "__main__":
    main()