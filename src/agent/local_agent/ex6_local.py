from __future__ import annotations

from pathlib import Path

import frontmatter
from rich.console import Console
from ollama import chat

console = Console()
MODEL = "qwen2.5-coder:7b"

BASE_SYSTEM = (
    "You are a Python coding assistant. "
    "Always check whether the user's request matches one of the available skills. "
    "If it does, use the load_skill tool to load the skill before answering. "
    "Do not assume the contents of a skill file without loading it first. "
    "If no relevant skill is available, answer normally."
)

def list_skills(skills_dir: str = "skills") -> list[Path]:
    d = Path(skills_dir)
    if not d.exists():
        return []
    return sorted([p for p in d.glob("*.md") if p.is_file()])

def skills_instruction_block(skills_dir: str = "skills") -> str:
    files = list_skills(skills_dir)
    if not files:
        return "Available skills: (none found)\n"

    lines = ["Available skills:"]
    for f in files:
        skill = frontmatter.load(f)
        name = skill.metadata.get("name") or f.stem
        desc = skill.metadata.get("description") or ""
        lines.append(f"- {f.name}: {name} — {desc}".rstrip())
    return "\n".join(lines) + "\n"

def load_skill_text(filename: str, skills_dir: str = "skills") -> str:
    p = Path(skills_dir) / filename
    return p.read_text(encoding="utf-8")

def run_ex6_local(user_text: str, history):
    if history is None:
        skills_block = skills_instruction_block()
        system = BASE_SYSTEM + "\n\n" + skills_block
        history = [{"role": "system", "content": system}]

    user_text = (user_text or "").strip()

    # keep the same /load behavior (web can type it too)
    if user_text.startswith("/load "):
        filename = user_text.split(" ", 1)[1].strip()
        skill_md = load_skill_text(filename)
        history.append({"role": "user", "content": f"Loaded skill file {filename}:\n\n{skill_md}"})
        meta = {"model": MODEL, "input_tokens": "—", "output_tokens": "—"}
        return f"(loaded {filename})", history, meta

    history.append({"role": "user", "content": user_text})
    resp = chat(model=MODEL, messages=history)
    assistant = resp["message"]["content"]
    history.append({"role": "assistant", "content": assistant})

    meta = {
        "model": MODEL,
        "input_tokens": resp.get("prompt_eval_count", "—"),
        "output_tokens": resp.get("eval_count", "—"),
    }
    return assistant, history, meta

def main() -> None:
    console.print("Exercise 6 local. Type 'exit' to quit.")

    skills_block = skills_instruction_block()
    system = BASE_SYSTEM + "\n\n" + skills_block

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    while True:
        user = console.input(">> ").strip()
        if user.lower() in {"exit", "quit"}:
            return

        # Simple manual "skill loading" command
        if user.startswith("/load "):
            filename = user.split(" ", 1)[1].strip()
            skill_md = load_skill_text(filename)
            messages.append({"role": "user", "content": f"Loaded skill file {filename}:\n\n{skill_md}"})
            console.print(f"(loaded {filename})")
            continue

        messages.append({"role": "user", "content": user})
        resp = chat(model=MODEL, messages=messages)
        assistant = resp["message"]["content"]
        messages.append({"role": "assistant", "content": assistant})
        console.print(assistant)

if __name__ == "__main__":
    main()