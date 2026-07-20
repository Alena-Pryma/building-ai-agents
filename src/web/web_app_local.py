import os
import subprocess
import sys

import gradio as gr
from rich.console import Console

from src.agent.local_agent.ex1_local import run_ex1_local
from src.agent.local_agent.ex2_local import run_ex2_local
from src.agent.local_agent.ex3_local import run_ex3_local
from src.agent.local_agent.ex4_local import run_ex4_local
from src.agent.local_agent.ex5_local import run_ex5_local
from src.agent.local_agent.ex6_local import run_ex6_local

from pathlib import Path

from src.agent.local_agent.full_assistant_local import run_full_local, AgentDeps

console = Console()


def format_file_label(path, prefix="Upload"):
    if not path:
        return f"{prefix}: no file"
    return f"{prefix}: {Path(str(path)).name}"


def make_button_file_label(path, prefix):
    return format_file_label(path, prefix=prefix)


def open_path_in_default_app(path):
    if not path:
        return False

    p = Path(str(path)).expanduser()
    if not p.exists():
        return False

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        elif os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:
        return False


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

def router(exercise: str, user_text: str, ex2_history, ex3_history, ex4_history, ex6_history):
    if exercise == "Exercise 1 (code)":
        out, meta = run_ex1_local(user_text)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 2 (history)":
        out, ex2_history, meta = run_ex2_local(user_text, ex2_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 3 (tools)":
        out, ex3_history, meta = run_ex3_local(user_text, ex3_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 4 (hooks)":
        out, ex4_history, meta = run_ex4_local(user_text, ex4_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 5 (reasoning)":
        out, meta = run_ex5_local(user_text)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    if exercise == "Exercise 6 (skills)":
        out, ex6_history, meta = run_ex6_local(user_text, ex6_history)
        return out, ex2_history, ex3_history, ex4_history, ex6_history, meta
    raise KeyError(exercise)

def on_upload(uploaded_file, full_deps):
    if full_deps is None:
        full_deps = AgentDeps(console=console)

    if uploaded_file is not None:
        path = getattr(uploaded_file, "name", None) or str(uploaded_file)
        full_deps.selected_file = path
    else:
        full_deps.selected_file = None

    upload_label = make_button_file_label(getattr(full_deps, "selected_file", None), "Upload")
    open_label = make_button_file_label(getattr(full_deps, "opened_file", None), "Open")
    return full_deps, upload_label, open_label


def on_open_file(selected_file, full_deps):
    if full_deps is None:
        full_deps = AgentDeps(console=console)

    if selected_file is None:
        full_deps.opened_file = None
    else:
        path = getattr(selected_file, "name", None) or str(selected_file)
        full_deps.opened_file = path
        open_path_in_default_app(path)

    upload_label = make_button_file_label(getattr(full_deps, "selected_file", None), "Upload")
    open_label = make_button_file_label(getattr(full_deps, "opened_file", None), "Open")
    return full_deps, upload_label, open_label


def on_send(exercise, user_text, chat, ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps, uploaded_file, opened_file):
    user_text = (user_text or "").strip()

    if full_deps is None:
        full_deps = AgentDeps(console=console)
    if full_hist is None:
        full_hist = []
    if ex2_hist is None:
        ex2_hist = None

    file_bar_visible = False
    file_status_html = ""
    file_proof_wrap_visible = False
    proof_file = None
    upload_label_md = make_button_file_label(getattr(full_deps, "selected_file", None), "Upload")
    open_label_md = make_button_file_label(getattr(full_deps, "opened_file", None), "Open")

    if uploaded_file is not None:
        path = getattr(uploaded_file, "name", None) or str(uploaded_file)
        full_deps.selected_file = path
        upload_label_md = make_button_file_label(full_deps.selected_file, "Upload")

    if opened_file is not None:
        path = getattr(opened_file, "name", None) or str(opened_file)
        full_deps.opened_file = path
        open_label_md = make_button_file_label(full_deps.opened_file, "Open")

    badge_html = "<div class='model-badge'>Model: <span class='model-pill'>—</span></div>"

    if not user_text:
        return (
            chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
            badge_html,
            proof_file,
            file_status_html,
            gr.update(visible=file_bar_visible),
            gr.update(visible=file_proof_wrap_visible),
            upload_label_md,
            open_label_md,
        )

    if user_text.lower() in {"exit", "quit"}:
        return (
            [], "", None, None, None, None, [], full_deps,
            badge_html,
            None,
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            "Upload: no file",
            "Open: no file",
        )

    try:
        if exercise == "Full Assistant Local":
            out, full_hist, meta = run_full_local(user_text, full_deps, full_hist)
            badge_html = make_badge(meta)

            created = meta.get("created_file") if isinstance(meta, dict) else None
            deleted = meta.get("deleted_file") if isinstance(meta, dict) else None
            used_skill = meta.get("used_skill") if isinstance(meta, dict) else None
            last_tool = meta.get("last_tool") if isinstance(meta, dict) else None

            if used_skill:
                file_status_html = (
                    "<div class='model-badge'>"
                    f"Used skill: <span class='model-pill'>{Path(str(used_skill)).name}</span>"
                    + (f"&nbsp;&nbsp;Tool: <span class='model-pill'>{last_tool}</span>" if last_tool else "")
                    + "</div>"
                )
                file_bar_visible = True
            elif created:
                proof_file = created
                nice_name = Path(created).name
                file_status_html = (
                    "<div class='model-badge'>"
                    f"File created: <span class='model-pill'>{nice_name}</span>"
                    + (f"&nbsp;&nbsp;Tool: <span class='model-pill'>{last_tool}</span>" if last_tool else "")
                    + "</div>"
                )
                file_bar_visible = True
                file_proof_wrap_visible = True
            elif deleted:
                proof_file = None
                file_status_html = (
                    "<div class='model-badge'>"
                    f"File deleted: <span class='model-pill'>{deleted}</span>"
                    + (f"&nbsp;&nbsp;Tool: <span class='model-pill'>{last_tool}</span>" if last_tool else "")
                    + "</div>"
                )
                file_bar_visible = True
                file_proof_wrap_visible = False
            elif last_tool:
                file_status_html = (
                    "<div class='model-badge'>"
                    f"Tool: <span class='model-pill'>{last_tool}</span>"
                    "</div>"
                )
                file_bar_visible = True

            chat = chat + [{"role": "user", "content": user_text}, {"role": "assistant", "content": out}]
            return (
                chat, "", ex2_hist, ex3_hist, ex4_hist, ex6_hist, full_hist, full_deps,
                badge_html,
                proof_file,
                file_status_html,
                gr.update(visible=file_bar_visible),
                gr.update(visible=file_proof_wrap_visible),
                upload_label_md,
                open_label_md,
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
            upload_label_md,
            open_label_md,
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
            upload_label_md,
            open_label_md,
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
        "Upload: no file",
        "Open: no file",
    )

# FIT_JS measures the *actual* pixel space left in the viewport and sets that as the #chatbox height directly.
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

# JS run right after chat state updates: re-fits the chat box then scrolls it to the very last message.
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
       Two earlier CSS-only attempts (pure flex+height:0, then sticky
       footer) both depended on assumptions about Gradio's internal DOM
       that turned out wrong for this version, causing the footer to
       overlap the chat / sit below the fold.
       This version does not guess: JS (see FIT_JS below) measures the
       ACTUAL pixel space available — window height minus header minus
       footer minus sidebar/badge — and sets #chatbox's height directly
       in pixels. A pixel height set via inline style always wins over
       content size, regardless of what Gradio nests inside it. */
    #app {
      width: 100%;
      height: 100dvh;
      padding: 6px 16px;
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

    /* Height is set by JS at runtime (in px) — these are just safe
       fallbacks before JS runs on first paint */
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
    .gradio-container > .wrap { background: #f8f9fb !important; padding: 0 !important; }

    button { border-radius: 14px !important; }
    input, textarea { border-radius: 14px !important; }

    #inputbox { width: 100%; }
    #inputbox .input_outer { background: #ffffff !important; }

    /* emoji toggle */
    #emoji_toggle button{
      min-width: 44px !important;
      width: 44px !important;
      padding: 0 !important;
    }

    /* Allow panels to clip their own scroll content, but not clip popovers */
    .panel { overflow: visible; }

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

    /* Compact uploader */
    #uploader{
      height: auto !important;
      max-height: none !important;
    }

    #uploader [data-testid="file-upload"]{
      padding: 0 !important;
      border: none !important;
      background: transparent !important;
    }
    /* Hide the big dropzone area, keep a compact button */
    #uploader [data-testid="file-upload"] .file-dropzone,
    #uploader [data-testid="file-upload"] .file-upload,
    #uploader [data-testid="file-upload"] .upload,
    #uploader [data-testid="file-upload"] .wrap{
      display: none !important;
    }
    #uploader [data-testid="file-upload"] p,
    #uploader [data-testid="file-upload"] span {
      display: none !important;
    }
    #uploader button{
      height: 36px !important;
      min-height: 36px !important;
      padding: 0 12px !important;
      border-radius: 12px !important;
      font-weight: 600 !important;
    }
    #uploader .border-dashed {
      border: none !important;
      padding: 0 !important;
      min-height: 0 !important;
    }
    #uploader .border-dashed > * {
      display: none !important;
    }
    #uploader [data-testid="file-upload"] {
      padding-top: 4px !important;
      padding-bottom: 4px !important;
    }

    #app .gr-markdown { margin-top: 0 !important; }
    #app .gr-markdown > *:first-child { margin-top: 0 !important; }

    /* Hide Gradio built-in icons (share / delete / copy) */
    button[aria-label="Share"],
    button[aria-label="Delete"],
    button[aria-label="Copy"],
    button[title="Share"],
    button[title="Delete"],
    button[title="Copy"],
    a[aria-label="Share"],
    a[aria-label="Delete"],
    a[aria-label="Copy"]{
      display: none !important;
    }
    [class*="toolbar"] button,
    [class*="toolbar"] a,
    [class*="toolbar"] svg,
    [class*="header"] button,
    [class*="header"] a,
    [class*="header"] svg{
      display: none !important;
    }

    #chatbox button[aria-label="Share"],
    #chatbox button[aria-label="Delete"],
    #chatbox button[aria-label="Copy"],
    #chatbox button[title="Share"],
    #chatbox button[title="Delete"],
    #chatbox button[title="Copy"],
    #chatbox [class*="toolbar"] button,
    #chatbox [class*="toolbar"] a,
    #chatbox [class*="toolbar"] svg,
    #chatbox [class*="header"] button,
    #chatbox [class*="header"] a,
    #chatbox [class*="header"] svg{
      display: none !important;
    }

    #inputbox button[aria-label="Copy"],
    #inputbox button[title="Copy"],
    #inputbox .copy-button,
    #inputbox .gr-copy-button {
      display: none !important;
    }

    #actions_row{
      padding: 4px 12px 6px !important;
    }
    #actions_row button{
      margin: 0 !important;
    }
    /* Upload file button */
    #uploader, #open_btn {
      display: inline-flex !important;
      justify-content: center !important;
      align-items: center !important;
      padding: 0 18px !important;
      height: 36px !important;
      border-radius: 999px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      flex: 1 1 0 !important;
      min-width: 0 !important;
    }

    #uploader button, #open_btn button{
      width: 100% !important;
      height: 36px !important;
      min-height: 36px !important;
      border-radius: 999px !important;
      font-weight: 600 !important;
      border: 1px solid var(--button-primary-border-color, transparent) !important;
      background: var(--button-primary-background-fill, var(--button-primary-background, inherit)) !important;
      color: var(--button-primary-text-color, inherit) !important;
    }

    #uploader *, #open_btn * {
      color: inherit !important;
    }

    #file_action_row {
      gap: 8px !important;
      align-items: stretch !important;
    }

    #upload_action, #open_action {
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
      gap: 6px !important;
      flex: 1 1 0 !important;
      min-width: 0 !important;
    }

    #file_action_row .gr-button {
      width: 100% !important;
    }

    #upload_file_name_line, #open_file_name_line {
      margin-top: 0 !important;
      font-size: 12px !important;
      color: rgba(0,0,0,.65) !important;
      min-height: 18px !important;
      text-align: center !important;
      line-height: 1.3 !important;
    }

    """

    with gr.Blocks(
        title="THRIVE 3.0 THE BEST GPT — Python Coding Assistant",
    ) as demo:

        with gr.Group(elem_id="app"):
            with gr.Column(elem_id="app_header"):
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
                            choices=[
                                "Exercise 1 (code)",
                                "Exercise 2 (history)",
                                "Exercise 3 (tools)",
                                "Exercise 4 (hooks)",
                                "Exercise 5 (reasoning)",
                                "Exercise 6 (skills)",                                 
                                "Full Assistant Local",
                                 ],
                            value="Exercise 1 (code)",
                            label="Mode",
                        )
                        gr.Markdown("<div style='white-space: normal; line-height: 1.25; text-align:center;'>Choose 1 of 6 exercises or Full Assistant🦾.</div>")
                        with gr.Row(elem_id="file_action_row"):
                            with gr.Column(elem_id="upload_action"):
                                uploaded = gr.UploadButton(label="Upload", file_count="single", elem_id="uploader", variant="primary")
                                upload_file_name_line = gr.Markdown(value="Upload: no file", elem_id="upload_file_name_line")
                            with gr.Column(elem_id="open_action"):
                                opened = gr.UploadButton(label="Open", file_count="single", elem_id="open_btn", variant="primary")
                                open_file_name_line = gr.Markdown(value="Open: no file", elem_id="open_file_name_line")

                with gr.Column(scale=3, min_width=520, elem_id="chat_col"):
                    model_badge = gr.Markdown(
                        value="<div class='model-badge'>Model: <span class='model-pill'>—</span></div>",
                        elem_id="model_badge",
                    )
                    file_bar = gr.Group(visible=False, elem_classes=["panel", "filebar"])
                    with file_bar:
                        file_status = gr.Markdown(value="")
                        file_proof_wrap = gr.Group(visible=False, elem_id="file_proof_wrap")
                        with file_proof_wrap:
                            file_proof = gr.File(label="Download", interactive=True)

                    chatbot = gr.Chatbot(
                        label="Chat",
                        elem_id="chatbox",
                        elem_classes=["panel"],
                        autoscroll=True,
                    )

            with gr.Column(elem_id="footer_area"):
                ex2_history = gr.State(None)
                ex3_history = gr.State(None)
                ex4_history = gr.State(None)
                ex6_history = gr.State(None)
                full_history = gr.State([])
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

        io_list = [chatbot, user_box, ex2_history, ex3_history, ex4_history, ex6_history,
                   full_history, full_deps, model_badge, file_proof, file_status, file_bar, file_proof_wrap,
                   upload_file_name_line, open_file_name_line]

        uploaded.change(
            fn=on_upload,
            inputs=[uploaded, full_deps],
            outputs=[full_deps, upload_file_name_line, open_file_name_line],
        )

        opened.change(
            fn=on_open_file,
            inputs=[opened, full_deps],
            outputs=[full_deps, upload_file_name_line, open_file_name_line],
        )

        send.click(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, uploaded, opened],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=SCROLL_JS)

        user_box.submit(
            fn=on_send,
            inputs=[exercise, user_box, chatbot, ex2_history, ex3_history, ex4_history, ex6_history, full_history, full_deps, uploaded, opened],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=SCROLL_JS)

        clear.click(
            fn=on_clear,
            inputs=[],
            outputs=io_list,
        ).then(fn=None, inputs=None, outputs=None, js=FIT_JS)

        emoji_toggle.click(fn=toggle_emoji_panel, inputs=[emoji_open], outputs=[emoji_open, emoji_panel]).then(fn=None, inputs=None, outputs=None, js=FIT_JS)
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
