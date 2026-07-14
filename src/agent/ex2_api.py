import os

from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

#---------Main---------

def main() -> None:
    load_dotenv()
    console = Console()

    message_history = None

    while True:
        user_input = console.input(">> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            return

        output, message_history, _model_name = run_ex2(user_input, message_history)
        console.print(output)

def run_ex2(user_input: str, message_history=None):
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
            "You are a helpful assistant for both coding and text tasks.\n"
            "Only output code when the user explicitly asks for code or debugging.\n"
            "Write clear, correct, and minimal."
            "If the user asks for code (mentions Python/JS/SQL/R, functions, errors, stack traces, files, or requests code), respond with minimal runnable code + a short note.\n"
            "If the user asks for translation or writing, respond with text (no code).\n"
            "If unclear, ask one clarifying question.\n"
        ),
    )

    result = agent.run_sync(user_input, message_history=message_history)
    usage = result.usage
    meta = {
        "model": model_name,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    return result.output, result.all_messages(), meta


if __name__ == "__main__":
    main()