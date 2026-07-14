from __future__ import annotations

from pathlib import Path

from rich.console import Console
from ollama import chat

console = Console()
MODEL = "qwen2.5-coder:7b"

SYSTEM = """You are a coding assistant with file tools.

If you need a tool, output ONE line:
TOOL <name> key=value key=value

Tools:
- TOOL read_file path=...
- TOOL search_files pattern=**/*.py
- TOOL write_file path=...   (then next message: content between CONTENT_BEGIN/CONTENT_END)
- TOOL delete_file path=...

For write_file content, use:
CONTENT_BEGIN
...text...
CONTENT_END

When finished, output:
FINAL: <text>
"""

def read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    return p.read_text(encoding="utf-8")

def write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"OK: wrote {len(content)} chars to {path}"

def search_files(pattern: str) -> list[str]:
    return [str(p) for p in Path(".").glob(pattern) if p.is_file()]

def delete_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    p.unlink()
    return f"OK: deleted {path}"

TOOLS = {
    "read_file": lambda args: read_file(args["path"]),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "search_files": lambda args: search_files(args["pattern"]),
    "delete_file": lambda args: delete_file(args["path"]),
}

def _parse_tool_line(text: str):
    t = (text or "").strip()
    if not t.startswith("TOOL "):
        return None
    parts = t.split()
    if len(parts) < 2:
        return None
    name = parts[1].strip()
    args = {}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            args[k.strip()] = v.strip()
    return name, args

def _extract_content_block(text: str) -> str | None:
    a = (text or "").find("CONTENT_BEGIN")
    b = (text or "").find("CONTENT_END")
    if a == -1 or b == -1 or b <= a:
        return None
    return (text[a+len("CONTENT_BEGIN"):b]).strip("\n")

def run_ex3_local(user_text: str, history):
    if history is None:
        history = [{"role": "system", "content": SYSTEM}]

    user_text = (user_text or "").strip()
    lower = user_text.lower()

    is_list_request = any(
        k in lower for k in [
            "show all", "list", "find all", "all python files", ".py", ".md",
            "покажи", "найди", "список", "все", "файлы"
        ]
    )

    if is_list_request:
        # decide pattern
        if ".md" in lower or "markdown" in lower:
            pattern = "**/*.md"
        elif ".py" in lower or "python" in lower:
            pattern = "**/*.py"
        else:
            pattern = "**/*"

        files = search_files(pattern)
        text = "\n".join(f"- {p}" for p in files)
        meta = {"model": MODEL, "input_tokens": "—", "output_tokens": "—"}
        return f"Found {len(files)} files:\n\n{text}", history, meta
    history.append({"role": "user", "content": user_text})

    pending_write_path = None

    for _ in range(10):
        resp = chat(model=MODEL, messages=history)
        assistant = (resp["message"]["content"] or "").strip()

        meta = {
            "model": MODEL,
            "input_tokens": resp.get("prompt_eval_count", "—"),
            "output_tokens": resp.get("eval_count", "—"),
        }

        history.append({"role": "assistant", "content": assistant})

        # waiting for write content
        if pending_write_path:
            content = _extract_content_block(assistant)
            if content is None:
                history.append({"role": "user", "content": "Provide content ONLY between CONTENT_BEGIN and CONTENT_END."})
                continue
            tool_result = write_file(pending_write_path, content)
            pending_write_path = None
            history.append({"role": "user", "content": f"Tool result: {tool_result}"})
            continue

        # final
        if assistant.startswith("FINAL:"):
            return assistant.removeprefix("FINAL:").strip(), history, meta

        tool = _parse_tool_line(assistant)
        if tool is None:
            # treat as final text if model didn't follow protocol
            return assistant, history, meta

        name, args = tool

        try:
            if name == "read_file":
                tool_result = read_file(args["path"])
            elif name == "search_files":
                tool_result = search_files(args.get("pattern", "**/*"))
            elif name == "delete_file":
                tool_result = delete_file(args["path"])
            elif name == "write_file":
                pending_write_path = args.get("path")
                tool_result = f"OK. Now provide content between CONTENT_BEGIN and CONTENT_END for {pending_write_path}."
            else:
                tool_result = f"ERROR: unknown tool {name}"
        except Exception as e:
            tool_result = f"ERROR: {type(e).__name__}: {e}"

        history.append({"role": "user", "content": f"Tool result: {tool_result}"})

    return "Stopped (tool loop limit reached).", history, {"model": MODEL, "input_tokens": "—", "output_tokens": "—"}

def main() -> None:
    console.print("Exercise 3 local (TOOLS). Type 'exit' to quit.")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]

    while True:
        user = console.input(">> ").strip()
        if user.lower() in {"exit", "quit"}:
            return

        messages.append({"role": "user", "content": user})

        pending_write_path = None

        for _ in range(10):
            resp = chat(model=MODEL, messages=messages)
            assistant = (resp["message"]["content"] or "").strip()
            messages.append({"role": "assistant", "content": assistant})

            if pending_write_path:
                content = _extract_content_block(assistant)
                if content is None:
                    messages.append({"role": "user", "content": "Provide content ONLY between CONTENT_BEGIN and CONTENT_END."})
                    continue
                tool_result = write_file(pending_write_path, content)
                pending_write_path = None
                messages.append({"role": "user", "content": f"Tool result: {tool_result}"})
                continue

            if assistant.startswith("FINAL:"):
                console.print(assistant.removeprefix("FINAL:").strip())
                break

            tool = _parse_tool_line(assistant)
            if tool is None:
                console.print(assistant)
                break

            name, args = tool
            try:
                if name == "read_file":
                    tool_result = read_file(args["path"])
                elif name == "search_files":
                    tool_result = search_files(args.get("pattern", "**/*"))
                elif name == "delete_file":
                    tool_result = delete_file(args["path"])
                elif name == "write_file":
                    pending_write_path = args.get("path")
                    tool_result = f"OK. Now provide content between CONTENT_BEGIN and CONTENT_END for {pending_write_path}."
                else:
                    tool_result = f"ERROR: unknown tool {name}"
            except Exception as e:
                tool_result = f"ERROR: {type(e).__name__}: {e}"

            messages.append({"role": "user", "content": f"Tool result: {tool_result}"})

if __name__ == "__main__":
    main()