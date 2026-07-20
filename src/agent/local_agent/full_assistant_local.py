from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

import frontmatter
from ollama import chat as ollama_chat
from rich.console import Console

CHAT_MODEL = "llama3.2:3b"
CODE_MODEL = "qwen2.5-coder:7b"
PROJECT_ROOT = Path(".").resolve()

YES = {"yes", "y", "да", "ага", "ok", "okay", "ок", "OK"}
NO = {"no", "n", "нет", "nope"}

LOW_KEYWORDS = {
    "simple", "easy", "quick", "fast", "short", "brief", "concise", "simply",
    "просто", "легко", "быстро", "кратко", "коротко", "сжато", "четко", "вкратце",
}

HIGH_KEYWORDS = {
    "hard", "complex", "difficult", "challenging", "complicated",
    "deep", "prove", "detailed", "thoroughly",
    "explain", "explanation", "in detail", "step by step",
    "сложно", "сложный", "трудно", "подробно", "детально",
    "объясни", "объяснение", "шаг за шагом", "пошагово",
}

# ---------------- Deps ----------------

@dataclass
class AgentDeps:
    console: Console
    pending_op: dict[str, Any] | None = None
    confirm_count: int = 0
    selected_file: str | None = None
    opened_file: str | None = None
    user_context: dict[str, str] = field(default_factory=dict)
    last_meta: dict[str, Any] | None = None
    last_answer: str = ""

# ---------------- Helpers: path safety ----------------

def _resolve_in_project(path: str) -> Path | None:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    return p

def _matches_query(path: Path, raw_query: str) -> bool:
    raw_query = (raw_query or "").strip().strip("\"'` ")
    if not raw_query:
        return False

    query = Path(raw_query).name.lower()
    has_extension = bool(Path(query).suffix)
    name = path.name.lower()
    stem = path.stem.lower()

    if has_extension:
        return query == name
    return query == name or query == stem

def _resolve_path_with_fallback(path: str) -> Path | None:
    raw = (path or "").strip().strip("\"'` ")
    if not raw:
        return None

    p = Path(raw).expanduser()
    if p.is_absolute():
        candidates = [p]
    else:
        candidates = [PROJECT_ROOT / p, Path.cwd() / p, p]

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except OSError:
            continue

    search_roots = [PROJECT_ROOT, Path.cwd(), Path.home(), Path("/Volumes")]
    for root in search_roots:
        try:
            for found in root.rglob("*"):
                if not found.is_file():
                    continue
                if _matches_query(found, raw):
                    return found.resolve()
        except (PermissionError, OSError):
            continue

    return None

def _normalize_yesno(text: str) -> str:
    t = (text or "").strip().lower()
    t = " ".join(t.split())
    return t

# ---------------- File's formats auto ----------------

def _guess_extension_from_content(text: str) -> str:
    t = (text or "").lstrip()
    low = t.lower()

    # Office / Tables
    if "\t" in t and len(t.splitlines()) >= 2:
        return ".tsv"
    if "," in t and len(t.splitlines()) >= 2:
        # CSV ofter open in Excel
        return ".csv"
    # SQL
    if re.search(r"\b(create\s+table|select\s+.+\s+from|insert\s+into|update\s+\w+\s+set)\b", low):
        return ".sql"
    # Python / R
    if re.search(r"\b(def\s+\w+\(|import\s+\w+|from\s+\w+\s+import)\b", t):
        return ".py"
    if re.search(r"\b(library\(|ggplot\(|dplyr|tidyr|<-)\b", low):
        return ".R"
    # JSON / YAML
    if low.startswith("{") or low.startswith("["):
        return ".json"
    if re.search(r"^\s*[\w\-]+\s*:\s*.+$", t, flags=re.MULTILINE):
        return ".yml"
    # Markdown
    if re.search(r"^#{1,6}\s+\S+", t, flags=re.MULTILINE) or "```" in t:
        return ".md"
    
    return ".txt"

def _ensure_extension_auto(name: str, content: str) -> str:
    n = (name or "").strip().strip("\"'` ")
    if not n:
        ext = _guess_extension_from_content(content)
        return "output" + ext

    if Path(n).suffix:
        return n

    ext = _guess_extension_from_content(content)
    return n + ext

# ---------------- Parse write ----------------
def _parse_save_intent(text: str) -> str | None:
    t = (text or "").strip()
    low = t.lower()

    if not re.search(r"\b(сохрани|сохранить|запиши|записать|save)\b", low):
        return None

    # Save to file ..."
    m = re.search(r"(?:в файл|to file)\s+(.+)$", t, flags=re.IGNORECASE)
    if m:
        name = m.group(1).strip(" :\"'`")
        if name:
            return name

    # Without name - default
    return "output.txt"
def _parse_delete_intent(text: str) -> str | None:
    t = (text or "").strip()

    m = re.search(
        r"(?:удали(?:ть)?|delete|remove)\s+(?:файл\s+|file\s+)?([^\n]+)",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1).strip().strip("\"'`")

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
            return f"Do you want to delete this file `{path}`? Please answer (1/2): yes or no."
        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            return f"Do you want to save file `{path}` ({n} chars)? Please confirm (1/2): yes/no."
        return f"Confirm the action `{op}` (1/2): yes or no."

    if deps.confirm_count == 0:
        if op == "delete_file":
            path = args.get("path", "")
            return f"Are you really sure that you want to delete `{path}`? Confirm (2/2): yes/no."
        if op == "write_file":
            path = args.get("path", "")
            n = len(args.get("content", "") or "")
            return f"Are you really sure that you want to save `{path}` ({n} chars)? Confirm (2/2): yes or no."
        return f"Confirm the action `{op}` one more time (2/2): yes or no."

    if deps.confirm_count < 2:
        return "Waiting for your confirmation (2/2): yes or no."

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
        return "OK. One more confirmation needed: yes/no."

    op = deps.pending_op["op"]
    args = deps.pending_op["args"]
    deps.pending_op = None
    deps.confirm_count = 0

    if op == "write_file":
        out = _write_file_impl(args["path"], args.get("content", ""))
        deps.last_meta = {"created_file": args["path"], "last_tool": "write_file(executed)"}
        return out

    if op == "delete_file":
        out = _delete_file_impl(args["path"])
        if out.startswith("Deleted"):
            deps.last_meta = {"deleted_file": args["path"], "last_tool": "delete_file(executed)"}
        return out

    return None

# ---------------- Tools (impl) ----------------

def _read_file_impl(path: str) -> str:
    p = _resolve_path_with_fallback(path)
    if p is None:
        return f"ERROR: file not found: {path}"
    if p.is_dir():
        return f"ERROR: '{p}' is a directory."
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
    raw = (pattern or "").strip().strip("\"'` ")
    if not raw:
        return []

    search_roots = [
        PROJECT_ROOT,
        #Path.home(),
        #Path("/Volumes"),
    ]

    matches = []
    seen = set()

    for root in search_roots:
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if _matches_query(p, raw):
                    s = str(p.resolve())
                    if s not in seen:
                        seen.add(s)
                        matches.append(s)
        except (PermissionError, OSError):
            continue

    return sorted(matches)

def _delete_file_impl(path: str) -> str:
    p = _resolve_in_project(path)
    if p is None:
        return f"ERROR: refusing to delete outside project root: {path}"
    
    if not p.exists():
        return f"File not found: {path}"

    abs_path = str(p.resolve())
    try:
        print(f"[DEBUG] Deleting file: {abs_path}")
        p.unlink()
    except Exception as e:
        return f"ERROR deleting {abs_path}: {e}"
    if p.exists():
        return f"ERROR deleting {abs_path}: file still exists after unlink."
    return f"Deleted {abs_path}"

def _load_skill_impl(filename: str, skills_dir: str = "skills") -> str:
    filename = Path(filename).name
    candidates = [
        PROJECT_ROOT / skills_dir / filename,
        Path(skills_dir) / filename,
        PROJECT_ROOT / filename,
    ]

    p = None
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                p = candidate
                break
        except OSError:
            continue

    if p is None:
        p = _resolve_path_with_fallback(str(Path(skills_dir) / filename))
    if p is None:
        p = _resolve_path_with_fallback(filename)

    if p is None:
        return f"ERROR: skill not found: {filename}"
    if p.is_dir():
        return f"ERROR: '{p}' is a directory."

    return p.read_text(encoding="utf-8")

def _read_selected_file_impl(deps: AgentDeps) -> str:
    if not deps.selected_file:
        return "No file selected. Ask the user to upload a file first."
    return _read_file_impl(deps.selected_file)


def _extract_user_context(user_input: str, deps: AgentDeps) -> None:
    text = (user_input or "").strip()
    if not text:
        return

    location_match = re.search(r"\b(?:i live|living|live|located|from|in)\s+(?:in\s+)?(?:the\s+)?([A-Za-zÄÖÜäöüß\- ]{2,})", text, flags=re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip(" ,.")
        if location:
            deps.user_context["location"] = location

    if re.search(r"\b(?:bavaria|bayern|germany|deutschland)\b", text, flags=re.IGNORECASE):
        deps.user_context["region"] = "Bavaria/Germany"


def _auto_select_skill(user_input: str) -> tuple[str | None, str | None]:
    text = (user_input or "").strip().lower()
    if not text:
        return None, None

    tokens = re.findall(r"[A-Za-zА-Яа-яäöüÄÖÜß]{2,}", text)
    token_set = {token.lower() for token in tokens if len(token) >= 3}
    if not token_set:
        return None, None

    scores: list[tuple[int, Path]] = []
    skills_dir = Path("skills")
    if not skills_dir.exists():
        return None, None

    for skill_file in sorted(skills_dir.glob("*.md")):
        try:
            skill = frontmatter.load(skill_file)
        except Exception:
            continue

        metadata = skill.metadata or {}
        name = str(metadata.get("name") or "").lower()
        description = str(metadata.get("description") or "").lower()
        filename = skill_file.stem.lower()
        body = (getattr(skill, "content", "") or "").lower()
        skill_text = " ".join([filename, name, description, body, skill_file.name.lower()])
        if not skill_text.strip():
            continue

        score = sum(2 for token in token_set if token in skill_text)
        if not score:
            continue

        for token in sorted(token_set):
            if token in ["letter", "jobcenter", "document", "draft", "legal", "benefit", "widerspruch", "antrag", "update", "missing", "german", "formal", "polite"]:
                if token in skill_text:
                    score += 3

        for domain_terms in [
            ["medical", "triage", "doctor", "symptom", "emergency", "fever", "pain", "urgent", "child", "health"],
            ["sql", "database", "query", "table", "join", "select", "postgres", "mysql"],
            ["python", "code", "script", "function", "class", "debug"],
            ["email", "mail", "reply", "message"],
            ["legal", "law", "contract", "claim", "draft", "jobcenter", "widerspruch", "antrag"],
            ["translation", "translate", "language", "german", "english"],
            ["data", "analysis", "dataset", "chart", "statistics"],
            ["form", "administrative", "legal", "bureaucratic", "de", "low"],
        ]:
            if any(term in skill_text for term in domain_terms):
                score += 1

        scores.append((score, skill_file))

    if not scores:
        return None, None

    best_score, best = max(scores, key=lambda item: item[0])
    if best_score < 4:
        return None, None

    return str(best.relative_to(Path("."))), _load_skill_impl(best.name, "skills")


def _maybe_auto_open_file(
    user_input: str,
    deps: AgentDeps,
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]], dict[str, Any]] | None:
    text = (user_input or "").strip()
    if not text:
        return None

    if deps.selected_file:
        return None

    lower = text.lower()
    if any(lower.startswith(prefix) for prefix in ("save ", "write ", "delete ", "remove ", "run ", "execute ", "install ")):
        return None

    # Only attempt file search when the user explicitly asks to open/read/find a file
    if not re.search(r"\b(open|read|show|find|locate|открой|откройте|прочитай|прочитайте|покажи|покажите|найди|найдите)\b", lower):
        return None

    # Only treat tokens that look like filenames (must contain a dot/extension)
    candidates = [c for c in re.findall(r"[A-Za-z0-9_.-]{3,}", text) if "." in c]
    for token in candidates:
        matches = _search_files_impl(token)
        if not matches:
            continue

        meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
        if len(matches) == 1:
            result = _read_file_impl(matches[0])
            deps.last_answer = result
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": result})
            return result, messages, meta

        result = "Found files:\n" + "\n".join(matches)
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": result})
        return result, messages, meta

    return None

# ---------------- Skills list for prompt ----------------

class SkillsCapability:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir

    def get_instructions(self) -> str:
        d = Path(self.skills_dir)
        if not d.exists():
            return "Available skills:\n(none)\n"
        md_files = sorted(p for p in d.glob("*.md") if p.is_file())
        if not md_files:
            return "Available skills:\n(none)\n"
        lines = [
            "Available skills:",
            "Use a skill when the user's request clearly matches a domain covered by a skill file.",
            "When a relevant skill exists, load it with TOOL load_skill filename=<skill_file_name> before answering.",
        ]
        for f in md_files:
            skill = frontmatter.load(f)
            name = skill.metadata.get("name") or f.stem
            desc = skill.metadata.get("description") or ""
            lines.append(f"- {f.name}: {name} — {desc}".rstrip())
        return "\n".join(lines) + "\n"

    def load_skill(self, filename: str) -> str:
        return _load_skill_impl(filename, self.skills_dir)


def _skills_block(skills_dir: str = "skills") -> str:
    return SkillsCapability(skills_dir).get_instructions()

# ---------------- Parsing: TOOL line + markers ----------------

def _parse_tool_line(text: str) -> tuple[str, dict[str, str]] | None:
    lines = (text or "").splitlines()
    tool_line = None
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("TOOL "):
            tool_line = ln
            break
    if not tool_line:
        return None

    parts = re.findall(r'''(?:[^\s"]+|"[^"]*")+''', tool_line)
    if len(parts) < 2:
        return None

    name = parts[1].strip()
    args: dict[str, str] = {}
    for p in parts[2:]:
        if "=" not in p:
            continue

        k, v = p.split("=", 1)
        args[k.strip()] = v.strip().strip("\"'")
    return name, args

# ---------------- Prompt ----------------

FULL_INSTRUCTIONS = (
    "You are a helpful assistant for both coding and text tasks.\n"
    "You are a helpful assistant at first, generate answer with text first of all and not with code or files location.\n"
    "Everytime responce with text, not code. Code only if ask to write, check, change, adjust code only\n"
    "\n"
    "You have access to local files ONLY through tools.\n"
    "Never say you cannot access local files.\n"
    "\n"
    "If the user has already uploaded or selected a file, treat that file as the primary source of truth.\n"
    "If a file is selected AND the user asks about that file (summarize/analyze/translate/edit it), you MUST call TOOL read_selected_file first.\n"
    "Do not search for unrelated files when a selected file is already available.\n"
    "\n"
    "Available tools:\n"
    "- read_file\n"
    "- read_selected_file\n"
    "- search_files\n"
    "- load_skill\n"
    "- write_file\n"
    "- delete_file\n"
    "\n"
    "Allowed without confirmation:\n"
    "- read_file\n"
    "- read_selected_file\n"
    "- search_files\n"
    "- load_skill\n"
    "\n"
    "FILE CREATION RULE:\n"
    "- If the user asks to create/save/write a file, you MUST call TOOL write_file.\n"
    "- If the user asks to create/save/write a file, you MUST call TOOL write_file.\n"
    "- Do NOT output any Python code, explanations, or commentary.\n"
    "- Output EXACTLY two parts only:\n"
    "  (1) the exact file content as plain text\n"
    "  (2) one line: TOOL write_file path=<filename> content=\"<exact same content>\"\n"
    "- The filename must include an extension (e.g. demo.txt). If user omitted extension, use .txt.\n"
    "\n"
    "If the user explicitly asks to open/read/find a file and provides a filename:\n"
    "1. Call TOOL search_files query=<filename>.\n"
    "2. If exactly one file is found, call TOOL read_file path=<full_path>.\n"
    "3. Otherwise, list matches and ask which one to open.\n"
    "\n"
    "If the user asks to run a script:\n"
    "1. search_files\n"
    "2. read_file\n"
    "3. then answer using the file content.\n"
    "\n"
    "For health or medical questions, do not answer with code, Python snippets, or unrelated technical text.\n"
    "Answer in plain language only, very briefly, and follow the medical skill guidance.\n"
    "If the request is about a child with fever, give simple first steps and urgent warning signs.\n"
    "\n"
    "TOOL FORMAT:\n"
    "TOOL <tool_name> key=value key=value\n"
    "\n"
    "If you call TOOL write_file, put the file content into the content=... argument (do not omit it).\n"
    "When the user asks to create/save/write a file: your answer must be exactly two parts: (1) the content, (2) one TOOL write_file line.\n"
    "Do not output FINAL until all required tool calls are finished.\n"
    "You MUST use the output of every tool.\n"
    "If read_file returns text, answer using that text.\n"
    "Never ignore tool results.\n"
    "Never replace them with a generic reply.\n"
    "read_selected_file can ONLY be used as: TOOL read_selected_file (no arguments).\n"
    "Never write fake Python like read_selected_file('file') or print(read_selected_file(...)). That is not a real function.\n"
)

# ---------------- Stream-chat ----------------

def _ollama_chat_stream_text(model: str, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
    text_parts: list[str] = []
    last_chunk: dict[str, Any] = {}

    for chunk in ollama_chat(model=model, messages=messages, stream=True):
        last_chunk = chunk
        msg = chunk.get("message", {})
        piece = msg.get("content", "")
        if piece:
            text_parts.append(piece)

    full_text = "".join(text_parts).strip()
    meta = {
        "model": model,
        "input_tokens": last_chunk.get("prompt_eval_count", "—"),
        "output_tokens": last_chunk.get("eval_count", "—"),
    }
    return full_text, meta

# ---------------- Local runner ----------------

def run_full_local(
    user_input: str,
    deps: AgentDeps,
    messages: list[dict[str, str]] | None,
):
    if messages is None:
        messages = []

    # 0) Confirmation first (this is the ONLY place where write/delete can actually execute)
    confirm_out = _handle_confirmations(user_input, deps)
    if confirm_out is not None:
        meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
        if deps.last_meta:
            meta.update(deps.last_meta)
            deps.last_meta = None
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": confirm_out})
        
        deps.last_answer = confirm_out
        return confirm_out, messages, meta
    
    _extract_user_context(user_input, deps)

    delete_path = _parse_delete_intent(user_input)

    if delete_path:
        matches = _search_files_impl(delete_path)

        if not matches:
            msg = f"File '{delete_path}' not found."
            meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta

        if len(matches) > 1:
            msg = "Found several files:\n" + "\n".join(matches)
            meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta

        rel = str(Path(matches[0]).relative_to(PROJECT_ROOT))

        msg = _require_double_confirm(
            deps,
            "delete_file",
            {"path": rel},
        )
        meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": msg})
        meta["last_tool"] = "delete_file(confirm)"
        return msg, messages, meta

    auto_result = _maybe_auto_open_file(user_input, deps, messages)
    if auto_result is not None:
        return auto_result

    skills_capability = SkillsCapability()
    system = FULL_INSTRUCTIONS + "\n" + skills_capability.get_instructions()

    convo: list[dict[str, str]] = [{"role": "system", "content": system}]
    convo.extend([m for m in messages if m.get("role") != "system"])
    convo.append({"role": "user", "content": (user_input or "").strip()})
    
    prompt_l = (user_input or "").lower()
    if any(k in prompt_l for k in LOW_KEYWORDS):
        style = "concise"
    elif any(k in prompt_l for k in HIGH_KEYWORDS):
        style = "detailed"
    else:
        style = "normal"

    convo.append({
        "role": "user",
        "content": (
            f"STYLE={style}. "
            "Default output is plain text for non-technical people. "
            "Only output code if the user explicitly asks to write/fix/adjust code."
        )
    })
    
    if deps.user_context:
        context_text = "; ".join(f"{k}={v}" for k, v in deps.user_context.items())
        convo.append({"role": "user", "content": f"User context: {context_text}. Use this context when it helps answer the request, especially for region-specific legal or medical advice."})
    if deps.selected_file and re.search(r"\b(summarize|analyze|translate|edit|объясни|проанализируй|переведи|отредактируй|суммари|резюме)\b", user_input.lower()):
        content = _read_selected_file_impl(deps)
        meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—", "last_tool": "read_selected_file(auto)"}
        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": content})
        return content, messages, meta

    used_skill: str | None = None

    text = user_input.lower()

    code_words = (
        "javascript", "typescript", "java", "c++", "c#", "golang", "rust",
        "write code", "generate code", "show code", "adjust code", "change code", "correct code",
        "напиши код", "сгенерируй код", "покажи код", "откорректируй код", "оптимизируй код", 
        "fix my code", "debug my code", "refactor",
        "исправь код", "поправь код", "почини код", "поменяй код",
        "traceback", "stack trace"
    )
    wants_code = any(w in text for w in code_words)
    wants_file_op = bool(re.search(r"\b(create|save|write)\b.*\bfile\b|\b(сохрани|сохранить|запиши|записать|создай)\b", text))
    model = CHAT_MODEL if wants_file_op else (CODE_MODEL if wants_code else CHAT_MODEL)

    auto_skill_path, auto_skill_content = (None, None) if wants_file_op else _auto_select_skill(user_input)
    if not used_skill and auto_skill_path and auto_skill_content and not auto_skill_content.startswith("ERROR"):
        used_skill = auto_skill_path
        convo.append({
            "role": "user",
            "content": (
                f"IMPORTANT: The request matches the skill file {auto_skill_path}. "
                "Use the skill content as the main source of truth for this request. "
                "Do not ignore it. Do not answer with code, unrelated technical snippets, or generic filler. "
                "Produce a normal, helpful answer in the requested language and style.\n"
                f"SKILL_FILE: {auto_skill_path}\n"
                f"SKILL_CONTENT:\n{auto_skill_content}"
            ),
        })

    for _ in range(20):
        assistant, token_meta = _ollama_chat_stream_text(model, convo)
        meta = dict(token_meta)

        if deps.last_meta:
            meta.update(deps.last_meta)
            deps.last_meta = None
        if used_skill:
            meta["used_skill"] = used_skill
        print("\n========== LLM ==========")
        print(assistant)
        print("=========================\n")
        tool = _parse_tool_line(assistant)

        if tool is None:
            assistant = assistant.removeprefix("FINAL").lstrip(":").strip()

            deps.last_answer = assistant
            
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": assistant})
            return assistant, messages, meta

        tool_name, args = tool

        # Never execute write/delete directly; always convert into confirmation request
        if tool_name == "delete_file":
            raw = (args.get("path", "") or args.get("file", "") or args.get("filename", "")).strip()
            if not raw:
                msg = "ERROR: delete_file requires path."
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": msg})
                return msg, messages, meta
            
            candidates: list[Path] = []

            base = _resolve_in_project(raw)
            if base is not None and base.exists():
                candidates = [base]
            else:
                matches = _search_files_impl(raw)
                # keep only files inside project root
                in_project = []
                for m in matches:
                    try:
                        p = Path(m).resolve()
                        p.relative_to(PROJECT_ROOT)
                        in_project.append(p)
                    except Exception:
                        continue
                if not in_project:
                    msg = f"Файл по имени '{raw}' не найден в проекте."
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "assistant", "content": msg})
                    return msg, messages, meta

                if len(in_project) > 1:
                    listed = ", ".join(str(p.relative_to(PROJECT_ROOT)) for p in in_project[:5])
                    if len(in_project) > 5:
                        listed += ", ..."
                    msg = f"Найдено несколько файлов для '{raw}': {listed}. Уточните, какой именно удалить."
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "assistant", "content": msg})
                    return msg, messages, meta

                candidates = [in_project[0]]

            if not candidates:
                msg = f"Файл по имени '{raw}' не найден в проекте."
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": msg})
                return msg, messages, meta

            if len(candidates) > 1:
                listed = ", ".join(str(c.relative_to(PROJECT_ROOT)) for c in candidates[:5])
                if len(candidates) > 5:
                    listed += ", ..."
                msg = f"Найдено несколько файлов для '{raw}': {listed}. Уточните, какой именно удалить."
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": msg})
                return msg, messages, meta

            cand = candidates[0]
            rel_path = str(cand.relative_to(PROJECT_ROOT))

            msg = _require_double_confirm(deps, "delete_file", {"path": rel_path})
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta
        
        if tool_name == "write_file":
            raw = args.get("path", "").strip() or args.get("file", "").strip() or args.get("filename", "").strip()
            if not raw:
                msg = "ERROR: write_file requires path."
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": msg})
                return msg, messages, meta
            content = args.get("content", "")

            if not (content or "").strip():
                content = deps.last_answer or ""

            if not (content or "").strip():
                msg = "ERROR: nothing to write. First provide the content, then request write_file."
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": msg})
                return msg, messages, meta

            msg = _require_double_confirm(deps, "write_file", {"path": raw, "content": content})
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": msg})
            return msg, messages, meta

        if tool_name == "search_files":
            query = (
                args.get("query")
               or args.get("pattern")
                or args.get("path")
                or args.get("filename")
                or args.get("file")
                or ""
            )

            result = _search_files_impl(query)
        elif tool_name == "read_file":
            path = args.get("path") or args.get("file") or args.get("filename")

            if not path:
                result = "ERROR: read_file requires path."
            else:
                result = _read_file_impl(path)
        elif tool_name == "read_selected_file":
            result = _read_selected_file_impl(deps)
        elif tool_name == "load_skill":
            result = skills_capability.load_skill(args.get("filename", ""))
            if args.get("filename"):
                used_skill = args.get("filename")
                meta["used_skill"] = used_skill
        else:
            result = f"Unknown tool: {tool_name}"
        if isinstance(meta, dict):
            meta["last_tool"] = tool_name

        convo.append({"role": "assistant", "content": assistant})
        if tool_name == "search_files":
            if not result:
                tool_result = "No files found."
            elif len(result) == 1:
                tool_result = (
                    "Found exactly one file:\n"
                    f"{result[0]}\n"
                    "Now call TOOL read_file path=\"" + result[0] + "\""
                )
            else:
                tool_result = "Found files:\n" + "\n".join(result)
        else:
            tool_result = str(result)
        convo.append({
            "role": "user",
            "content":
                f"Tool {tool_name} returned:\n\n"
                f"{result}\n\n"
                "Use ONLY this content to answer the user's request. "
                "Do NOT ignore it. "
                "Do NOT ask for the file again. "
                "If the user asked to explain, explain this content."
        })
        
        continue

    msg = "Stopped (tool loop limit reached)."
    meta = {"model": CHAT_MODEL, "input_tokens": "—", "output_tokens": "—"}
    messages.append({"role": "assistant", "content": msg})
    return msg, messages, meta
