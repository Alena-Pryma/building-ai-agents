import gradio as gr
from rich.console import Console

# local exercises
from src.agent.local_agent.ex1_local import run_ex1_local
from src.agent.local_agent.ex2_local import run_ex2_local
from src.agent.local_agent.ex3_local import run_ex3_local
from src.agent.local_agent.ex4_local import run_ex4_local
from src.agent.local_agent.ex5_local import run_ex5_local
from src.agent.local_agent.ex6_local import run_ex6_local

from pathlib import Path

# local full assistant
from src.agent.local_agent.full_assistant_local import run_full_local, AgentDeps

console = Console()

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

def router(exercise: str, user_text: str, ex2_history, ex3_history, ex4_history, ex6_history):
    if exercise == "Exercise 1":
        out, meta = run_ex1_local(user_text)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 2":
        out, ex2_history, meta = run_ex2_local(user_text, ex2_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 3":
        out, ex3_history, meta = run_ex3_local(user_text, ex3_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 4":
        out, ex4_history, meta = run_ex4_local(user_text, ex4_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 5":
        out, meta = run_ex5_local(user_text)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 6":
        out, ex6_history, meta = run_ex6_local(user_text, ex6_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    raise KeyError(exercise)

def on_send(exercise, user_text, chat, ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps, uploaded_file):
    user_text = (user_text or "").strip()

    if full_deps is None:
        full_deps = AgentDeps(console=console)
    if full_hist is None:
        full_hist = []
    if ex2_hist is None:
        ex2_hist = None

    # file UI defaults
    file_bar_visible = False
    file_status_html = ""
    file_proof_wrap_visible = False
    proof_file = None

    # update selected file from upload (used by Full Assistant read_selected_file)
    if uploaded_file is not None:
        path = getattr(uploaded_file, "name", None) or str(uploaded_file)
        full_deps.selected_file = path
        file_status_html = f"<div class='model-badge'>Selected file: <span class='model-pill'>{Path(full_deps.selected_file).name}</span></div>"
        file_bar_visible = True

    # Always provide uploaded file context to Full Assistant (simple-user UX)
    if exercise == "Full Assistant" and getattr(full_deps, "selected_file", None):
        p = Path(full_deps.selected_file)
        suffix = (p.suffix or "").lower()

        header = (
            "\n\n---\n"
            + f"UPLOADED_FILE_NAME: {p.name}\n"
            + f"UPLOADED_FILE_PATH: {full_deps.selected_file}\n"
        )

        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            user_text = user_text + header + f"UPLOADED_FILE_TYPE: image ({suffix})\n"
        elif suffix in {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".zip"}:
            user_text = user_text + header + f"UPLOADED_FILE_TYPE: binary/document ({suffix})\n"
        else:
            try:
                file_text = p.read_text(encoding="utf-8", errors="replace")[:12000]
                user_text = (
                    user_text
                    + header
                    + f"UPLOADED_FILE_TYPE: text ({suffix or 'no extension'})\n"
                    + "UPLOADED_FILE_CONTENT (first 12000 chars):\n"
                    + file_text
                )
            except Exception as e:
                user_text = (
                    user_text
                    + header
                    + f"(FAILED_TO_READ_UPLOADED_FILE_AS_TEXT: {type(e).__name__}: {e})\n"
                )

    badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"

    if not user_text:
        if getattr(full_deps, "selected_file", None):
            file_status_html = f"<div class='model-badge'>Selected file: <span class='model-pill'>{Path(full_deps.selected_file).name}</span></div>"
            file_bar_visible = True
        return (
            chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
            badge_html,
            proof_file,
            file_status_html,
            gr.update(visible=file_bar_visible),
            gr.update(visible=file_proof_wrap_visible),
        )

    if user_text.lower() in {"exit", "quit"}:
        return (
            [], "", None, None, None, None, [], full_deps,
            badge_html,
            None,
            "",
            gr.update(visible=False),
            gr.update(visible=False),
        )

    try:
        if exercise == "Full Assistant":
            out, full_hist, meta = run_full_local(user_text, full_deps, full_hist)
            badge_html = make_badge(meta)

            # If assistant wrote/deleted files, your local backend can include meta keys too (optional)
            created = meta.get("created_file") if isinstance(meta, dict) else None
            deleted = meta.get("deleted_file") if isinstance(meta, dict) else None

            if getattr(full_deps, "selected_file", None):
                file_status_html = f"<div class='model-badge'>Selected file: <span class='model-pill'>{full_deps.selected_file}</span></div>"
                file_bar_visible = True

            if created:
                proof_file = created
                file_status_html = f"<div class='model-badge'>File created: <span class='model-pill'>{created}</span></div>"
                file_bar_visible = True
                file_proof_wrap_visible = True
            elif deleted:
                proof_file = None
                file_status_html = f"<div class='model-badge'>File deleted: <span class='model-pill'>{deleted}</span></div>"
                file_bar_visible = True
                file_proof_wrap_visible = False

            chat = chat + [{"role": "user", "content": user_text}, {"role": "assistant", "content": out}]
            return (
                chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
                badge_html,
                proof_file,
                file_status_html,
                gr.update(visible=file_bar_visible),
                gr.update(visible=file_proof_wrap_visible),
            )

        out, ex2_hist, ex3_hist, ex4_hist, ex6_hist, meta = router(exercise, user_text, ex2_hist, ex3_hist, ex4_hist, ex6_hist)
        badge_html = make_badge(meta)
        chat = chat + [{"role": "user", "content": user_text}, {"role": "assistant", "content": out}]
        return (
            chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
            badge_html,
            proof_file,
            file_status_html,
            gr.update(visible=False),
            gr.update(visible=False),
        )

    except Exception as e:
        err = f"Error in {exercise}: {type(e).__name__}: {e}"
        chat = chat + [{"role": "user", "content": user_text}, {"role": "assistant", "content": err}]
        return (
            chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
            badge_html,
            proof_file,
            file_status_html,
            gr.update(visible=False),
            gr.update(visible=False),
        )

def on_clear():
    badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"
    return (
        [], "", None, None, None, None, [], None,
        badge_html,
        None,
        "",
        gr.update(visible=False),
        gr.update(visible=False),
    )

def main():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root, body, .gradio-container,
    #chatbox, #chatbox *,
    input, textarea, button, select {
      font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif !important;
      font-style: normal !important;
    }
    .gradio-container { max-width: 1280px !important; width: 100% !important; margin: 0 auto; }
    
    #app {
      height: 100dvh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 12px;
      padding: 6px 12px;
      box-sizing: border-box;
    }

    .panel { border-radius: 16px !important; border: 1px solid rgba(0,0,0,.06); background: #ffffff !important; box-shadow: none !important; }
    #model_badge .model-badge{
      display: inline-flex;
      align-items: center;
      gap: 2px;
      padding: 10px 2px;
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

    #main_row { min-height: 0; display:flex; gap:16px; align-items:stretch; margin-top: 30px !important; }
    #main_row > .column { min-height:0; display:flex; flex-direction:column; }

    /* make chat not leave huge empty space */
    #chatbox { flex: 1 1 auto !important; min-height: 0px !important; max-height: none !important; overflow:auto !important; }

    #inputbox { width: 100%; margin-bottom: 26px !important; }
    #inputbox .input_outer { background: #ffffff !important; }

    #actions_row { display:flex; justify-content: flex-end !important; gap: 12px !important; padding-top:6px; }
    #actions_row button { min-width:120px; border-radius:12px !important; }

    /* emoji toggle */
    #emoji_toggle button{
      min-width: 44px !important;
      width: 44px !important;
      padding: 0 !important;
    }

    /* prevent clipping */
    .panel { overflow: visible !important; }
    .panel * { overflow: visible !important; }

    /* hide chat header actions */
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

    #chatbox [class*="header"] [class*="right"],
    #chatbox [class*="header"] [class*="actions"],
    #chatbox [class*="header"] [class*="buttons"] {
      display: none !important;
    }

    /* floating emoji panel */
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
    #emoji_panel .emoji-btn button{
      min-width: 40px !important;
      width: 40px !important;
      height: 36px !important;
      padding: 0 !important;
      border-radius: 12px !important;
      font-size: 18px !important;
      line-height: 1 !important;
    }
    #emoji_panel .gr-row{
      flex-wrap: wrap !important;
      gap: 8px !important;
    }

    #main_row [data-testid="file-upload"] .wrap,
    #main_row [data-testid="file-upload"] .block,
    #main_row [data-testid="file-upload"] .upload,
    #main_row [data-testid="file-upload"] .file,
    #main_row [data-testid="file-upload"] .file-preview,
    #main_row [data-testid="file-upload"] .file-dropzone,
    #main_row [data-testid="file-upload"] .file-upload,
    #main_row [data-testid="file-upload"] .input-file {
      height: 120px !important;
      max-height: 120px !important;
      overflow: hidden !important;
    }

    /* compact uploader without hiding text */
    #uploader{
      height: 64px !important;
      max-height: 64px !important;
      overflow: hidden !important;
    }

    #uploader [data-testid="file-upload"]{
      height: 44px !important;
      max-height: 44px !important;
      min-height: 0 !important;
      padding: 8px 10px !important;
      overflow: hidden !important;
    }

    /* make dropzone content smaller so it fits */
    #uploader [data-testid="file-upload"] *{
      font-size: 12px !important;
      line-height: 1.1 !important;
    }

    /* shrink icon so it doesn't push text */
    #uploader [data-testid="file-upload"] svg{
      width: 18px !important;
      height: 18px !important;
    }
    #app .gr-markdown { margin-top: 0 !important; }
    #app .gr-markdown > *:first-child { margin-top: 0 !important; }

    #uploader [data-testid="file-upload"] p,
    #uploader [data-testid="file-upload"] span {
      display: none !important;
    }
    /* uploader -> button only */
    #uploader { height: auto !important; max-height: none !important; }

    #uploader [data-testid="file-upload"]{
      padding: 0 !important;
      border: none !important;
      background: transparent !important;
    }

    /* hide the big dropzone area */
    #uploader [data-testid="file-upload"] .file-dropzone,
    #uploader [data-testid="file-upload"] .file-upload,
    #uploader [data-testid="file-upload"] .upload,
    #uploader [data-testid="file-upload"] .wrap{
      display: none !important;
    }

    /* keep the button visible and small */
    #uploader button{
      height: 36px !important;
      min-height: 36px !important;
      padding: 0 12px !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
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
                <div style="text-align:center; padding: 6px 0 12px;">
                  <div style="font-size:28px; font-weight:800; letter-spacing:.2px;">
                    THRIVE 3.0 THE BEST LOCAL GPT
                  </div>
                  <div style="opacity:.75; margin-top:4px; ">
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
                        gr.Markdown("<div style='white-space: normal; line-height: 1.25;'>Choose 1 of 6 exercises or Full Assistant🦾.</div>")
                        uploaded = gr.File(label="", file_count="single", elem_id="uploader")

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

                    chatbot = gr.Chatbot(label="Chat", elem_id="chatbox", elem_classes=["panel"], autoscroll=True)
                    gr.HTML(
                        """
                        <script>
                        (function () {
                          const root = document;
                          function scrollChat() {
                            const el = root.querySelector("#chatbox");
                            if (!el) return;
                            el.scrollTop = el.scrollHeight;
                          }
                          // scroll on any click/submit/update (cheap + works)
                          const obs = new MutationObserver(() => scrollChat());
                          const target = root.querySelector("#chatbox");
                          if (target) obs.observe(target, {childList:true, subtree:true});
                          window.addEventListener("load", () => setTimeout(scrollChat, 50));
                        })();
                        </script>
                        """
                    )

            ex2_history = gr.State(None)
            ex3_history = gr.State(None)
            ex4_history = gr.State(None)
            ex6_history = gr.State(None)
            full_history = gr.State([])
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

        send.click(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, uploaded],
            outputs=[chatbot, user_box, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )
        user_box.submit(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, uploaded],
            outputs=[chatbot, user_box, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )
        clear.click(
            fn=on_clear,
            inputs=[],
            outputs=[chatbot, user_box, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap],
        )

        emoji_toggle.click(fn=toggle_emoji_panel, inputs=[emoji_open], outputs=[emoji_open, emoji_panel])
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