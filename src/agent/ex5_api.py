from __future__ import annotations

import os
from typing import Any, Callable

from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

class ReasoningEffort(AbstractCapability[Any]):
    """Adjusts model reasoning effort based on keywords in the user prompt."""

    LOW_KEYWORDS = {
        "simple", "easy", "quick", "fast", "short", "brief", "concise", "simply",
        "main", "primary", "basic", "fundamental", "quickly", "briefly", "clearly",
        "essential", "core", "shortly", "main point", "key", "precisely", "to the point",
        "просто", "легко", "быстро", "кратко", "коротко", "сжато", "четко", "основное",
        "основной", "основная", "основные", "главное", "главная", "главные", "основы",
        "кратко", "краткий", "краткая", "по сути", "вкратце", "в двух словах",
    }

    HIGH_KEYWORDS = {
        "hard", "complex", "difficult", "challenging", "complicated",
        "deep", "prove", "detailed", "thoroughly",
        "explain", "explanation", "in detail", "step by step",
        "сложно", "сложный", "трудно", "тяжело", "подробно", "детально",
        "тщательно", "объясни", "объяснение", "шаг за шагом", "пошагово",
    }

    def get_model_settings(self) -> Callable[[RunContext[Any]], ModelSettings]:
        """Returns a callback that sets reasoning effort for each request."""
        
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

def run_ex5(user_input: str) -> str:
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
            "Answer clearly and concisely. "
            "If the user asks to create/modify/delete files, first ask for explicit confirmation."
        ),
        capabilities=[ReasoningEffort()],
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
    console.print(run_ex5(user_input))

if __name__ == "__main__":
    main()