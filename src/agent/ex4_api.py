from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from pydantic_ai.tools import ToolDefinition
from pydantic_ai.messages import ToolCallPart
from pydantic_ai import RunContext

from src.agent.deps import AgentDeps

#---------Tools---------

def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk and return its content."""
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"
    return p.read_text(encoding="utf-8")

def write_file(path: str, content: str) -> str:
    """Write UTF-8 text content to disk."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"

def search_files(pattern: str) -> list[str]:
    """Search for files matching a glob pattern, e.g. '**/*.py'."""
    return [str(p) for p in Path(".").glob(pattern) if p.is_file()]

def delete_file(path: str) -> str:
    """Delete a file from disk."""
    p = Path(path)
    if p.exists():
        p.unlink()
        return f"Deleted {path}"
    return f"File not found: {path}"

#---------FOR WEB SEARCH WITH TAVILY---------
#from tavily import TavilyClient
#python -m pip install tavily-python
#def web_search(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web for recent info."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    r = client.search(query=query, max_results=max_results)
    out = list[dict[str, str]] = []
    for item in r.get("results", [])[:max_results]:
        out.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:300],
            }
        )
    return out


#---------Capability with hook---------
class FileOperations(AbstractCapability[AgentDeps]):
    def get_toolset(self) -> FunctionToolset:
        toolset = FunctionToolset()
        toolset.add_function(read_file)
        toolset.add_function(write_file)
        toolset.add_function(search_files)
        toolset.add_function(delete_file)
        #toolset.add_function(web_search)
        return toolset

    async def before_tool_execute(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Log each tool invocation before execution."""
        
        ctx.deps.console.print(f"[tool] Calling tool: {call.tool_name}")
        return args

def run_ex4(user_input: str) -> str:
    load_dotenv()
    console = Console()
    deps = AgentDeps(console=console)

    provider = OpenAIProvider(
        base_url=os.environ["ROUTER_BASE_URL"],
        api_key=os.environ["ROUTER_API_KEY"],
    )
    model_name = os.environ["ROUTER_MODEL_TOOLS_MEDIUM"]

    model = OpenAIChatModel(
        model_name=model_name,
        provider=provider,
    )

    agent = Agent(
        model=model,
        instructions=(
            "You are a Python coding assistant. "
            "You can use tools to read, search, write, and delete files. "
            "Reading and searching files are always allowed. "
            "Never call write_file or delete_file without the user's explicit permission. "
            "Before modifying or deleting any file, ask the user for confirmation. "
            "Only perform the operation after the user confirms it."
            "After using search_files, always use one of the returned paths exactly as-is when calling read_file. "
            "Never invent filenames like 'result_from_search'. "
        ),
        deps_type=AgentDeps,
        capabilities=[FileOperations()],
    )

    result = agent.run_sync(user_input, deps=deps)
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
    console.print(run_ex4(user_input))

if __name__ == "__main__":
    main()