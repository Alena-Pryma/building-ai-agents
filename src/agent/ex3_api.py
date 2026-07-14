from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIResponsesModel

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

#---------Tools---------

def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk and return its content.

    Args:
        path: Path to the file to read (relative or absolute).

    Returns:
        The file content as a string.
    """
    return Path(path).read_text(encoding="utf-8")

def write_file(path: str, content: str) -> str:
    """Write UTF-8 text content to disk.

    Args:
        path: Path to the file to write (relative or absolute).
        content: The full text content to write.

    Returns:
        A short confirmation message.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"

def search_files(pattern: str) -> list[str]:
    """Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern, e.g. '**/*.py'.

    Returns:
        List of matching file paths as strings.
    """
    return [str(p) for p in Path(".").glob(pattern) if p.is_file()]

def delete_file(path: str) -> str:
    """Delete a file from disk.

    Args:
        path: Path to the file to delete.

    Returns:
        A short confirmation message.
    """
    p = Path(path)
    if p.exists():
        p.unlink()
        return f"Deleted {path}"
    return f"File not found: {path}"

#---------Capability---------

class FileOperations(AbstractCapability[Any]):
    def get_toolset(self) -> FunctionToolset:
        toolset = FunctionToolset()
        toolset.add_function(read_file)
        toolset.add_function(write_file)
        toolset.add_function(search_files)
        toolset.add_function(delete_file)
        return toolset

#---------Main---------
def run_ex3(user_input: str) -> str:
    load_dotenv()
    console = Console()

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
            "You can use tools to read, write, search, and delete files. "
            "Reading and searching files are always allowed. "
            "Never create, write, overwrite, or delete files without the user's explicit permission. "
            "Before performing any file modification or deletion, ask the user for confirmation. "
            "Proceed only after the user confirms the operation twice with a clear affirmative response. "
            "If the user does not provide two explicit confirmations, do not call write_file or delete_file."
        ),
        capabilities=[FileOperations()],
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
    console.print(run_ex3(user_input))

if __name__ == "__main__":
    main()