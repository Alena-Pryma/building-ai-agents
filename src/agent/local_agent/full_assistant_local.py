from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from ollama import chat as ollama_chat
from rich.console import Console

MODEL_NAME = "qwen2.5-coder:7b"
PROJECT_ROOT = Path(".").resolve()

YES = {"yes", "y", "да", "ага", "ok", "okay", "ок"}
NO = {"no", "n", "нет", "nope"}


# ---------------- Deps ----------------

@dataclass
class AgentDeps:
    console: Console
    pending_op: dict[str, Any] | None = None
    confirm_count: int = 0
    selected_file: str | None = None
    last_meta: dict[str, Any] | None = None


# ---------------- Helpers: path safety ----------------

def _resolve_in_project(path: str) -> Path | None:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    else:
        p = p.resolve()

    root = str(PROJECT_ROOT)
    ps = str(p)
    if ps == root or ps.startswith(root + "/"):
        return p
    return None


def _normalize_yesno(text: str) -> str:
    t = (text or "").strip().lower()
    t = " ".join(t.split())
    return t


# ---------------- Confirm flow ----------------

def _require_double_confirm(deps: AgentDeps, op: str, args: dict[str, Any]) -> str | None:
    is_new = (
        deps.pending_op is None
        or deps.pending_op.get("op") != op
        or deps.pending_op.get("args") != args
    )
    if is_new:
        deps.pending_op = {"op": op, "args": args}
        deps.confirm_count = 0

        if op == "delete_file":
            path = args.get("path", "")
            return f"Вы хотите удалить файл `{path}`? Подтвердите (1/2): да/yes или нет/no."
        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            return (
                f"Вы хотите создать/перезаписать файл `{path}` ({n} символов)? "
                f"Подтвердите (1/2): да/yes или нет/no."
            )
        return f"Подтвердите действие `{op}` (1/2): да/yes или нет/no."

    if deps.confirm_count == 0:
        if op == "delete_file":
            path = args.get("path", "")
            return f"Подтвердите удаление `{path}` ещё раз (2/2): да/yes или нет/no."
        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            return f"Подтвердите запись `{path}` ({n} символов) ещё раз (2/2): да/yes или нет/no."
        return f"Подтвердите действие `{op}` ещё раз (2/2): да/yes или нет/no."

    if deps.confirm_count < 2:
        return "Ожидаю подтверждение (2/2): да/yes или нет/no."

    return None


def _handle_confirmations(user_input: str, deps: AgentDeps) -> str | None:
    t = _normalize_yesno(user_input)
    if deps.pending_op is None or t not in (YES | NO):
        return None

    if t in NO:
        deps.pending_op = None
        deps.confirm_count = 0
        return "Cancelled."

    deps.confirm_count += 1
    if deps.confirm_count < 2:
        return "Noted. One more confirmation needed (yes/да)."

    op = deps.pending_op["op"]
    args = deps.pending_op["args"]
    deps.pending_op = None
    deps.confirm_count = 0

    if op == "write_file":
        out = _write_file_impl(args["path"], args.get("content", ""))
        deps.last_meta = {"created_file": args["path"]}
        return out

    if op == "delete_file":
        out = _delete_file_impl(args["path"])
        deps.last_meta = {"deleted_file": args["path"]}
        return out

    return "Unknown pending operation."


# ---------------- Tools (impl) ----------------

def _read_file_impl(path: str) -> str:
    p = _resolve_in_project(path)
    if p is None:
        return f"ERROR: refusing to read outside project root: {path}"
    if not p.exists():
        return f"ERROR: file not found: {path}"
    return p.read_text(encoding="utf-8")


def _write_file_impl(path: str, content: str) -> str:
    p = _resolve_in_project(path)
    if p is None:
        return f"ERROR: refusing to write outside project root: {path}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


def _search_files_impl(pattern: str) -> list[str]:
    return [str(p) for p in Path(".").glob(pattern) if p.is_file()]


def _delete_file_impl(path: str) -> str:
    p = _resolve_in_project(path)
    if p is None:
        return f"ERROR: refusing to delete outside project root: {path}"
    if not p.exists():
        return f"File not found: {path}"
    p.unlink()
    return f"Deleted {path}"


def _load_skill_impl(filename: str, skills_dir: str = "skills") -> str:
    p = Path(skills_dir) / filename
    if not p.exists():
        return f"ERROR: skill not found: {p}"
    return p.read_text(encoding="utf-8")


def _read_selected_file_impl(deps: AgentDeps) -> str:
    if not deps.selected_file:
        return "No file selected. Ask the user to upload a file first."
    return _read_file_impl(deps.selected_file)


# ---------------- Skills list for prompt ----------------

def _skills_block(skills_dir: str = "skills") -> str:
    d = Path(skills_dir)
    if not d.exists():
        return "Available skills:\n(none)\n"
    md_files = sorted(p for p in d.glob("*.md") if p.is_file())
    if not md_files:
        return "Available skills:\n(none)\n"
    lines = ["Available skills:"]
    for f in md_files:
        skill = frontmatter.load(f)
        name = skill.metadata.get("name") or f.stem
        desc = skill.metadata.get("description") or ""
        lines.append(f"- {f.name}: {name} — {desc}".rstrip())
    return "\n".join(lines) + "\n"


# ---------------- Parsing: TOOL line + markers ----------------

def _parse_tool_line(text: str) -> tuple[str, dict[str, str]] | None:
    t = (text or "").strip()
    if not t.startswith("TOOL "):
        return None
    parts = t.split()
    if len(parts) < 2:
        return None
    name = parts[1].strip()
    args: dict[str, str] = {}
    for p in parts[2:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        args[k.strip()] = v.strip()
    return name, args


def _extract_content_block(text: str) -> str | None:
    t = text or ""
    a = t.find("CONTENT_BEGIN")
    b = t.find("CONTENT_END")
    if a == -1 or b == -1 or b <= a:
        return None
    return t[a + len("CONTENT_BEGIN") : b].strip("\n")


# ---------------- Prompt ----------------

FULL_INSTRUCTIONS = (
    "You are a helpful assistant for both coding and text tasks.\n"
    "You may use tools: read_file, read_selected_file, search_files, load_skill, write_file, delete_file.\n"
    "Allowed without confirmation: read_file, read_selected_file, search_files, load_skill.\n"
    "write_file/delete_file require explicit user permission and two confirmations.\n"
    "IMPORTANT SAFETY:\n"
    "- Never call write_file/delete_file unless the user explicitly asked to write/delete.\n"
    "- If you think a write/delete is needed, ask first.\n"
    "\n"
    "TOOL CALL FORMAT (NO JSON):\n"
    "- To call a tool, output ONE line:\n"
    "  TOOL <tool_name> key=value key=value\n"
    "  Example: TOOL search_files pattern=**/*.py\n"
    "  Example: TOOL read_file path=README.md\n"
    "  Example: TOOL read_selected_file\n"
    "\n"
    "WRITE FILE WITHOUT JSON:\n"
    "- Step 1: request write:\n"
    "  TOOL write_file path=path/to/file.txt\n"
    "- Step 2: in the next assistant message, output content ONLY between markers:\n"
    "  CONTENT_BEGIN\n"
    "  ...file content...\n"
    "  CONTENT_END\n"
    "\n"
    "FINAL ANSWER:\n"
    "  FINAL <text>\n"
)


# ---------------- Local runner ----------------

def run_full_local(
    user_input: str,
    deps: AgentDeps,
    messages: list[dict[str, str]] | None,
):
    if messages is None:
        messages = []

    # 0) confirmations first (this is the ONLY place where write/delete can actually execute)
    confirm_out = _handle_confirmations(user_input, deps)
    if confirm_out is not None:
        meta = {"model": MODEL_NAME, "input_tokens": "—", "output_tokens": "—"}
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": confirm_out})
        return confirm_out, messages, meta

    system = FULL_INSTRUCTIONS + "\n" + _skills_block()

    convo: list[dict[str, str]] = [{"role": "system", "content": system}]
    convo.extend([m for m in messages if m.get("role") != "system"])
    convo.append({"role": "user", "content": (user_input or "").strip()})

    pending_write_path: str | None = None
    pending_write_content: str | None = None

    for _ in range(20):
        resp = ollama_chat(model=MODEL_NAME, messages=convo, stream=False)
        assistant = (resp["message"]["content"] or "").strip()

        meta = {
            "model": MODEL_NAME,
            "input_tokens": resp.get("prompt_eval_count", "—"),
            "output_tokens": resp.get("eval_count", "—"),
        }
        if deps.last_meta:
            meta.update(deps.last_meta)
            deps.last_meta = None

        # If model is providing content for a previously requested write_file
        if pending_write_path is not None:
            content = _extract_content_block(assistant)
            if content is None:
                convo.append({"role": "assistant", "content": assistant})
                convo.append({"role": "user", "content": "Provide file content ONLY between CONTENT_BEGIN and CONTENT_END."})
                continue

            pending_write_content = content

            # Ask for double confirmation (DO NOT write here)
            msg = _require_double_confirm(
                deps,
                "write_file",
                {"path": pending_write_path, "content": pending_write_content},
            )
            pending_write_path = None
            pending_write_content = None

            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta

        tool = _parse_tool_line(assistant)

        # Not a tool call -> finalize
        if tool is None:
            if assistant.startswith("FINAL"):
                assistant = assistant.split("FINAL", 1)[1].lstrip(":").strip()
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": assistant})
            return assistant, messages, meta

        tool_name, args = tool

        # SAFETY: never execute write/delete directly; always convert into confirmation request
        if tool_name == "delete_file":
            path = args.get("path", "")
            msg = _require_double_confirm(deps, "delete_file", {"path": path})
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta

        if tool_name == "write_file":
            pending_write_path = args.get("path")
            if not pending_write_path:
                result = "Missing path for write_file."
            else:
                result = f"OK. Now provide content between CONTENT_BEGIN and CONTENT_END for {pending_write_path}."
            convo.append({"role": "assistant", "content": assistant})
            convo.append({"role": "user", "content": f"Tool result ({tool_name}): {result}"})
            continue

        # dispatch safe tools
        if tool_name == "search_files":
            result = _search_files_impl(args.get("pattern", "**/*"))
        elif tool_name == "read_file":
            result = _read_file_impl(args.get("path", ""))
        elif tool_name == "read_selected_file":
            result = _read_selected_file_impl(deps)
        elif tool_name == "load_skill":
            result = _load_skill_impl(args.get("filename", ""), args.get("skills_dir", "skills"))
        else:
            result = f"Unknown tool: {tool_name}"

        convo.append({"role": "assistant", "content": assistant})
        convo.append({"role": "user", "content": f"Tool result ({tool_name}): {result}"})

    msg = "Stopped (tool loop limit reached)."
    meta = {"model": MODEL_NAME, "input_tokens": "—", "output_tokens": "—"}
    messages.append({"role": "assistant", "content": msg})
    return msg, messages, meta