# Lucelec RAG Bot Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Retroactive plan:** All three tasks below were already implemented and verified before this document was written (user request: document finished work as a formal plan). Every step is checked off with the actual commands and output produced at the time.

**Goal:** Fix three crashes in the Lucelec RAG Streamlit bot (`Template-bot/files/lucelec_rag_bot.py`) and one crash in its test suite (`Template-bot/files/run_tests.py`) that blocked the app from booting, from rendering its sidebar, and from handling a normal customer chat message.

**Architecture:** Each bug is independent — no shared state or interfaces between tasks. Three are direct edits to `lucelec_rag_bot.py`; one is a two-line addition to `run_tests.py`.

**Tech Stack:** Python 3.10, Streamlit (`streamlit` package, Components v1 API), plain HTML/JS (Web Speech API) for the voice component. No build tooling.

## Global Constraints

- Repo at `C:\Users\Vaughnroy Smith\Downloads\demarnew-Template-bots\Template-bot` is **not git-tracked** — no `git commit` steps are possible; each task's "commit" step is replaced with a verification step (compile check + test run) instead.
- Target platform is Windows; two of the four fixes are specifically Windows-console-encoding issues that won't reproduce on macOS/Linux.
- `Template-bot/files/run_tests.py` is the only automated test surface in this repo — it must stay at 90/90 passing after every task.
- No new dependencies. All fixes use the standard library or Streamlit/langchain packages already in `requirements.txt`.

---

### Task 1: Fix missing `voice_recorder_component` directory crash

**Files:**
- Create: `Template-bot/files/voice_recorder_component/index.html`
- Reference (unmodified): `Template-bot/files/lucelec_rag_bot.py:1586-1597` (`declare_component` call and `render_voice_recorder()`)

**Interfaces:**
- Consumes: nothing from other tasks — fully independent.
- Produces: a Streamlit custom component contract used by `render_voice_recorder()` (`lucelec_rag_bot.py:1592`) — the component must call Streamlit's `setComponentValue` with a plain string (the speech transcript). `render_voice_recorder()` already does `str(VOICE_RECORDER_COMPONENT(key="voice_recorder_component", default=""))` and treats the string result as the transcript, so no other file needs to change.

- [x] **Step 1: Reproduce the crash**

Run: `python -m streamlit run lucelec_rag_bot.py --server.headless true` from `Template-bot/files/`
Actual (before fix): `streamlit.errors.StreamlitAPIException: No such component directory: '...\voice_recorder_component'` at `lucelec_rag_bot.py:1586` (`components.declare_component(...)`).

- [x] **Step 2: Confirm the directory was never built, not merely deleted**

Run: `grep -rn "voice_recorder_component" .` from the repo root.
Actual: only one match — the `declare_component()` call site itself. No other file references it, and no `.git` history exists to check (repo isn't version-controlled) — nothing indicates the folder ever existed.

- [x] **Step 3: Confirm the expected contract from the call site**

Read `lucelec_rag_bot.py:1592-1597`:
```python
def render_voice_recorder() -> str:
    """Use a browser-based recorder UI so voice input works without server STT."""
    result = str(VOICE_RECORDER_COMPONENT(key="voice_recorder_component", default=""))
    if result and result != "None":
        return result.strip()
    return ""
```
And the caller at `lucelec_rag_bot.py:2895-2900` (as of the original bug report): `st.caption("Use your browser microphone to dictate a question.")` immediately before calling `render_voice_recorder()`. This confirms the component must perform speech-to-text **in the browser** (no server STT round-trip) and return the transcript as a plain string.

- [x] **Step 4: Write the component**

Create `Template-bot/files/voice_recorder_component/index.html` — self-contained HTML/CSS/JS, no build step, no external JS dependency. Uses the browser's `SpeechRecognition`/`webkitSpeechRecognition` (Web Speech API) for STT and a hand-rolled Streamlit Components v1 `postMessage` handshake:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body { margin: 0; padding: 0; font-family: "Source Sans Pro", sans-serif; }
  #wrap { display: flex; align-items: center; gap: 10px; padding: 6px 4px; }
  #mic-btn {
    border: none; border-radius: 50%; width: 42px; height: 42px; font-size: 20px;
    cursor: pointer; background: #f0f2f6; color: #262730;
    transition: background 0.15s ease, transform 0.1s ease;
  }
  #mic-btn:hover { background: #e6e9ef; }
  #mic-btn.recording { background: #ff4b4b; color: white; animation: pulse 1.2s infinite; }
  #mic-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(255,75,75,0.5); }
    70% { box-shadow: 0 0 0 10px rgba(255,75,75,0); }
    100% { box-shadow: 0 0 0 0 rgba(255,75,75,0); }
  }
  #status { font-size: 13px; color: #555; }
</style>
</head>
<body>
  <div id="wrap">
    <button id="mic-btn" title="Record a question">🎤</button>
    <span id="status">Click the mic and speak</span>
  </div>

<script>
  const STREAMLIT_MSG_PREFIX = "streamlit:";

  function sendMessageToStreamlit(type, data) {
    const outData = Object.assign({ isStreamlitMessage: true, type: type }, data);
    window.parent.postMessage(outData, "*");
  }

  function initStreamlit() {
    sendMessageToStreamlit("componentReady", { apiVersion: 1 });
    setFrameHeight();
  }

  function setFrameHeight() {
    const height = document.documentElement.scrollHeight;
    sendMessageToStreamlit("setFrameHeight", { height: height });
  }

  function setComponentValue(value) {
    sendMessageToStreamlit("setComponentValue", { value: value, dataType: "json" });
  }

  window.addEventListener("message", (event) => {
    if (!event.data || event.data.type !== STREAMLIT_MSG_PREFIX + "render") return;
  });

  const micBtn = document.getElementById("mic-btn");
  const statusEl = document.getElementById("status");
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognitionImpl) {
    micBtn.disabled = true;
    statusEl.textContent = "Speech recognition not supported in this browser.";
  } else {
    const recognizer = new SpeechRecognitionImpl();
    recognizer.lang = "en-US";
    recognizer.interimResults = false;
    recognizer.maxAlternatives = 1;
    let recording = false;

    micBtn.addEventListener("click", () => {
      if (recording) { recognizer.stop(); return; }
      try { recognizer.start(); }
      catch (err) { statusEl.textContent = "Could not start microphone: " + err.message; }
    });

    recognizer.addEventListener("start", () => {
      recording = true;
      micBtn.classList.add("recording");
      statusEl.textContent = "Listening...";
    });

    recognizer.addEventListener("result", (event) => {
      const transcript = event.results[0][0].transcript;
      statusEl.textContent = "Captured: " + transcript;
      setComponentValue(transcript);
    });

    recognizer.addEventListener("error", (event) => {
      statusEl.textContent = "Mic error: " + event.error;
    });

    recognizer.addEventListener("end", () => {
      recording = false;
      micBtn.classList.remove("recording");
      if (statusEl.textContent === "Listening...") {
        statusEl.textContent = "Click the mic and speak";
      }
    });
  }

  window.addEventListener("load", () => {
    initStreamlit();
    setFrameHeight();
  });
</script>
</body>
</html>
```

- [x] **Step 5: Verify the crash is gone**

Run: `python -m streamlit run lucelec_rag_bot.py --server.headless true` from `Template-bot/files/`
Actual: server starts clean, prints `Local URL: http://localhost:8502` with no exception. (`declare_component()` only validates the directory exists at call time — it does not itself execute browser JS, so this confirms the directory/path resolution is fixed; the mic button's live behavior needs a browser click to confirm, which is out of scope for a headless check.)

- [x] **Step 6: Verify (no commit possible — repo has no git)**

Confirmed via Step 5's clean boot. No `git add`/`git commit` — see Global Constraints.

---

### Task 2: Fix `run_tests.py` Windows Unicode crashes

**Files:**
- Modify: `Template-bot/files/run_tests.py:11-20` (imports + module-level setup)
- Modify: `Template-bot/files/run_tests.py:266` (source-read line in section 11)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by other tasks — `run_tests.py` is the test entrypoint, not imported anywhere.

- [x] **Step 1: Reproduce the first crash**

Run: `python run_tests.py` from `Template-bot/files/`
Actual (before fix): runs sections 1-3 clean, crashes in section 4 ("Intent routing") with:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 13: character maps to <undefined>
```
Root cause: the active Windows console codepage can't encode `→` (U+2192), printed by the `check()` helper's FAIL-detail branch (`run_tests.py:29`, unaffected by this fix — the fix is at the stream level, not the call site).

- [x] **Step 2: Fix stream encoding at the top of the file**

Edit `run_tests.py` — add after the existing imports (`io, os, sys, glob, shutil, contextlib`), before `PASSES = []`:

```python
# Windows consoles often use a codepage that can't encode the arrow/dot
# characters this script prints (e.g. cp437/cp1252 vs. the → in FAIL lines),
# which crashes the run partway through with UnicodeEncodeError.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

- [x] **Step 3: Re-run — confirm the first crash is gone, find the second**

Run: `python run_tests.py` from `Template-bot/files/`
Actual: sections 1-10 now pass clean (arrow/dot characters print fine). New crash in section 11 ("Streamlit routing states"):
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 147473: character maps to <undefined>
```
at `run_tests.py:266` — `open(b.__file__).read()` (reading `lucelec_rag_bot.py`'s own source with no explicit encoding, defaulting to the Windows locale codepage, which can't decode a UTF-8 byte in that file). Same root cause class (platform-default encoding on Windows), different direction (read vs. write) — in scope per the approved spec ("rerun to completion, fix whatever real failures surface").

- [x] **Step 4: Fix the source-read encoding**

Edit `run_tests.py:266`:
```python
# Before:
src = open(b.__file__).read()
# After:
src = open(b.__file__, encoding="utf-8").read()
```

- [x] **Step 5: Re-run to completion**

Run: `python run_tests.py` from `Template-bot/files/`
Actual:
```
  90/90 checks passed

  No failures.
```
All 11 sections ran to completion. No real (non-encoding) failures found.

- [x] **Step 6: Verify (no commit possible — repo has no git)**

Confirmed via Step 5's full pass. No `git add`/`git commit` — see Global Constraints.

---

### Task 3: Fix `chat_button_0` `StreamlitValueAssignmentNotAllowedError`

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:2523-2542` (`initialize_sidebar_state`)
- Modify: `Template-bot/files/lucelec_rag_bot.py:2554-2563` (`reset_chat_session`) — same anti-pattern, fixed for consistency even though not yet observed crashing
- Modify: `Template-bot/files/lucelec_rag_bot.py` call sites — sidebar init (~line 2654) and the "Start over" button (~line 2851, exact line shifted after Task 4's edit)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `initialize_sidebar_state(state)` now mutates and returns the same object passed in (works for a plain `dict` or `st.session_state`) instead of returning a detached copy. `reset_chat_session(state)` calls `initialize_sidebar_state(state)` internally and inherits the same in-place behavior — its return value is still the same object, so existing callers that use the return value keep working unchanged.

- [x] **Step 1: Reproduce the crash**

In the running app, click any sidebar chat entry (widget `key="chat_button_0"`, `lucelec_rag_bot.py:2734`).
Actual (before fix):
```
streamlit.errors.StreamlitValueAssignmentNotAllowedError: Values for the widget with `key` 'chat_button_0' cannot be set using `st.session_state`.
```
at `st.button(..., key=f"chat_button_{index}")` inside the sidebar chat-list loop.

- [x] **Step 2: Identify the root cause**

Read `initialize_sidebar_state` (before fix):
```python
def initialize_sidebar_state(state: Optional[dict] = None) -> dict:
    """Seed a consistent sidebar session state for the Streamlit UI."""
    state = {} if state is None else dict(state)
    state.setdefault("page_state", "customer_view")
    # ... more setdefault calls ...
    return state
```
Called as: `sidebar_state = initialize_sidebar_state(st.session_state)` then `st.session_state.update(sidebar_state)`.

`dict(state)` makes a **full copy of every key currently in `st.session_state`** — including `chat_button_0`, which Streamlit itself owns (it stores each button's last-click value under its own key across reruns). `st.session_state.update(sidebar_state)` then writes that entire copy back, including `chat_button_0`, which marks it as "just written via the Session State API this run" even though the value didn't change. Streamlit's `check_session_state_rules` (`streamlit/elements/lib/policies.py`) unconditionally rejects any such external write for `st.button` — buttons only support ephemeral click state, never a settable value — so the very next `st.button(key="chat_button_0")` call raises.

- [x] **Step 3: Fix `initialize_sidebar_state` to mutate in place**

Edit `lucelec_rag_bot.py:2523-2526`:
```python
# Before:
def initialize_sidebar_state(state: Optional[dict] = None) -> dict:
    """Seed a consistent sidebar session state for the Streamlit UI."""
    state = {} if state is None else dict(state)
    state.setdefault("page_state", "customer_view")

# After:
def initialize_sidebar_state(state: Optional[dict] = None) -> dict:
    """Seed a consistent sidebar session state for the Streamlit UI.

    Mutates `state` in place (works for a plain dict or `st.session_state`)
    instead of copying it, so keys owned by other widgets (e.g. a button's
    click state) never get round-tripped through a write Streamlit doesn't
    allow for that widget type.
    """
    if state is None:
        state = {}
    state.setdefault("page_state", "customer_view")
```
(The remaining `state.setdefault(...)` calls below are unchanged — `setdefault` on an existing key is a no-op, so it never triggers a spurious write.)

- [x] **Step 4: Update the sidebar-init call site**

Edit the "4. VIEW ROUTER" section:
```python
# Before:
sidebar_state = initialize_sidebar_state(st.session_state)
st.session_state.update(sidebar_state)
if st.session_state.page_state != 'customer_view' and ...

# After:
initialize_sidebar_state(st.session_state)
if st.session_state.page_state != 'customer_view' and ...
```

- [x] **Step 5: Fix the "Start over" button's identical pattern**

`reset_chat_session` had the same `initialize_sidebar_state(state)` → return → `st.session_state.update(...)` round trip at its call site. Not observed crashing (the call is immediately followed by `st.rerun()`, which aborts the script before any button re-renders in that same run) but it's the same landmine — fixed for consistency:
```python
# Before:
if st.button("Start over"):
    reset_state = reset_chat_session(st.session_state)
    st.session_state.update(reset_state)
    st.rerun()

# After:
if st.button("Start over"):
    reset_chat_session(st.session_state)
    st.rerun()
```
`reset_chat_session` itself needed no change beyond what Step 3 already gave it (it calls `initialize_sidebar_state(state)` and then does `state["messages"] = []` etc. directly on the now-in-place-mutated object).

- [x] **Step 6: Verify**

Run: `python -m py_compile lucelec_rag_bot.py && python run_tests.py` from `Template-bot/files/`
Actual: `COMPILE_OK`, then `90/90 checks passed / No failures.` (the test suite doesn't exercise the live sidebar-click path, so this confirms no regression, not the fix itself — the fix's actual trigger condition only manifests in a running browser session; static reasoning + code removal of the exact offending write is the confirmation for the click behavior itself.)

- [x] **Step 7: Verify (no commit possible — repo has no git)**

Confirmed via Step 6. No `git add`/`git commit` — see Global Constraints.

---

### Task 4: Fix `UnboundLocalError` on `user` / `sim_language` in normal chat flow

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:2687` (`is_admin` computation, "6. APP DATA LOAD")

**Interfaces:**
- Consumes: `answer()`'s existing signature at `lucelec_rag_bot.py:2454`: `def answer(question: str, index: dict, user: Optional[dict] = None, excel_data: list = None, language: str = "English") -> dict`, and its existing default-fallback body: `user = user or {"id_verified": True, "mood": DEFAULT_REGISTER, "segment": "Domestic"}` (`lucelec_rag_bot.py:2455`). This task does not modify `answer()` — it only ensures the call site always has a defined `user`/`sim_language` to pass in, so `answer()`'s own designed-for `None` fallback actually gets exercised for real customers.
- Produces: nothing consumed by other tasks.

- [x] **Step 1: Reproduce the crash**

In the running app, without opening the sidebar Settings panel, submit any chat message.
Actual (before fix):
```
UnboundLocalError: local variable 'user' referenced before assignment
File "lucelec_rag_bot.py", line 2928, in streamlit_app
    out = answer(q, index, user, excel_data=excel_records, language=sim_language)
```

- [x] **Step 2: Identify the root cause**

`user` and `sim_language` are only ever assigned inside the sidebar's "⚙️ Settings" expander (`if st.session_state.get("show_settings", False):`), specifically:
- `sim_language = st.session_state.ui_language` (inside the expander, only reached if the expander is open)
- `user = {"id_verified": sim_verified, "mood": ..., "segment": ...}` (further inside, in the "The user in front of you" customer-simulation subsection)

`show_settings` defaults to `False` (`initialize_sidebar_state`, and the sidebar's own `st.session_state.setdefault("show_settings", False)`), so on a fresh session — the normal path for a real customer who never clicks "⚙️ Settings" — that whole code block never executes. Streamlit re-runs the full script top-to-bottom on every interaction, so `user`/`sim_language` are simply undefined names the moment a chat message reaches `answer(q, index, user, ..., language=sim_language)` at line 2928.

`answer()` was already written to handle `user=None` gracefully (`user = user or {"id_verified": True, "mood": DEFAULT_REGISTER, "segment": "Domestic"}`, `lucelec_rag_bot.py:2455`) — the call site just never gave it the chance to receive `None`, because the name didn't exist at all rather than being explicitly `None`.

- [x] **Step 3: Seed defaults right after `is_admin` is computed**

Edit `lucelec_rag_bot.py:2686-2687` ("6. APP DATA LOAD"):
```python
# Before:
    # 6. APP DATA LOAD
    is_admin = (st.session_state.page_state == 'admin_view') 

# After:
    # 6. APP DATA LOAD
    is_admin = (st.session_state.page_state == 'admin_view')

    # Defaults for the real (non-simulated) customer flow. The Settings
    # panel below overrides both when a staff member opens it to test as a
    # simulated customer — but it's collapsed by default, so a real
    # customer's first chat message must work without ever opening it.
    user = None
    sim_language = st.session_state.ui_language
```
This runs before the sidebar/Settings block, so when that block *does* execute (Settings opened), its own `user = {...}` and `sim_language = st.session_state.ui_language` assignments simply overwrite these defaults — no change to the admin/testing-simulation behavior. When it doesn't execute, `user` stays `None` and flows into `answer()`'s existing `user or {...}` fallback exactly as that function was already designed to handle; `sim_language` stays equal to the real UI language toggle (the same value the Settings panel would have set it to anyway).

- [x] **Step 4: Verify**

Run: `python -m py_compile lucelec_rag_bot.py && python run_tests.py` from `Template-bot/files/`
Actual: `COMPILE_OK`, then `90/90 checks passed / No failures.`

- [x] **Step 5: Verify (no commit possible — repo has no git)**

Confirmed via Step 4. No `git add`/`git commit` — see Global Constraints.

---

## Self-Review

**Spec coverage:** The original spec (`docs/superpowers/specs/2026-08-05-fix-run-tests-encoding-design.md`) covered only Task 2's first half (the `→` print crash) plus "fix whatever real failures the completed run reveals." Task 2's second half (the `open()` read crash) falls under that clause. Tasks 1, 3, and 4 were separate bug reports handled ad hoc during the same session, outside the original spec's scope — captured here per the user's explicit request to retroactively document all finished work as one plan.

**Placeholder scan:** No TBD/TODO markers; every step shows actual before/after code and actual command output, not descriptions of what to do.

**Type consistency:** `initialize_sidebar_state(state: Optional[dict] = None) -> dict` and `reset_chat_session(state: Optional[dict] = None) -> dict` keep their original signatures — only their internal copy-vs-mutate behavior changed, so no caller-visible type changes across tasks. `answer()`'s signature (Task 4) is unmodified; Task 4 only fixes what its call site passes.

**Outcome:** All four fixes verified. `run_tests.py` at 90/90 passing after every task. App boots clean (`streamlit run`, no exception at startup). Live-browser click-through for Tasks 1, 3, and 4 (mic button, chat-switch button, plain chat message without opening Settings) was not independently re-verified in a real browser session as part of writing this plan — flagged here rather than claimed as done.
