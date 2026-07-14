from rich.console import Console
from ollama import chat

console = Console()

MODEL = "qwen2.5-coder:7b"
SYSTEM = (
    "You are a helpful assistant for both coding and text tasks.\n"
    "Only output code when the user explicitly asks for code or debugging.\n"
    "Write clear, correct, and minimal."
    "If the user asks for code (mentions Python/JS/SQL/R or other programming languages, functions, errors, stack traces, files, or requests code), respond with minimal runnable code + a short note.\n"
    "If the user asks for translation or writing, respond with text (no code).\n"
    "If unclear, ask one clarifying question.\n"
)
def run_ex2_local(user_text: str, history):
    if history is None:
        history = [{"role": "system", "content": SYSTEM}]

    user_text = (user_text or "").strip()
    history.append({"role": "user", "content": user_text})

    resp = chat(model=MODEL, messages=history)
    assistant_text = resp["message"]["content"]

    history.append({"role": "assistant", "content": assistant_text})

    meta = {
        "model": MODEL,
        "input_tokens": resp.get("prompt_eval_count", "—"),
        "output_tokens": resp.get("eval_count", "—"),
    }
    return assistant_text, history, meta

def main() -> None:
    messages = [{"role": "system", "content": SYSTEM}]

    while True:
        user_input = console.input(">> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            return

        messages.append({"role": "user", "content": user_input})

        resp = chat(model=MODEL, messages=messages)
        assistant_text = resp["message"]["content"]

        messages.append({"role": "assistant", "content": assistant_text})
        console.print(assistant_text)

if __name__ == "__main__":
    main()