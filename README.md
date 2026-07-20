# Building AI Agents - Coding Assistant (THRIVE 3.0)

This project is my solution for the “Building AI Agents” exercises (1–6) and a Full Assistant built with **PydanticAI** for work with API-keys and local (ollama).

## What it does
- Answers Python/coding questions
- Supports multi-turn chat (conversation history)
- Can use file tools: read/search/write/delete (write/delete require double confirmation)
- Adds visibility via tool-call hooks
- Adjusts reasoning effort (low/medium/high) based on the request
- Loads additional Skills from `/skills` (Markdown)

## How to run (API / Gradio UI)
1) Install dependencies:
   `pip install -r requirements.txt`
2) Create `.env` (see `.env.example`)
3) Run the app:
   `python run_web.py`


## How to run (ollama / Gradio UI)
1) Install dependencies:
   `pip install -r requirements.txt`
2) Make sure Ollama is installed and the model is available (e.g. `llama3.2:3b`, `qwen2.5-coder:7b`)
3) Run the app:
   `python run_web_local.py`

## Configuration
Create a `.env` file locally (do not commit it). Use `.env.example` as a template.

## Project structure (high level)
- `src/agent/` — exercises + full assistant (API version) + full assistant local (ollama version)
- `skills/` — markdown skills loaded at runtime
- `run_web.py` — Gradio entrypoint
- `run_web_local.py` — Gradio entrypoint
- `requirements.txt` — dependencies
