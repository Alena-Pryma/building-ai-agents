from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import frontmatter
from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset

PROJECT_ROOT = Path(".").resolve()

YES = {"yes", "y", "да", "ага", "ok", "okay", "ок"}
NO = {"no", "n", "нет", "nope"}

# --------- Deps for hooks / logging ---------

@dataclass
class AgentDeps:
    console: Console
    pending_op: dict[str, Any] | None = None
    confirm_count: int = 0

# --------- Path safety ---------

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

# --------- Double confirmation flow ---------

def _require_double_confirm(
    deps: AgentDeps,
    op: str,
    args: dict[str, Any],
    lang: str = "ru",
) -> str | None:
    """
    Returns:
      - None if operation is allowed now
      - str message to user if blocked (needs confirmations / reset)
    """
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
            if lang == "en":
                return f"Do you want to delete the file `{path}`? Please confirm (1/2): yes or no."
            return f"Вы хотите удалить файл `{path}`? Подтвердите (1/2): да/yes или нет/no."

        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            if lang == "en":
                return (
                    f"Do you want to create/overwrite the file `{path}` ({n} characters)? "
                    f"Please confirm (1/2): yes or no."
                )
            return (
                f"Вы хотите создать/перезаписать файл `{path}` ({n} символов)? "
                f"Подтвердите (1/2): да/yes или нет/no."
            )

        if lang == "en":
            return f"Do you want to perform the operation `{op}`? Please confirm (1/2): yes or no."
        return f"Подтвердите действие `{op}` (1/2): да/yes или нет/no."

    # Same op: ask second confirm (2/2)
    if deps.confirm_count == 0:
        if op == "delete_file":
            path = args.get("path", "")
            if lang == "en":
                return f"Do you want to delete the file `{path}`? Please confirm (2/2): yes or no."
            return f"Подтвердите удаление `{path}` ещё раз (2/2): да/yes или нет/no."

        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            if lang == "en":
                return (
                    f"Do you want to create/overwrite the file `{path}` ({n} characters)? "
                    f"Please confirm (2/2): yes or no."
                )
            return f"Подтвердите запись `{path}` ({n} символов) ещё раз (2/2): да/yes или нет/no."

        if lang == "en":
            return f"Do you want to perform the operation `{op}`? Please confirm (2/2): yes or no."
        return f"Подтвердите действие `{op}` ещё раз (2/2): да/yes или нет/no."

    # Second confirmation
    if deps.confirm_count < 2:
        if lang == "en":
            return "Awaiting confirmation (2/2): yes or no."
        return "Ожидаю подтверждение (2/2): да/yes или нет/no."

    # Already confirmed twice
    return None

def _handle_confirmations(user_input: str, deps: AgentDeps) -> tuple[str | None, dict[str, Any] | None]:
    """
    If user answers yes/no while an operation is pending:
      - returns (message_to_user, file_meta) and clears pending state
    Otherwise returns (None, None).
    """
    t = " ".join((user_input or "").lower().split())
    if deps.pending_op is None or t not in (YES | NO):
        return None, None

    if t in NO:
        deps.pending_op = None
        deps.confirm_count = 0
        return "Cancelled.", None

    deps.confirm_count += 1
    if deps.confirm_count < 2:
        return "Noted. One more confirmation needed (yes/да).", None

    op = deps.pending_op["op"]
    args = deps.pending_op["args"]
    deps.pending_op = None
    deps.confirm_count = 0

    if op == "write_file":
        msg = _write_file_impl(args["path"], args.get("content", ""))
        return msg, {"created_file": args["path"]}

    if op == "delete_file":
        out = _delete_file_impl(args["path"])
        if out.startswith("Deleted "):
            deps.last_meta = {"deleted_file": args["path"]}
        else:
            deps.last_meta = {"delete_error": out}
        return out

    return "Unknown pending operation.", None

# --------- Tools (safe impl) ---------

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
    abs_path = str(p.resolve())
    try:
        exists = p.exists()
    except Exception as e:
        return f"ERROR checking file {abs_path}: {e}"
    if not exists:
        return f"File not found: {abs_path}"
    try:
        print(f"Deleting file: {abs_path}")
        p.unlink()
    except Exception as e:
        return f"ERROR deleting {abs_path}: {e}"
    if p.exists():
        return f"ERROR deleting {abs_path}: file still exists after unlink."
    return f"Deleted {abs_path}"

# ----- Tool functions (read/search are direct; write/delete are wrapped) -----

def read_file(path: str) -> str:
    return _read_file_impl(path)

def search_files(pattern: str) -> list[str]:
    return _search_files_impl(pattern)

def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
    msg = _require_double_confirm(ctx.deps, "write_file", {"path": path, "content": content}, lang="ru")
    return msg if msg is not None else _write_file_impl(path, content)

def delete_file(ctx: RunContext[AgentDeps], path: str) -> str:
    msg = _require_double_confirm(ctx.deps, "delete_file", {"path": path}, lang="ru")
    return msg if msg is not None else _delete_file_impl(path)

# --------- Capability: File operations + hook ---------

class FileOperations(AbstractCapability[AgentDeps]):
    def get_toolset(self) -> FunctionToolset:
        toolset = FunctionToolset()
        toolset.add_function(read_file)
        toolset.add_function(search_files)
        toolset.add_function(write_file)
        toolset.add_function(delete_file)
        return toolset

    async def before_tool_execute(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        ctx.deps.console.print(f"[tool] Calling tool: {call.tool_name}")
        return args

# --------- Capability: Reasoning effort ---------

class ReasoningEffort(AbstractCapability[Any]):
    LOW_KEYWORDS = {
        "simple", "easy", "quick", "fast", "short", "brief", "concise", "simply",
        "main", "primary", "basic", "fundamental", "quickly", "briefly", "clearly",
        "essential", "core", "shortly", "main point", "key", "precisely", "to the point",
        "просто", "легко", "быстро", "кратко", "коротко", "сжато", "четко", "основное",
        "основной", "основная", "основные", "главное", "главная", "главные", "основы",
        "краткий", "краткая", "по сути", "вкратце", "в двух словах",
    }

    HIGH_KEYWORDS = {
        "hard", "complex", "difficult", "challenging", "complicated",
        "deep", "prove", "detailed", "thoroughly",
        "explain", "explanation", "in detail", "step by step",
        "сложно", "сложный", "трудно", "тяжело", "подробно", "детально",
        "тщательно", "объясни", "объяснение", "шаг за шагом", "пошагово",
    }

    def get_model_settings(self) -> Callable[[RunContext[Any]], ModelSettings]:
        def _set_reasoning_effort(ctx: RunContext[Any]) -> ModelSettings:
            prompt = (ctx.prompt or "").lower()

            if any(k in prompt for k in self.LOW_KEYWORDS):
                thinking = "low"
            elif any(k in prompt for k in self.HIGH_KEYWORDS):
                thinking = "high"
            else:
                thinking = "medium"

            return ModelSettings(thinking=thinking)

        return _set_reasoning_effort

# --------- Capability: Skills ---------

def load_skill(filename: str, skills_dir: str = "skills") -> str:
    p = Path(skills_dir) / filename
    if not p.exists():
        return f"ERROR: skill not found: {p}"
    return p.read_text(encoding="utf-8")

class Skills(AbstractCapability[Any]):
    def get_toolset(self) -> FunctionToolset:
        toolset = FunctionToolset()
        toolset.add_function(load_skill)
        return toolset

    def get_instructions(self) -> str:
        skills_dir = Path("skills")
        if not skills_dir.exists():
            return "Available skills:\n(none)\n"

        md_files = sorted(p for p in skills_dir.glob("*.md") if p.is_file())
        if not md_files:
            return "Available skills:\n(none)\n"

        lines = ["Available skills:"]
        for f in md_files:
            skill = frontmatter.load(f)
            name = skill.metadata.get("name") or f.stem
            desc = skill.metadata.get("description") or ""
            lines.append(f"- {f.name}: {name} — {desc}".rstrip())
        return "\n".join(lines) + "\n"

# --------- Full assistant ---------

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
    "DELETE FILE (VERY IMPORTANT):\n"
    "- NEVER use write_file when the user wants to delete a file.\n"
    "- To delete, always call:\n"
    "  TOOL delete_file path=<exact_filename_or_path>\n"
    "  Example: TOOL delete_file path=demo.txt\n"
    "- You may first call search_files to find the exact path, then call delete_file with that path.\n"
    "\n"
    "FINAL ANSWER:\n"
    "  FINAL <text>\n"
)

def choose_model(user_text: str, message_history=None) -> str:
    t = (user_text or "").lower()

    hard = (
        "design", "architecture", "refactor", "complex", "сложно", "сложный",
        "пошагово", "deep", "prove", "доказ", "edge case", "production", "точно", "детально",
        "security", "perf", "оптимизируй", "optimize", "analyse", "debug", "stack trace", "traceback",
        "tool", "files", "read_file", "write_file", "delete_file", "search_files", "research"
    )

    medium = (
        "python", "sql", "regex", "api", "pydantic", "class", "function", "code",
        "переведи", "translate", "rewrite", "email", "письмо", "cv", "bewerbung",
        "заявка", "запрос", "документ", "официальний", "официально"
    )

    total_len = len(FULL_INSTRUCTIONS) + len(t)
    
    if message_history:
        try:
            for m in message_history:
                if isinstance(m, dict):
                    c = m.get("content", "")
                else:
                    c = str(m)
                total_len += len(str(c))
        except Exception:
            pass
    
    if any(k in t for k in hard) or total_len > 4000:
        return os.environ["ROUTER_MODEL_TOOLS_HEAVY"]

    if any(k in t for k in medium) or total_len > 2000:
        return os.environ["ROUTER_MODEL_TOOLS_MEDIUM"]

    return os.environ["ROUTER_MODEL_TOOLS_LIGHT"]

def run_full(user_input: str, deps: AgentDeps, message_history=None):
    load_dotenv()

    provider = OpenAIProvider(
        base_url=os.environ["ROUTER_BASE_URL"],
        api_key=os.environ["ROUTER_API_KEY"],
    )

    selected = choose_model(user_input, message_history)
    model = OpenAIChatModel(model_name=selected, provider=provider)
    deps.console.print(f"[router] selected model: {selected}")

    agent = Agent(
        model=model,
        instructions=FULL_INSTRUCTIONS,
        deps_type=AgentDeps,
        capabilities=[FileOperations(), ReasoningEffort(), Skills()],
    )

    # Handle pending confirmations before model call
    confirm_msg, file_meta = _handle_confirmations(user_input, deps)
    if confirm_msg is not None:
        meta = {"model": selected, "input_tokens": "-", "output_tokens": "-"}
        if file_meta:
            meta.update(file_meta)
        return confirm_msg, message_history, meta

    # Start confirmation flow if user asks directly (without tool call)
    text = (user_input or "").strip()
    lower = text.lower()

    if any(k in lower for k in ["удали файл", "удалить файл", "delete file", "remove file"]):
        if "файл" in lower:
            path = text.split("файл", 1)[1].strip()
        else:
            path = text.split("file", 1)[1].strip()
        if "." not in Path(path).name:
            path = path + ".txt"
        lang = "en" if ("delete file" in lower or "remove file" in lower) else "ru"
        msg = _require_double_confirm(deps, "delete_file", {"path": path}, lang=lang)
        meta = {"model": selected, "input_tokens": "-", "output_tokens": "-"}
        return msg or "Awaiting confirmation.", message_history, meta

    if any(k in lower for k in ["создай файл", "создать файл", "create file", "write file", "overwrite file"]):
        if "файл" in lower:
            tail = text.split("файл", 1)[1].strip()
        else:
            tail = text.split("file", 1)[1].strip()
        parts = tail.split("с текстом", 1)
        if len(parts) == 1:
            parts = tail.split("with text", 1)
        path = parts[0].strip()
        if "." not in Path(path).name:
            path = path + ".txt"
        content = parts[1].strip() if len(parts) > 1 else ""
        lang = "en" if ("create file" in lower or "write file" in lower or "overwrite file" in lower) else "ru"
        msg = _require_double_confirm(deps, "write_file", {"path": path, "content": content}, lang=lang)
        meta = {"model": selected, "input_tokens": "-", "output_tokens": "-"}
        return msg or "Awaiting confirmation.", message_history, meta

    result = agent.run_sync(user_input, deps=deps, message_history=message_history)

    usage = result.usage
    in_tok = getattr(usage, "input_tokens", None)
    out_tok = getattr(usage, "output_tokens", None)

    meta = {"model": selected, "input_tokens": in_tok, "output_tokens": out_tok}
    return result.output, result.all_messages(), meta

def main() -> None:
    console = Console()
    deps = AgentDeps(console=console)
    message_history = None

    while True:
        user_input = console.input(">> ").strip()
        if user_input.lower() in {
            "exit", "quit", "close", "stop", "end",
            "пока", "выход", "закрыть", "стоп", "конец",
        }:
            return

        output, message_history, _meta = run_full(user_input, deps, message_history)
        console.print(output)

if __name__ == "__main__":
    main()
