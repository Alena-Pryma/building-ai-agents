import os

from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

#---------Main---------

def run_ex1(user_input: str):
    load_dotenv()

    # Provider
    provider = OpenAIProvider(
        base_url=os.environ["ROUTER_BASE_URL"],
        api_key=os.environ["ROUTER_API_KEY"],
    )
    model_name = os.environ["ROUTER_MODEL_TOOLS_LIGHT"]

    # Model
    model = OpenAIChatModel(
        model_name=model_name,
        provider=provider,
    )

    # Agent
    agent = Agent(
        model=model,
        instructions=(
            "You are a Python coding assistant. "
            "Write clear, correct, and minimal Python code."
        ),
    )

    # Run the agent
    result = agent.run_sync(user_input)
    usage = result.usage
    meta = {
        "model": model_name,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    return result.output, meta

def main() -> None:
    console = Console()
    user_input = console.input(">> ")
    out, model_name = run_ex1(user_input)
    console.print(f"[model] {model_name}")
    console.print(out)

if __name__ == "__main__":
    main()