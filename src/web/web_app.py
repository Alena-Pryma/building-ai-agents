import gradio as gr
from rich.console import Console

from src.agent.ex1_api import run_ex1
from src.agent.ex2_api import run_ex2
from src.agent.ex3_api import run_ex3
from src.agent.ex4_api import run_ex4
from src.agent.ex5_api import run_ex5
from src.agent.ex6_api import run_ex6
from src.agent.full_assistant import run_full, AgentDeps

console = Console()

def router(exercise: str, user_text: str):
    mapping = {
        "Exercise 1": run_ex1,
        "Exercise 3": run_ex3,
        "Exercise 4": run_ex4,
        "Exercise 5": run_ex5,
        "Exercise 6": run_ex6,
    }
    fn = mapping[exercise]
    result = fn(user_text)

    if isinstance(result, tuple) and len(result) == 3:
        out, _messages, meta = result
        return out, meta
    
    if isinstance(result, tuple) and len(result) == 2:
        out, _messages, meta = result
        return result

    return result, {"model": "—", "input_tokens": "—", "output_tokens": "—"}

def make_badge(meta):
    if isinstance(meta, dict):
        model_name = meta.get("model", "—")
        in_tok = meta.get("input_tokens", "—")
        out_tok = meta.get("output_tokens", "—")
    else:
        model_name = str(meta)
        in_tok = "—"
        out_tok = "—"

    return (
        "<div class='model-badge'>"
        f"Model: <span class='model-pill'>{model_name}</span>"
        f"&nbsp;&nbsp;Tokens: <span class='model-pill'>in {in_tok} / out {out_tok}</span>"
        "</div>"
    )

def add_emoji(current_text, emoji):
    current_text = current_text or ""
    if current_text and not current_text.endswith((" ", "\n")):
        current_text += " "
    return current_text + emoji

def toggle_emoji_panel(is_open: bool):
    is_open = bool(is_open)
    new_open = not is_open
    return new_open, gr.update(visible=new_open)

def add_emoji_and_close(current_text, emoji):
    new_text = add_emoji(current_text, emoji)
    return new_text, False, gr.update(visible=False)

def add_emoji_1(t): return add_emoji_and_close(t, "😀")
def add_emoji_2(t): return add_emoji_and_close(t, "😂")
def add_emoji_3(t): return add_emoji_and_close(t, "🥹")
def add_emoji_4(t): return add_emoji_and_close(t, "😍")
def add_emoji_5(t): return add_emoji_and_close(t, "👍")
def add_emoji_6(t): return add_emoji_and_close(t, "🙏")
def add_emoji_7(t): return add_emoji_and_close(t, "🔥")
def add_emoji_8(t): return add_emoji_and_close(t, "🎉")
def add_emoji_9(t): return add_emoji_and_close(t, "❤️")

def reply(message: str, history, exercise: str, ex2_history, full_history, full_deps):
    if full_deps is None:
        full_deps = AgentDeps(console=console)
    
    if (message or "").strip().lower() in {"exit", "quit"}:
        return "Chat ended. Click the clear button in the chat to start a new conversation.", ex2_history, full_history, full_deps

    try:
        if exercise == "Exercise 2":
            output, new_hist = run_ex2(message, ex2_history)
            return output, new_hist, full_history, full_deps
        
        if exercise == "Full Assistant":
            output, new_hist, meta = run_full(message, full_deps, full_history)
            return output, ex2_history, new_hist, full_deps
        
        return router(exercise, message), ex2_history, full_history, full_deps

    except Exception as e:
        return f"Error in {exercise}: {type(e).__name__}: {e}", ex2_history, full_history, full_deps


def main():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root, body, .gradio-container,
    #chatbox, #chatbox *,
    input, textarea, button, select {
      font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif !important;
      font-style: normal !important;
    }
    .gradio-container { max-width: none !important; width: 96vw !important; margin: 0 auto; }

    #app {
      height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 12px;
      padding: 6px 12px;
    }

    .panel { border-radius: 16px !important; border: 1px solid rgba(0,0,0,.06); background: #ffffff !important; box-shadow: none !important; }
    #model_badge .model-badge{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255,255,255,.65);
      border: 1px solid rgba(0,0,0,.08);
      font-size: 13px;
      color: rgba(0,0,0,.72);
    }
    .file-status, #file_status {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    #model_badge .model-pill{
      padding: 6px 10px;
      border-radius: 999px;
      background: #eef0f4;
      border: 1px solid rgba(0,0,0,.08);
      font-weight: 600;
      color: rgba(0,0,0,.78);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }

    body, .gradio-container { background: #ffffff !important; }
    .gradio-container > .wrap { background: #f8f9fb !important; padding: 12px 0 !important; }
    
    button { border-radius: 14px !important; }
    input, textarea { border-radius: 14px !important; }

    #main_row { min-height: 0; display:flex; gap:16px; align-items:stretch; }
    #main_row > .column { display:flex; flex-direction:column; }

    #chatbox { flex: 1 1 auto !important; min-height: 260px !important; max-height: calc(100vh - 340px) !important; overflow:auto !important; }
    
    #inputbox { width: 100%; }
    #inputbox .input_outer { background: #ffffff !important; }

    #actions_row { display:flex; justify-content: flex-end !important; gap: 12px !important; padding-top:6px; }
    #actions_row button { min-width:120px; border-radius:12px !important; }

    /* emoji must be compact */
    #emoji_toggle button{
      min-width: 44px !important;
      width: 44px !important;
      padding: 0 !important;
    }

    /* do NOT force width on emoji toggle */
    #actions_row .emoji-toggle-btn { min-width: 44px !important; }

    /* align HTML inside row */
    #actions_row .gr-html { display:flex; align-items:center; }
    
    #file_bar .panel {
      padding: 10px 12px;
    }
    
    /* prevent text clipping in left panel */
    .panel { overflow: visible !important; }
    .panel * { overflow: visible !important; }

    /* Hard-hide any buttons/icons inside Chatbot header/toolbar */
    #chatbox [class*="header"] button,
    #chatbox [class*="header"] a,
    #chatbox [class*="header"] svg,
    #chatbox [class*="header"] [role="button"],
    #chatbox [class*="toolbar"] button,
    #chatbox [class*="toolbar"] a,
    #chatbox [class*="toolbar"] svg,
    #chatbox [class*="toolbar"] [role="button"] {
      display: none !important;
    }

    #chatbox button[aria-label="Share"],
    #chatbox button[aria-label="Delete"],
    #chatbox button[aria-label="Copy"],
    #chatbox button[title="Share"],
    #chatbox button[title="Delete"],
    #chatbox button[title="Copy"] {
      display: none !important;
    }

    /* fallback: hide the entire right-side header action cluster */
    #chatbox [class*="header"] [class*="right"],
    #chatbox [class*="header"] [class*="actions"],
    #chatbox [class*="header"] [class*="buttons"] {
      display: none !important;
    }
    /* Emoji: toggle button near Send */
    #emoji_toggle button{
      width: 44px !important;
      height: 44px !important;
      padding: 0 !important;
      border-radius: 14px !important;
      font-size: 20px !important;
    }

    /* Floating emoji panel */
    #emoji_panel{
      position: fixed;
      right: 18px;
      bottom: 86px;
      z-index: 9999;
      
      width: auto;
      max-width: calc(100vw - 36px);
      
      padding: 10px;
      border-radius: 16px;
      background: rgba(255,255,255,.92);
      border: 1px solid rgba(0,0,0,.08);
      box-shadow: 0 14px 44px rgba(0,0,0,.14);
      backdrop-filter: blur(12px);
    }
    /* Remove Gradio vertical gaps inside the panel */
    #emoji_panel .row{ gap: 8px !important; }
    #emoji_panel .gr-row{ gap: 8px !important; }
    #emoji_panel .gr-column{ gap: 0 !important; }

    /* Emoji buttons: small, tight */
    #emoji_panel .emoji-btn button{
      min-width: 40px !important;
      width: 40px !important;
      height: 36px !important;
      padding: 0 !important;
      border-radius: 12px !important;
      font-size: 18px !important;
      line-height: 1 !important;
    }

    .emoji-toggle-btn{
      width:44px;height:44px;border-radius:14px;
      border:1px solid rgba(0,0,0,.08);
      background:#fff;
      font-size:20px;
      cursor:pointer;
    }
    /* force emoji panel rows to stay horizontal */
    #emoji_panel .gr-row{
      flex-wrap: nowrap !important;
      align-items: center !important;
    }

    /* prevent each emoji from stretching full width */
    #emoji_panel .gr-button{
      flex: 0 0 auto !important;
    }

    /* remove default full-width behavior inside the panel */
    #emoji_panel .gr-form{
      width: auto !important;
    }

    """
    with gr.Blocks(
        title="THRIVE 3.0 THE BEST GPT — Python Coding Assistant",
        theme=gr.themes.Soft(),
        css=css,
    ) as demo:

        with gr.Group(elem_id="app"):
            gr.Markdown(
                """
                <div style="text-align:center; padding: 6px 0 2px;">
                  <div style="font-size:28px; font-weight:800; letter-spacing:.2px;">
                    THRIVE 3.0 THE BEST GPT
                  </div>
                  <div style="opacity:.75; margin-top:4px;">
                    Python Coding Assistant • Exercises 1–6 + Full Assistant
                  </div>
                </div>
                """
            )

            with gr.Row(elem_id="main_row"):
                with gr.Column(scale=1, min_width=260):
                    with gr.Group(elem_classes=["panel"]):
                        exercise = gr.Dropdown(
                            choices=[f"Exercise {i}" for i in range(1, 7)] + ["Full Assistant"],
                            value="Exercise 1",
                            label="Mode",
                        )
                        gr.Markdown("<div style='white-space: normal; line-height: 1.25;'>Choose 1 of 6 exercises or the Full Assistant.</div>")

                with gr.Column(scale=3, min_width=520):
                    model_badge = gr.Markdown(
                        value="<div class='model-badge'>Model: <span class='model-pill'>—</span></div>",
                        elem_id="model_badge",
                    )
                    file_bar = gr.Group(visible=False, elem_classes=["panel", "filebar"])
                    with file_bar:
                        file_status = gr.Markdown(value="")
                        file_proof_wrap = gr.Group(visible=False)
                        with file_proof_wrap:
                            file_proof = gr.File(label="File", interactive=False)

                    chatbot = gr.Chatbot(label="Chat", elem_id="chatbox", elem_classes=["panel"])

            ex2_history = gr.State(None)
            full_history = gr.State(None)
            full_deps = gr.State(None)
            emoji_open = gr.State(False)

            user_box = gr.Textbox(
                label="Your message",
                placeholder="Ask a Python coding question…",
                lines=3,
                elem_id="inputbox",
                elem_classes=["panel"],
            )
            emoji_panel = gr.Column(visible=False, elem_id="emoji_panel")
            with emoji_panel:
                with gr.Row():
                    e1 = gr.Button("😀", elem_classes=["emoji-btn"])
                    e2 = gr.Button("😂", elem_classes=["emoji-btn"])
                    e3 = gr.Button("🥹", elem_classes=["emoji-btn"])
                    e4 = gr.Button("😍", elem_classes=["emoji-btn"])
                    e5 = gr.Button("👍", elem_classes=["emoji-btn"])
                    e6 = gr.Button("🙏", elem_classes=["emoji-btn"])
                    e7 = gr.Button("🔥", elem_classes=["emoji-btn"])
                    e8 = gr.Button("🎉", elem_classes=["emoji-btn"])
                    e9 = gr.Button("❤️", elem_classes=["emoji-btn"])

            with gr.Row(elem_id="actions_row"):
                send = gr.Button("Send", variant="primary")
                clear = gr.Button("Clear")
                emoji_toggle = gr.Button("🙂", elem_id="emoji_toggle", scale=0)

        def on_send(exercise, user_text, chat, ex2_hist, full_hist, full_deps):
            user_text = (user_text or "").strip()
            if full_deps is None:
                full_deps = AgentDeps(console=console)  

            file_bar_update = gr.update(visible=False)
            file_status_html = ""
            file_proof_wrap_update = gr.update(visible=False)

            badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"
            proof_file = None

            if not user_text:
                return chat, "", ex2_hist, full_hist, full_deps, badge_html, proof_file,  file_status_html, file_bar_update, file_proof_wrap_update

            if user_text.lower() in {"exit", "quit"}:
                return [], "", None, None, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update

            if exercise == "Exercise 2":
                out, new_hist, meta = run_ex2(user_text, ex2_hist)
                badge_html = make_badge(meta)
                chat = chat + [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": out},
            ]
                return chat, "", new_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update

            if exercise == "Full Assistant":
                out, full_hist, meta = run_full(user_text, full_deps, full_hist)
                if not isinstance(meta, dict):
                    meta = {}
                created = meta.get("created_file") if isinstance(meta, dict) else None
                deleted = meta.get("deleted_file") if isinstance(meta, dict) else None
                if not created and not deleted:
                    low = (out or "").lower()
                    if low.startswith("wrote ") or " created file:" in low:
                        file_status_html = "<div class='model-badge'>File created</div>"
                        file_bar_update = gr.update(visible=True)
                    elif low.startswith("deleted ") or " deleted file:" in low:
                        file_status_html = "<div class='model-badge'>File deleted</div>"
                        file_bar_update = gr.update(visible=True)

                if created:
                    proof_file = created
                    file_status_html = f"<div class='model-badge'>File created: <span class='model-pill'>{created}</span></div>"
                    file_bar_update = gr.update(visible=True)
                    file_proof_wrap_update = gr.update(visible=True)
                elif deleted:
                    proof_file = None
                    file_status_html = f"<div class='model-badge'>File deleted: <span class='model-pill'>{deleted}</span></div>"
                    file_bar_update = gr.update(visible=True)
                    file_proof_wrap_update = gr.update(visible=False)
                else:
                    proof_file = None
                    file_status_html = ""
                    file_bar_update = gr.update(visible=False)
                    file_proof_wrap_update = gr.update(visible=False)
                
                badge_html = make_badge(meta)
                chat = chat + [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": out},
                ]

                return chat, "", ex2_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update
            
            out, meta = router(exercise, user_text)
            badge_html = make_badge(meta)

            chat = chat + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": out},
            ]
            return chat, "", ex2_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update

        def on_clear():
            badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"
            return [], "", None, None, None, badge_html, None, "", gr.update(visible=False), gr.update(visible=False)
        send.click(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, full_history, full_deps],
            outputs=[chatbot, user_box, ex2_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )
        user_box.submit(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, full_history, full_deps],
            outputs=[chatbot, user_box, ex2_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )
        clear.click(
            fn=on_clear,
            inputs=[],
            outputs=[chatbot, user_box, ex2_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )
        emoji_toggle.click(
            fn=toggle_emoji_panel,
            inputs=[emoji_open],
            outputs=[emoji_open, emoji_panel],
        )

        e1.click(fn=add_emoji_1, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e2.click(fn=add_emoji_2, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e3.click(fn=add_emoji_3, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e4.click(fn=add_emoji_4, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e5.click(fn=add_emoji_5, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e6.click(fn=add_emoji_6, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e7.click(fn=add_emoji_7, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e8.click(fn=add_emoji_8, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e9.click(fn=add_emoji_9, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])

    demo.launch()

if __name__ == "__main__":
    main()