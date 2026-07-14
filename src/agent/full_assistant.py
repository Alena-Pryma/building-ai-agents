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

    # Waiting for second yes (should not usually happen, but keep safe)
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
        msg = _delete_file_impl(args["path"])
        return msg, {"deleted_file": args["path"]}

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
    if not p.exists():
        return f"File not found: {path}"
    p.unlink()
    return f"Deleted {path}"


# Tool functions exposed to the agent (read/search are direct; write/delete are wrapped)

def read_file(path: str) -> str:
    return _read_file_impl(path)


def search_files(pattern: str) -> list[str]:
    return _search_files_impl(pattern)


def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
    # DO NOT write here; always enforce double confirm via deps state
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
    "Only output code when the user explicitly asks for code or debugging.\n"
    "You may use tools to read, search, write, and delete files.\n"
    "Reading and searching files are always allowed.\n"
    "Never create, write, overwrite, or delete files without the user's explicit permission.\n"
    "Before any file modification or deletion, ask the user for confirmation.\n"
    "Proceed only after the user confirms the operation twice with a clear affirmative response.\n"
    "If the user does not provide two explicit confirmations, do not call write_file or delete_file.\n"
    "Always check whether the user's request matches one of the available skills. "
    "If it does, use the load_skill tool to load the skill before answering.\n"
    "Do not assume the contents of a skill file without loading it first.\n"
)


def choose_model(user_text: str) -> str:
    t = (user_text or "").lower()

    hard = (
        "design", "architecture", "refactor", "complex", "сложно", "сложный",
        "пошагово", "deep", "prove", "доказ", "edge case", "production",
        "security", "perf", "оптимизац", "debug", "stack trace", "traceback",
        "tool", "files", "read_file", "write_file", "delete_file", "search_files",
    )

    medium = (
        "python", "sql", "regex", "api", "pydantic", "class", "function",
        "переведи", "translate", "rewrite", "email", "письмо", "cv", "bewerbung",
    )

    if any(k in t for k in hard) or len(t) > 1000:
        return os.environ["ROUTER_MODEL_TOOLS_HEAVY"]

    if any(k in t for k in medium) or len(t) > 400:
        return os.environ["ROUTER_MODEL_TOOLS_MEDIUM"]

    return os.environ["ROUTER_MODEL_TOOLS_LIGHT"]


def run_full(user_input: str, deps: AgentDeps, message_history=None):
    load_dotenv()

    provider = OpenAIProvider(
        base_url=os.environ["ROUTER_BASE_URL"],
        api_key=os.environ["ROUTER_API_KEY"],
    )

    selected = choose_model(user_input)
    model = OpenAIChatModel(model_name=selected, provider=provider)

    agent = Agent(
        model=model,
        instructions=FULL_INSTRUCTIONS,
        deps_type=AgentDeps,
        capabilities=[FileOperations(), ReasoningEffort(), Skills()],
    )

    # Handle pending confirmations BEFORE model call
    confirm_msg, file_meta = _handle_confirmations(user_input, deps)
    if confirm_msg is not None:
        meta = {"model": selected, "input_tokens": "-", "output_tokens": "-"}
        if file_meta:
            meta.update(file_meta)
        return confirm_msg, message_history, meta

    # Optional: start confirmation flow if user asks directly (without tool call)
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