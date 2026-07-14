from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import frontmatter
from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import FunctionToolset

def load_skill(filename: str, skills_dir: str = "skills") -> str:
    """Load a skill markdown file from the skills directory and return its full text.

    Args:
        filename: The skill filename, e.g. "sql.md".
        skills_dir: Directory containing skill markdown files.

    Returns:
        The markdown content of the skill file.
    """
    p = Path(skills_dir) / filename
    return p.read_text(encoding="utf-8")

class Skills(AbstractCapability[Any]):
    """Provides access to reusable markdown skills."""
    def get_toolset(self) -> FunctionToolset:
        toolset = FunctionToolset()
        toolset.add_function(load_skill)
        return toolset

    def get_instructions(self) -> str:
        """Build the list of available skills for the agent prompt."""
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

def run_ex6(user_input: str) -> str:
    load_dotenv()

    provider = OpenAIProvider(
        base_url=os.environ["ROUTER_BASE_URL"],
        api_key=os.environ["ROUTER_API_KEY"],
    )

    model_name = os.environ["ROUTER_MODEL_TOOLS_MEDIUM"]

    model = OpenAIResponsesModel(
        model_name=model_name,
        provider=provider,
    )

    agent = Agent(
        model=model,
        instructions=(
            "You are a Python coding assistant. "
            "Always check whether the user's request matches one of the available skills. "
            "If it does, use the load_skill tool to load the skill before answering. "
            "Do not assume the contents of a skill file without loading it first. "
            "If no relevant skill is available, answer normally."
        ),
        capabilities=[Skills()],
    )

    result = agent.run_sync(user_input)
    usage = result.usage
    meta = {
        "model": model_name,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    return result.output, result.all_messages(), meta

def main() -> None:
    console = Console()
    user_input = console.input(">> ").strip()
    console.print(run_ex6(user_input))

if __name__ == "__main__":
    main()