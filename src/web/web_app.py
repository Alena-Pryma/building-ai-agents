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
        "Exercise 1 (code)": run_ex1,
        "Exercise 3 (tools)": run_ex3,
        "Exercise 4 (hooks)": run_ex4,
        "Exercise 5 (reasoning)": run_ex5,
        "Exercise 6 (skills)": run_ex6,
    }
    fn = mapping[exercise]
    result = fn(user_text)

    if isinstance(result, tuple) and len(result) == 3:
        out, _messages, meta = result
        return out, meta
    
    if isinstance(result, tuple) and len(result) == 2:
        out, meta = result
        return out, meta

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
def add_emoji_4(t): return add_emoji_and_close(t, "👍")
def add_emoji_5(t): return add_emoji_and_close(t, "👎")
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
        if exercise == "Exercise 2 (history)":
            output, new_hist = run_ex2(message, ex2_history)
            return output, new_hist, full_history, full_deps
        
        if exercise == "Full Assistant (API)":
            output, new_hist, meta = run_full(message, full_deps, full_history)
            return output, ex2_history, new_hist, full_deps
        
        return router(exercise, message), ex2_history, full_history, full_deps

    except Exception as e:
        return f"Error in {exercise}: {type(e).__name__}: {e}", ex2_history, full_history, full_deps

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
        return chat, "", ex2_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update
 
    if user_text.lower() in {"exit", "quit"}:
        return [], "", None, None, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update
 
    try:
        if exercise == "Exercise 2 (history)":
            out, new_hist, meta = run_ex2(user_text, ex2_hist)
            badge_html = make_badge(meta)
            chat = chat + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": out},
            ]
            return chat, "", new_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update
 
        if exercise == "Full Assistant (API)":
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
 
    except Exception as e:
        err = f"Error in {exercise}: {type(e).__name__}: {e}"
        chat = chat + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": err},
        ]
        return chat, "", ex2_hist, full_hist, full_deps, badge_html, proof_file, file_status_html, file_bar_update, file_proof_wrap_update
 
def on_clear():
    badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"
    return [], "", None, None, None, badge_html, None, "", gr.update(visible=False), gr.update(visible=False)
 
# FIT_JS measures the *actual* pixel space left in the viewport (window
# height minus the header row minus the footer row minus paddings) and
# sets that as the #chatbox height directly, in pixels. A pixel height
# set this way always wins, no matter what Gradio nests inside #chatbox
# or how its internal classes are named — that's what makes this robust
# across Gradio versions, unlike pure-CSS flex/percentage tricks.
FIT_JS = """
() => {
    function fitChat() {
        const app = document.querySelector('#app');
        const header = document.querySelector('#app_header');
        const footer = document.querySelector('#footer_area');
        const chat = document.querySelector('#chatbox');
        if (!app || !header || !footer || !chat) return;
 
        const viewportH = window.innerHeight;
        const chatTop = chat.getBoundingClientRect().top;
        const footerH = footer.getBoundingClientRect().height;
        const margin = 16; // small breathing room at the very bottom
        const available = Math.max(160, Math.round(viewportH - chatTop - footerH - margin));
 
        chat.style.height = available + 'px';
        chat.style.maxHeight = available + 'px';
        chat.style.overflowY = 'auto';
    }
 
    // expose globally so every later .then(js=...) call can reuse it
    // without re-declaring the function each time
    window.__fitChat = fitChat;
 
    if (!window.__fitChatInstalled) {
        window.__fitChatInstalled = true;
        window.addEventListener('resize', fitChat);
        // Gradio can change header/footer height (file bar showing/hiding,
        // textbox growing) without a window resize event, so also re-fit
        // on a light interval as a safety net.
        setInterval(fitChat, 700);
        const obs = new MutationObserver(() => fitChat());
        const target = document.querySelector('#app') || document.body;
        obs.observe(target, { childList: true, subtree: true, attributes: true });
    }
 
    fitChat();
    requestAnimationFrame(fitChat);
    setTimeout(fitChat, 100);
    setTimeout(fitChat, 400);
}
"""
 
# JS run right after chat state updates: re-fits the chat box (in case the
# footer grew/shrank) then scrolls it to the very last message. Runs via
# .then(..., js=...) so it fires *after* Gradio has already patched the DOM.
SCROLL_JS = """
() => {
    if (window.__fitChat) window.__fitChat();
    function scrollNow() {
        const box = document.querySelector('#chatbox');
        if (!box) return;
        box.scrollTop = box.scrollHeight;
    }
    scrollNow();
    requestAnimationFrame(scrollNow);
    setTimeout(scrollNow, 60);
    setTimeout(scrollNow, 200);
    setTimeout(scrollNow, 500);
    setTimeout(scrollNow, 900);
}
"""
 
def main():
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
 
    :root, body, .gradio-container,
    #chatbox, #chatbox *,
    input, textarea, button, select {
      font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif !important;
      font-style: normal !important;
    }
    html, body { margin: 0; height: 100%; overflow: hidden; } /* page itself never scrolls; JS sizes #chatbox to fit exactly */
    .gradio-container { max-width: 100% !important; width: 100% !important; margin: 0; height: 100dvh; overflow: hidden; }
 
    /* ---------- MAIN APP SHELL ----------
       JS (FIT_JS) measures the ACTUAL pixel space available — window
       height minus header minus footer minus sidebar/badge — and sets
       #chatbox's height directly in pixels. A pixel height set via
       inline style always wins over content size, regardless of what
       Gradio nests inside it internally. */
    #app {
      width: 100%;
      height: 100dvh;
      padding: 6px 12px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
 
    #app_header { flex: 0 0 auto; }
 
    #main_row {
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      gap: 16px;
      align-items: stretch;
      width: 100%;
      margin-top: 4px !important;
    }
    #main_row > .column { min-height: 0; display: flex; flex-direction: column; }
    #chat_col { min-height: 0; flex: 1 1 auto; display: flex; flex-direction: column; gap: 8px; }
    #model_badge, .filebar { flex: 0 0 auto; }
 
    /* height is set by JS at runtime (in px) — this is just a safe
       fallback before JS runs on first paint */
    #chatbox {
      overflow-y: auto !important;
      overflow-x: hidden;
      min-height: 120px;
    }
 
    #footer_area {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-top: 6px;
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
    .gradio-container > .wrap { background: #f8f9fb !important; padding: 0 !important; }
 
    button { border-radius: 14px !important; }
    input, textarea { border-radius: 14px !important; }
 
    #inputbox { width: 100%; }
    #inputbox .input_outer { background: #ffffff !important; }
 
    #actions_row { display:flex; justify-content: flex-end !important; gap: 12px !important; padding-top:6px; }
    #actions_row button { min-width:120px; border-radius:12px !important; }
 
    /* emoji must be compact */
    #emoji_toggle button{
      min-width: 44px !important;
      width: 44px !important;
      height: 44px !important;
      padding: 0 !important;
      font-size: 20px !important;
    }
 
    #file_bar .panel { padding: 10px 12px; }
 
    /* allow panels to clip their own scroll content, but not clip popovers */
    .panel { overflow: visible; }
 
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
    #chatbox [class*="header"] [class*="right"],
    #chatbox [class*="header"] [class*="actions"],
    #chatbox [class*="header"] [class*="buttons"] {
      display: none !important;
    }
 
    /* Floating emoji panel */
    #emoji_panel{
      position: fixed;
      right: 18px;
      bottom: 96px;
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
    #emoji_panel .row{ gap: 8px !important; }
    #emoji_panel .gr-row{ gap: 8px !important; flex-wrap: nowrap !important; align-items: center !important; }
    #emoji_panel .gr-column{ gap: 0 !important; }
    #emoji_panel .emoji-btn button{
      min-width: 40px !important;
      width: 40px !important;
      height: 36px !important;
      padding: 0 !important;
      border-radius: 12px !important;
      font-size: 18px !important;
      line-height: 1 !important;
    }
    #emoji_panel .gr-button{ flex: 0 0 auto !important; }
    #emoji_panel .gr-form{ width: auto !important; }
 
    .emoji-toggle-btn{
      width:44px;height:44px;border-radius:14px;
      border:1px solid rgba(0,0,0,.08);
      background:#fff;
      font-size:20px;
      cursor:pointer;
    }
    """
 
    with gr.Blocks(
        title="THRIVE 3.0 THE BEST GPT — Python Coding Assistant",
    ) as demo:
 
        with gr.Group(elem_id="app"):
            with gr.Column(elem_id="app_header"):
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
                            choices=[
                                "Exercise 1 (code)",
                                "Exercise 2 (history)",
                                "Exercise 3 (tools)",
                                "Exercise 4 (hooks)",
                                "Exercise 5 (reasoning)",
                                "Exercise 6 (skills)",                                 
                                "Full Assistant (API)",
                                 ],
                            value="Exercise 1 (code)",
                            label="Mode",
                        )
                        gr.Markdown("<div style='white-space: normal; line-height: 1.25; text-align:center;'>Choose 1 of 6 exercises or the Full Assistant.</div>")
 
                with gr.Column(scale=3, min_width=520, elem_id="chat_col"):
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
 
                    chatbot = gr.Chatbot(
                        label="Chat",
                        elem_id="chatbox",
                        elem_classes=["panel"],
                        autoscroll=True,
                    )
 
            with gr.Column(elem_id="footer_area"):
                ex2_history = gr.State(None)
                full_history = gr.State(None)
                full_deps = gr.State(None)
                emoji_open = gr.State(False)
 
                user_box = gr.Textbox(
                    label="Your message",
                    placeholder="Ask your question…",
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
                        e4 = gr.Button("👍", elem_classes=["emoji-btn"])
                        e5 = gr.Button("👎", elem_classes=["emoji-btn"])
                        e6 = gr.Button("🙏", elem_classes=["emoji-btn"])
                        e7 = gr.Button("🔥", elem_classes=["emoji-btn"])
                        e8 = gr.Button("🎉", elem_classes=["emoji-btn"])
                        e9 = gr.Button("❤️", elem_classes=["emoji-btn"])
 
                with gr.Row(elem_id="actions_row"):
                    send = gr.Button("Send", variant="primary")
                    clear = gr.Button("Clear")
                    emoji_toggle = gr.Button("🙂", elem_id="emoji_toggle", scale=0)
 
        io_list = [chatbot, user_box, ex2_history, full_history, full_deps,
                   model_badge, file_proof, file_status, file_bar, file_proof_wrap]
 
        send.click(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, full_history, full_deps],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=SCROLL_JS)
 
        user_box.submit(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, full_history, full_deps],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=SCROLL_JS)
 
        clear.click(
            fn=on_clear,
            inputs=[],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=FIT_JS)
 
        emoji_toggle.click(
            fn=toggle_emoji_panel,
            inputs=[emoji_open],
            outputs=[emoji_open, emoji_panel],
        ).then(fn=None, inputs=None, outputs=None, js=FIT_JS)

        e1.click(fn=add_emoji_1, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e2.click(fn=add_emoji_2, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e3.click(fn=add_emoji_3, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e4.click(fn=add_emoji_4, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e5.click(fn=add_emoji_5, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e6.click(fn=add_emoji_6, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e7.click(fn=add_emoji_7, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e8.click(fn=add_emoji_8, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])
        e9.click(fn=add_emoji_9, inputs=[user_box], outputs=[user_box, emoji_open, emoji_panel])

        demo.load(fn=None, inputs=None, outputs=None, js=FIT_JS)
 
    demo.launch(theme=gr.themes.Soft(), css=css)
 

if __name__ == "__main__":
    main()
