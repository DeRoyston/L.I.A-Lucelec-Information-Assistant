# Lucelec Bot UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the six UI bugs and ship the two polish features described in `docs/superpowers/specs/2026-08-07-lucelec-ui-polish-design.md` — missing footer, logo white-box, dark-mode title regression, accessibility CSS bug, voice-widget dark-mode gap, broken mic glyph, LLM-generated chat titles, and light animation/outline polish.

**Architecture:** Single file (`Template-bot/files/lucelec_rag_bot.py`) plus one existing asset file (`Template-bot/files/voice_recorder_component/index.html`). No new dependencies, no new modules. CSS additions live in two constants already established by the codebase's own pattern: `DARK_MODE_CSS` (dark-theme overrides) and a new `POLISH_CSS` (theme-neutral additions: footer markup styling, animations, outlines) defined the same way, right after `DARK_MODE_CSS`.

**Tech Stack:** Python 3.10, Streamlit 1.54, LangChain (`langchain_core.messages`), plain CSS/HTML injected via `st.markdown(..., unsafe_allow_html=True)`. Verification uses the repo's own `run_tests.py` harness (not pytest — see Global Constraints) plus the `browse` CLI already built at `C:\Users\Vaughnroy Smith\.claude\skills\gstack\browse\dist\browse` for manual visual checks.

## Global Constraints

- Windows platform (`C:\Users\Vaughnroy Smith\Downloads\demarnew-Template-bots`), PowerShell/Git-Bash — no Unix-only assumptions in any command.
- `Template-bot/files/run_tests.py` is the project's only automated test surface — not pytest. It uses a `check(name, condition, detail)` helper that prints PASS/FAIL and a final tally; new automated checks are added as new lines inside existing `section(...)` blocks or a new one. It must stay at **88/90 passing** after every task — the 2 pre-existing failures (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) are unrelated KB-leak issues from untracked source docs and are out of scope here.
- No new dependencies — every fix uses the standard library, Streamlit, or LangChain classes already imported in the file (`langchain_core.messages.SystemMessage`/`HumanMessage` is already used elsewhere, e.g. `lucelec_rag_bot.py:2143-2154`).
- This repo (`demarnew-Template-bots`, containing `Template-bot/`) **is** git-tracked (unlike a prior retroactive plan's assumption about the standalone `Template-bot` folder) — each task ends with a real `git commit`.
- Every CSS/HTML change must be verified against both light mode and dark mode (`st.session_state.dark_mode`) — this is the exact bug class (Bugs 3 and 4 in the spec) two tasks in this plan exist to fix, so don't reintroduce it.
- Streamlit reruns the whole script top-to-bottom on every interaction — any `st.session_state` read must account for the value already being updated by a widget's own `key=` binding earlier or later in the same run (see the existing `ui_language` comment at `lucelec_rag_bot.py:3323-3332` for the established idiom).

---

### Task 1: Fix dark-mode banner title color regression

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:84-142` (`DARK_MODE_CSS` constant)
- Test: `Template-bot/files/run_tests.py` (new check in a new "12 · UI polish" section)

**Interfaces:**
- Consumes: nothing from other tasks — fully independent, safe to do first.
- Produces: nothing consumed by other tasks.

**Context:** `DARK_MODE_CSS` overrides `.lucelec-subtitle`'s color (line 134: `.lucelec-subtitle { color: #85c1e9 !important; }`) but not `.lucelec-title`'s. Since `DARK_MODE_CSS` now injects *after* the banner's own `<style>` block (a prior session's fix, `lucelec_rag_bot.py:3145-3174`), the generic `[data-testid="stMarkdownContainer"] *` color rule inside `DARK_MODE_CSS` (lines 92-95) ties in specificity with `.lucelec-title`'s own color rule and wins on source order — turning the brand-yellow "LUCELEC" wordmark plain white/gray in dark mode. Confirmed visually during the design brainstorm (dark-mode screenshot showed a thin white title instead of the bold yellow one).

- [ ] **Step 1: Write the failing check**

Open `Template-bot/files/run_tests.py`. Find the end of the file (after section "11 · Streamlit routing states", before the `RESULTS` printing block near the end). Add a new section:

```python
# =====================================================================
section("12 · UI polish")
# =====================================================================
src_text = open(b.__file__, encoding="utf-8").read()

# Bug 3: .lucelec-title must have an explicit color override inside
# DARK_MODE_CSS, or it loses the cascade tie against the generic
# stMarkdownContainer rule and renders white/gray in dark mode instead
# of the brand yellow.
dark_css_start = src_text.index("DARK_MODE_CSS = ")
dark_css_end = src_text.index('"""', src_text.index('"""', dark_css_start) + 3)
dark_css_block = src_text[dark_css_start:dark_css_end]
check(
    "dark mode CSS pins .lucelec-title color",
    ".lucelec-title" in dark_css_block and "#F7DC6F" in dark_css_block,
    "DARK_MODE_CSS has no explicit .lucelec-title color override"
)
```

- [ ] **Step 2: Run it, confirm it fails**

Run (from `Template-bot/files/`): `python run_tests.py`
Expected: new section "12 · UI polish" appears, `FAIL  dark mode CSS pins .lucelec-title color` — `.lucelec-title` is not yet in `DARK_MODE_CSS`.

- [ ] **Step 3: Fix `DARK_MODE_CSS`**

Edit `lucelec_rag_bot.py:133-134`:
```python
# Before:
.lucelec-banner { background-color: #1a2733 !important; border-color: #2c3e50 !important; }
.lucelec-subtitle { color: #85c1e9 !important; }

# After:
.lucelec-banner { background-color: #1a2733 !important; border-color: #2c3e50 !important; }
.lucelec-title { color: #F7DC6F !important; }
.lucelec-subtitle { color: #85c1e9 !important; }
```
(Same yellow as the light-mode title color — the brand wordmark doesn't need a different shade in dark mode, it just needs to *win* the cascade tie against the generic markdown-color rule.)

- [ ] **Step 4: Run it, confirm it passes**

Run: `python run_tests.py`
Expected: `PASS  dark mode CSS pins .lucelec-title color`, 89/91 total (88 previous + 1 new pass, same 2 pre-existing unrelated fails).

- [ ] **Step 5: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task1.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" click "text=Settings"
sleep 1
"$B" click "text=🌙 Dark mode"
sleep 1
"$B" screenshot /tmp/task1_dark.png
```
Read `/tmp/task1_dark.png` — confirm "LUCELEC" renders in bold yellow, not white/gray.

- [ ] **Step 6: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py Template-bot/files/run_tests.py
git commit -m "fix: pin banner title color in dark mode CSS to stop cascade-tie regression"
```

---

### Task 2: Fix logo white-box mismatch

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:3152` (`.lucelec-logo` rule inside the banner's own `<style>` block)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by other tasks.

**Context:** The design reference (`Template-bot/files/Lucelec_bot_design.png`) shows the circular LUCELEC seal sitting directly on the blue banner. The app currently shows it inside a visible white square — the source PNG (`Lucelec_logo.png`) has a baked-in white background, confirmed by screenshot during the brainstorm. No transparent-background version of the logo exists among the project's asset files (`Template-bot/files/*.png` — only the one logo file). Fix with `mix-blend-mode: multiply`, which makes white pixels transparent against whatever's behind them without needing a new asset.

- [ ] **Step 1: Confirm no transparent logo asset exists**

Run: `ls "Template-bot/files/"*.png` (or `Get-ChildItem` on Windows) — confirm `Lucelec_logo.png` is the only logo PNG. If a second transparent-background logo file turns up, use that as `img_html`'s source instead of Steps 2-3 below, and skip the blend-mode CSS.

- [ ] **Step 2: Apply the blend-mode fix**

Edit `lucelec_rag_bot.py:3152`:
```python
# Before:
    .lucelec-logo {{ height: 110px; width: auto; }}

# After:
    .lucelec-logo {{ height: 110px; width: auto; mix-blend-mode: multiply; }}
```

- [ ] **Step 3: Compile check**

Run: `python -m py_compile lucelec_rag_bot.py`
Expected: no output (clean compile).

- [ ] **Step 4: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task2.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" screenshot /tmp/task2_light.png --clip 380,110,270,190
```
Read `/tmp/task2_light.png` — confirm the white square around the logo is gone and the seal blends into the blue banner. Also toggle dark mode (as in Task 1 Step 5) and re-screenshot the same clip — `mix-blend-mode: multiply` must not turn the logo fully black against the darker banner background; if it looks wrong in dark mode, use `mix-blend-mode: darken` instead (test both, keep whichever reads correctly in both themes).

- [ ] **Step 5: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py
git commit -m "fix: remove white box around banner logo with blend-mode instead of a new asset"
```

---

### Task 3: Add the missing footer bar

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:143` (insert `POLISH_CSS` constant, right after `DARK_MODE_CSS` ends)
- Modify: `Template-bot/files/lucelec_rag_bot.py:133-142` (`DARK_MODE_CSS`, add footer override)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3813` (end of `streamlit_app()`, add footer render call)
- Test: `Template-bot/files/run_tests.py` (extend "12 · UI polish" section)

**Interfaces:**
- Consumes: nothing from other tasks (independent of Tasks 1-2; touches different lines).
- Produces: `POLISH_CSS` constant — Task 6 (animations/outlines) appends to this same constant rather than creating a new one. If Task 6 runs before this task in a re-ordered execution, its implementer creates `POLISH_CSS` instead and this task appends to it — either order works as long as only one `POLISH_CSS = """..."""` definition ends up in the file.

**Context:** Design reference shows a bottom banner: light blue background, building silhouettes left and right, centered italic text "The Power Of Caring". The app currently renders nothing at the bottom of `streamlit_app()`.

- [ ] **Step 1: Write the failing check**

In `run_tests.py`'s "12 · UI polish" section (added in Task 1), add:
```python
check(
    "footer bar is rendered",
    "lucelec-footer" in src_text,
    "no .lucelec-footer markup found in streamlit_app()"
)
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `python run_tests.py`
Expected: `FAIL  footer bar is rendered`.

- [ ] **Step 3: Add the `POLISH_CSS` constant**

Insert immediately after `DARK_MODE_CSS`'s closing `"""` (currently `lucelec_rag_bot.py:142`, right before the `# Streamlit's config.toml [theme]...` comment at line 143):

```python
POLISH_CSS = """
.lucelec-footer {
    background-color: #5DADE2; padding: 1rem; border-radius: 10px;
    display: flex; justify-content: center; align-items: center; gap: 1rem;
    margin-top: 2rem;
}
.lucelec-footer-text {
    font-size: 1.4rem; font-weight: 700; color: #2C3E50 !important;
    font-style: italic; margin: 0;
}
.lucelec-footer-icon { width: 40px; height: auto; }
"""
```

- [ ] **Step 4: Add the footer's dark-mode override**

Edit `DARK_MODE_CSS` (the block Task 1 already touched — add one more line after the `.lucelec-title` line this plan's Task 1 introduced):
```python
# Before (after Task 1):
.lucelec-title { color: #F7DC6F !important; }
.lucelec-subtitle { color: #85c1e9 !important; }

# After:
.lucelec-title { color: #F7DC6F !important; }
.lucelec-subtitle { color: #85c1e9 !important; }
.lucelec-footer { background-color: #1a2733 !important; }
.lucelec-footer-text { color: #85c1e9 !important; }
```

- [ ] **Step 5: Render the footer**

At the very end of `streamlit_app()` (currently ending at `lucelec_rag_bot.py:3813`, right before the `# =====================================================================` separator comment), add — matching the function's 4-space base indentation:

```python
    # 8. FOOTER
    st.markdown(f"<style>{POLISH_CSS}</style>", unsafe_allow_html=True)
    st.markdown("""
    <div class="lucelec-footer">
        <svg class="lucelec-footer-icon" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="30" width="20" height="50" fill="#2C3E50"/>
            <rect x="30" y="15" width="20" height="65" fill="#2C3E50"/>
            <rect x="10" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="18" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="35" y="25" width="5" height="5" fill="#5DADE2"/>
            <rect x="43" y="25" width="5" height="5" fill="#5DADE2"/>
        </svg>
        <p class="lucelec-footer-text">The Power Of Caring</p>
        <svg class="lucelec-footer-icon" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="30" width="20" height="50" fill="#2C3E50"/>
            <rect x="30" y="15" width="20" height="65" fill="#2C3E50"/>
            <rect x="10" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="18" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="35" y="25" width="5" height="5" fill="#5DADE2"/>
            <rect x="43" y="25" width="5" height="5" fill="#5DADE2"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)
```
(Inline SVG building silhouettes, per the spec — no new binary asset needed. Simple rectangles with lit-window squares is enough to read as "buildings" at footer icon size; doesn't need to pixel-match the design PNG's illustration.)

- [ ] **Step 6: Run it, confirm it passes**

Run: `python run_tests.py`
Expected: `PASS  footer bar is rendered`, plus Task 1's check still passing.

- [ ] **Step 7: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task3.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" scroll
"$B" screenshot /tmp/task3_light.png
```
Read `/tmp/task3_light.png` — confirm the footer bar appears at the bottom with the light-blue background and centered text. Toggle dark mode and re-screenshot — confirm the footer switches to the dark navy background with light-blue text, matching the banner's dark treatment.

- [ ] **Step 8: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py Template-bot/files/run_tests.py
git commit -m "feat: add missing footer bar matching the design reference"
```

---

### Task 4: Fix accessibility font-size CSS scope and persistence bug

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:71-81` (`build_accessibility_css()`)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3127-3131` (top-of-function injection point)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3361-3372` (settings-block slider + old injection call)
- Test: `Template-bot/files/run_tests.py` (extend "12 · UI polish" section)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by other tasks. Independent of Tasks 1-3 (different code region) and Tasks 5-7.

**Context:** Two bugs in one function. (1) `build_accessibility_css()`'s selector (`html, body, [data-testid="stAppViewContainer"], ... *`) sets `font-size: ... !important` on every descendant, including `.lucelec-title`, whose own `font-size: 4rem` has no `!important` — the universal `!important` rule always wins regardless of specificity, so opening Settings visibly shrinks the giant banner title. (2) The `st.markdown(f"<style>{css}</style>", ...)` call only runs inside `if st.session_state.get("show_settings", False): with st.expander(...):` — since Streamlit reruns the whole script every interaction, the chosen font-size preference stops applying the instant Settings is collapsed.

- [ ] **Step 1: Write the failing checks**

In `run_tests.py`'s "12 · UI polish" section, add:
```python
import inspect
a11y_css_source = inspect.getsource(b.build_accessibility_css)
check(
    "accessibility CSS excludes branded title/subtitle/footer text",
    ":not(.lucelec-title)" in a11y_css_source
        and ":not(.lucelec-subtitle)" in a11y_css_source
        and ":not(.lucelec-footer-text)" in a11y_css_source,
    "build_accessibility_css() selector can still clobber branded text font-size"
)

app_source = inspect.getsource(b.streamlit_app)
# The old bug: injection call only appears inside the `show_settings`
# block. After the fix it must also appear before "# 4. VIEW ROUTER"
# (i.e. unconditionally, every rerun).
before_router = app_source[:app_source.index("# 4. VIEW ROUTER")]
check(
    "accessibility CSS injects unconditionally every rerun",
    "build_accessibility_css(" in before_router,
    "build_accessibility_css(...) is not called before the VIEW ROUTER section — font size won't persist once Settings is closed"
)
```

- [ ] **Step 2: Run it, confirm both fail**

Run: `python run_tests.py`
Expected: both new checks `FAIL`.

- [ ] **Step 3: Fix `build_accessibility_css()`'s selector**

Edit `lucelec_rag_bot.py:71-81`:
```python
# Before:
def build_accessibility_css(font_size: int) -> str:
    """Build the CSS that scales the Streamlit app UI to the requested font size."""
    font_size = max(14, min(24, int(font_size)))
    return f"""
    :root {{ --lucelec-font-size: {font_size}px; }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stMain"],
    [data-testid="stAppViewContainer"] *, [data-testid="stSidebar"] *, [data-testid="stMain"] * {{
        font-size: var(--lucelec-font-size) !important;
        line-height: 1.45 !important;
    }}
    """

# After:
def build_accessibility_css(font_size: int) -> str:
    """Build the CSS that scales the Streamlit app UI to the requested font size.

    Excludes the branded banner/footer text (.lucelec-title,
    .lucelec-subtitle, .lucelec-footer-text) — those are sized in rem by
    design and previously got silently shrunk to the accessibility font
    size because a universal `!important` selector always beats a
    non-important class rule regardless of specificity.
    """
    font_size = max(14, min(24, int(font_size)))
    return f"""
    :root {{ --lucelec-font-size: {font_size}px; }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stMain"],
    [data-testid="stAppViewContainer"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text),
    [data-testid="stSidebar"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text),
    [data-testid="stMain"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text) {{
        font-size: var(--lucelec-font-size) !important;
        line-height: 1.45 !important;
    }}
    """
```

- [ ] **Step 4: Move the injection to run unconditionally**

Edit `lucelec_rag_bot.py:3127-3131` (the "2. ACCESSIBILITY CSS INJECTION" section, right after `t()` is defined):
```python
# Before:
    # 2. ACCESSIBILITY CSS INJECTION
    a11y = st.session_state.get("accessibility_settings", {
        "font_size": 16, "tts": False, "stt": False, "simple_language": False
    })

# After:
    # 2. ACCESSIBILITY CSS INJECTION — runs every rerun (not gated behind
    # Settings being open) so the chosen font size persists once the
    # panel is collapsed. Reads the live slider value via its own
    # session_state key when Settings is open this run (same idiom as
    # the ui_language selectbox above), otherwise the last-saved value.
    a11y = st.session_state.get("accessibility_settings", {
        "font_size": 16, "tts": False, "stt": False, "simple_language": False
    })
    _current_font_size = int(st.session_state.get("font_size_slider", a11y.get("font_size", 16)))
    st.markdown(f"<style>{build_accessibility_css(_current_font_size)}</style>", unsafe_allow_html=True)
```

- [ ] **Step 5: Remove the now-redundant injection inside the Settings block**

Edit `lucelec_rag_bot.py:3361-3372` (keep the slider and the state-saving lines — only remove the duplicate CSS injection):
```python
# Before:
                a11y_state["stt"] = st.checkbox(t("stt_checkbox"), value=a11y_state.get("stt", False))
                font_size_value = st.slider(
                                    t("font_size_label"),
                                    min_value=14,
                                    max_value=24,
                                    value=int(a11y_state.get("font_size", 16)),
                                    key="font_size_slider")
                font_size_value = int(st.session_state.get("font_size_slider", font_size_value))
                a11y_state["font_size"] = font_size_value
                st.session_state.accessibility_settings = a11y_state

                css = build_accessibility_css(font_size_value)
                st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# After:
                a11y_state["stt"] = st.checkbox(t("stt_checkbox"), value=a11y_state.get("stt", False))
                font_size_value = st.slider(
                                    t("font_size_label"),
                                    min_value=14,
                                    max_value=24,
                                    value=int(a11y_state.get("font_size", 16)),
                                    key="font_size_slider")
                font_size_value = int(st.session_state.get("font_size_slider", font_size_value))
                a11y_state["font_size"] = font_size_value
                st.session_state.accessibility_settings = a11y_state
                # CSS injection now happens once, unconditionally, near the
                # top of streamlit_app() — see "2. ACCESSIBILITY CSS INJECTION".
```

- [ ] **Step 6: Run it, confirm both pass**

Run: `python run_tests.py`
Expected: both checks `PASS`.

- [ ] **Step 7: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task4.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" click "text=Settings"
sleep 1
"$B" screenshot /tmp/task4_settings_open.png
```
Read `/tmp/task4_settings_open.png` — confirm "LUCELEC" title is still full-size (not shrunk) with Settings open. Then drag the font-size slider to 24, close Settings (click the Settings button again), and screenshot the sidebar chat-list button labels — confirm they're still enlarged even with the panel collapsed (this is the persistence half of the bug).

- [ ] **Step 8: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py Template-bot/files/run_tests.py
git commit -m "fix: accessibility font-size CSS no longer clobbers banner title or resets when Settings closes"
```

---

### Task 5: Fix mic icon glyph and voice-widget dark mode

**Files:**
- Modify: `Template-bot/files/voice_recorder_component/index.html`
- Modify: `Template-bot/files/lucelec_rag_bot.py:3591` (the sidebar's own 🎤 toggle button — separate from the component's internal mic button)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by other tasks. Independent of all other tasks (only touches the voice component file plus one unrelated button line).

**Context:** Two related but separate elements both use the 🎤 emoji: the component's own internal mic button (inside the iframe, `index.html:85`) and the sidebar's toggle button that shows/hides the whole voice widget (`lucelec_rag_bot.py:3591`, `st.button("🎤", on_click=toggle_voice_widget, ...)`). Both render as a broken glyph on this environment's font stack. Separately, the component's internal styles (`#mic-btn { background: #f0f2f6; ... }`) are hardcoded light-only — the iframe is sandboxed from the parent page's `DARK_MODE_CSS` injection, so it can't read the in-app dark-mode toggle; it can only respond to the browser's own OS-level dark-mode preference via a media query.

- [ ] **Step 1: Replace the component's internal mic button glyph with inline SVG**

Edit `Template-bot/files/voice_recorder_component/index.html` — replace the button's emoji content and add matching CSS. Current (`index.html:85`):
```html
    <button id="mic-btn" title="Record a question">🎤</button>
```
New:
```html
    <button id="mic-btn" title="Record a question">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="9" y="2" width="6" height="12" rx="3" fill="currentColor"/>
        <path d="M5 10v1a7 7 0 0 0 14 0v-1" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M12 18v3M9 21h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </button>
```
Add to the existing `<style>` block (`index.html:64-81`), right after the `#mic-btn` rule:
```css
  #mic-btn { display: flex; align-items: center; justify-content: center; }
  #mic-btn svg { color: #262730; }
  #mic-btn.recording svg { color: white; }
```
(`currentColor` in the SVG picks up `color` from the button, so the existing `.recording` state's white color still applies without extra rules.)

- [ ] **Step 2: Add dark-mode support to the component**

Add to the same `<style>` block, after the existing rules:
```css
  @media (prefers-color-scheme: dark) {
    #mic-btn { background: #1e222b; }
    #mic-btn svg { color: #fafafa; }
    #mic-btn:hover { background: #2a2f3a; }
    #status { color: #9aa1ab; }
  }
```

- [ ] **Step 3: Replace the sidebar toggle button's emoji**

Edit `lucelec_rag_bot.py:3591`:
```python
# Before:
            st.button("🎤", on_click=toggle_voice_widget, use_container_width=True)

# After:
            st.button("🎙️", on_click=toggle_voice_widget, use_container_width=True)
```
(`st.button`'s label is plain Streamlit-rendered text, not raw HTML — it can't take an inline SVG. Swapping to the U+1F399 "Studio Microphone" emoji is the practical fix here since Streamlit's own font stack renders it correctly where U+1F3A4 "Microphone" doesn't; confirm in Step 4.)

- [ ] **Step 4: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task5.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" screenshot /tmp/task5_toggle.png --clip 1120,370,90,60
```
Read `/tmp/task5_toggle.png` — confirm the sidebar toggle button shows a recognizable mic glyph (not a broken/tofu character). If the U+1F399 emoji still doesn't render correctly in this environment, replace it with plain text `"Mic"` as a guaranteed-safe fallback instead of chasing font support further — either satisfies the bug fix (a broken glyph is worse than a text label).

Then click it to open the voice widget and confirm the SVG mic icon renders inside the component's iframe:
```bash
"$B" click "text=🎙️"
sleep 1
"$B" screenshot /tmp/task5_widget.png
```
Read `/tmp/task5_widget.png` — confirm the round mic button shows the inline SVG icon clearly.

- [ ] **Step 5: Commit**

```bash
git add Template-bot/files/voice_recorder_component/index.html Template-bot/files/lucelec_rag_bot.py
git commit -m "fix: replace broken mic emoji with inline SVG, add dark-mode support to voice widget"
```

---

### Task 6: Animations and outlines

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py` (`POLISH_CSS` constant — created in Task 3, appended to here; if this task runs before Task 3 in a different execution order, create `POLISH_CSS` here instead following Task 3 Step 3's format, and Task 3 appends to it)
- Test: `Template-bot/files/run_tests.py` (extend "12 · UI polish" section)

**Interfaces:**
- Consumes: `POLISH_CSS` constant (from Task 3, or creates it if run first — see above).
- Produces: nothing consumed by other tasks.

**Context:** Per the approved design: light-touch CSS transitions only (no JS, no new libraries) — chat messages fade/slide in, buttons and tabs get a hover transition instead of an instant snap, sidebar chat-switch fades. Plus `1px solid` outlines on four elements that currently have no visible boundary: parish badges, inactive tabs, the chat input box, and sidebar chat-list buttons.

- [ ] **Step 1: Write the failing check**

In `run_tests.py`'s "12 · UI polish" section, add:
```python
polish_css_start = src_text.index("POLISH_CSS = ")
polish_css_end = src_text.index('"""', src_text.index('"""', polish_css_start) + 3)
polish_css_block = src_text[polish_css_start:polish_css_end]
check(
    "POLISH_CSS has message fade-in animation",
    "@keyframes" in polish_css_block and "stChatMessage" in polish_css_block,
    "no keyframe animation targeting stChatMessage found in POLISH_CSS"
)
check(
    "POLISH_CSS outlines the four target elements",
    all(sel in polish_css_block for sel in
        [".parish-badge", "stChatInput", "stTab"])
    and "sidebar" in polish_css_block.lower(),
    "POLISH_CSS is missing one or more of the four outlined elements"
)
```

- [ ] **Step 2: Run it, confirm both fail**

Run: `python run_tests.py`
Expected: both new checks `FAIL` (or error if `POLISH_CSS` doesn't exist yet — in that case Task 3 hasn't run; complete Task 3 Step 3 first, or create the constant here per Task 3's format).

- [ ] **Step 3: Add animations to `POLISH_CSS`**

Append inside the `POLISH_CSS` triple-quoted string (before its closing `"""`):
```css
@keyframes lucelec-msg-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}
[data-testid="stChatMessage"] {
    animation: lucelec-msg-in 200ms ease-out;
}

[data-testid="stSidebar"] button,
.stTabs [data-baseweb="tab"] {
    transition: background-color 150ms ease, border-color 150ms ease;
}
```

- [ ] **Step 4: Add outlines to `POLISH_CSS`**

Append inside the same `POLISH_CSS` string:
```css
.parish-badge {
    border: 1px solid #b0b8c1;
}
.stTabs [data-baseweb="tab"] {
    border: 1px solid transparent;
    border-radius: 6px 6px 0 0;
}
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) {
    border-color: #d0d5db;
}
[data-testid="stChatInput"] {
    border: 1px solid #c4cad3;
    border-radius: 8px;
}
[data-testid="stSidebar"] button {
    border: 1px solid #d0d5db;
}
```
And their dark-mode equivalents — append to `DARK_MODE_CSS` (same file this task's `POLISH_CSS` block lives next to):
```css
.parish-badge { border-color: #3a3f4b !important; }
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) { border-color: #3a3f4b !important; }
[data-testid="stChatInput"] { border-color: #3a3f4b !important; }
[data-testid="stSidebar"] button { border-color: #3a3f4b !important; }
```
(`.parish-badge` already has a `border-color` override at the existing `lucelec_rag_bot.py:140` line inside `DARK_MODE_CSS` — merge into that existing rule instead of adding a duplicate selector block. Check the current `.parish-badge` rule in `DARK_MODE_CSS` before adding: if `border-color` is already set there, this task's dark override is redundant for that one selector — skip it and only add the other three.)

- [ ] **Step 5: Run it, confirm both pass**

Run: `python run_tests.py`
Expected: both checks `PASS`.

- [ ] **Step 6: Manual visual verification**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task6.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" screenshot /tmp/task6_outlines.png
```
Read `/tmp/task6_outlines.png` — confirm the tab bar's inactive tabs, the chat input box, and the sidebar chat buttons now show a visible thin border. Type a message into chat input and submit it — visually confirm the reply fades in rather than snapping into view (hard to verify precisely from a static screenshot; confirm at minimum that no layout breaks and the animation doesn't cause visible flicker/jank across two screenshots taken ~100ms apart).

- [ ] **Step 7: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py Template-bot/files/run_tests.py
git commit -m "feat: add light-touch animations and missing element outlines"
```

---

### Task 7: LLM-generated chat titles

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:1943` (insert `_heuristic_chat_title()` and `summarize_chat_title()`, right after `llm_call()` ends and before `extractive_answer()`)
- Modify: `Template-bot/files/lucelec_rag_bot.py:2799` (`initialize_sidebar_state`'s `chat_sessions` default)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3264` (`add_new_chat()`)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3275` (`delete_chat()`'s empty-list fallback)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3285` (sidebar's `chat_sessions` `setdefault`)
- Modify: `Template-bot/files/lucelec_rag_bot.py:3557-3560` (end of `process_chat_message()`)
- Test: `Template-bot/files/run_tests.py` (extend "12 · UI polish" section)

**Interfaces:**
- Consumes: nothing from other tasks — independent of Tasks 1-6 (different code regions; the only shared file is `lucelec_rag_bot.py` itself, and no line ranges overlap with earlier tasks).
- Produces: `_heuristic_chat_title(text: str) -> str` — pure, deterministic, no network/session-state dependency; safe for any future caller needing a synchronous fallback title. `summarize_chat_title(first_message: str) -> str` — tries the active LLM provider chain, falls back to `_heuristic_chat_title()` on any failure; never raises. Every chat dict (in `chat_sessions`) now always carries a `"titled": bool` key alongside its existing `"id"`, `"title"`, `"messages"` keys — any other code reading a chat dict can rely on this key existing.

- [ ] **Step 1: Write the failing checks for the heuristic fallback**

In `run_tests.py`'s "12 · UI polish" section, add:
```python
check("has _heuristic_chat_title()", hasattr(b, "_heuristic_chat_title"))
check("has summarize_chat_title()", hasattr(b, "summarize_chat_title"))

if hasattr(b, "_heuristic_chat_title"):
    t1 = b._heuristic_chat_title("How much does an old fridge cost to run per month?")
    check(
        "heuristic title is short and non-empty",
        bool(t1) and len(t1) <= 42,
        f"got: {t1!r}"
    )
    check(
        "heuristic title drops common stopwords",
        "does" not in t1.lower().split() and "the" not in t1.lower().split(),
        f"got: {t1!r}"
    )
    check(
        "heuristic title is deterministic",
        b._heuristic_chat_title("test message") == b._heuristic_chat_title("test message")
    )
    check(
        "heuristic title never blows up on empty input",
        b._heuristic_chat_title("") == "New chat",
        f"got: {b._heuristic_chat_title('')!r}"
    )
```

- [ ] **Step 2: Run it, confirm the `hasattr` checks fail**

Run: `python run_tests.py`
Expected: `FAIL  has _heuristic_chat_title()`, `FAIL  has summarize_chat_title()` (the checks depending on them will error/fail too since the functions don't exist yet).

- [ ] **Step 3: Implement `_heuristic_chat_title()` and `summarize_chat_title()`**

Insert after `llm_call()` ends (currently `lucelec_rag_bot.py:1942`, right before the blank line and `def extractive_answer(...)` at line 1945):

```python
_TITLE_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "how", "what", "when", "where", "why", "who", "which", "can",
    "could", "would", "should", "will", "i", "my", "me", "to", "of",
    "for", "in", "on", "at", "and", "or", "please", "hi", "hello",
}


def _heuristic_chat_title(text: str) -> str:
    """Turn a raw user message into a short chat-title, no LLM call.

    Deterministic — same input always gives the same output. Used as
    the fallback when no provider is configured or the title LLM call
    fails, so a chat never gets stuck without a real title.
    """
    words = re.findall(r"[A-Za-z0-9']+", text)
    kept = [w for w in words if w.lower() not in _TITLE_STOPWORDS]
    if not kept:
        kept = words
    title = " ".join(kept[:6]).strip()
    if not title:
        return "New chat"
    title = title[0].upper() + title[1:]
    if len(title) > 40:
        title = title[:40].rstrip() + "…"
    return title


def summarize_chat_title(first_message: str) -> str:
    """Generate a short chat-list title from the user's first message.

    Tries the active LLM provider chain first, asking for a 3-6 word
    summary. Falls back to _heuristic_chat_title() on any failure — no
    provider configured, network error, timeout, or an unexpected
    response shape — so this never raises into the UI.
    """
    from langchain_core.messages import SystemMessage, HumanMessage

    system = (
        "Summarize the user's question as a short chat title: 3 to 6 "
        "words, no trailing punctuation, no quotation marks. Reply with "
        "only the title, nothing else."
    )
    for provider in active_chain():
        if not is_configured(provider):
            continue
        try:
            llm = get_llm_for_provider(provider)
            response = llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=first_message),
            ])
            if isinstance(response.content, list):
                title = " ".join(
                    block.get("text", "") for block in response.content
                    if isinstance(block, dict)
                ).strip()
            else:
                title = str(response.content).strip()
            title = title.strip("\"' ")
            if title:
                return title[:60]
        except Exception:
            continue
    return _heuristic_chat_title(first_message)
```

- [ ] **Step 4: Run it, confirm the heuristic checks pass (LLM-path checks come in Step 8)**

Run: `python run_tests.py`
Expected: `PASS  has _heuristic_chat_title()`, `PASS  has summarize_chat_title()`, and all four `_heuristic_chat_title` behavior checks `PASS`.

- [ ] **Step 5: Add the `"titled"` flag to every chat-dict creation site**

Edit `lucelec_rag_bot.py:2799` (`initialize_sidebar_state`):
```python
# Before:
    state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": []}])

# After:
    state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": [], "titled": False}])
```

Edit `lucelec_rag_bot.py:3264` (`add_new_chat()`):
```python
# Before:
        new_chat = {"id": str(uuid4()), "title": t("new_chat_title"), "messages": []}

# After:
        new_chat = {"id": str(uuid4()), "title": t("new_chat_title"), "messages": [], "titled": False}
```

Edit `lucelec_rag_bot.py:3275` (`delete_chat()`'s empty-list fallback):
```python
# Before:
            chats = [{"id": str(uuid4()), "title": t("new_chat_title"), "messages": []}]

# After:
            chats = [{"id": str(uuid4()), "title": t("new_chat_title"), "messages": [], "titled": False}]
```

Edit `lucelec_rag_bot.py:3285` (sidebar's `chat_sessions` `setdefault`):
```python
# Before:
        st.session_state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": []}])

# After:
        st.session_state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": [], "titled": False}])
```

- [ ] **Step 6: Write the failing check for the "fires once" behavior**

Add to `run_tests.py`'s "12 · UI polish" section:
```python
process_chat_source = inspect.getsource(b.streamlit_app)
check(
    "process_chat_message titles the chat exactly once, using the titled flag",
    'chat.get("titled"' in process_chat_source and "summarize_chat_title(" in process_chat_source,
    "process_chat_message() doesn't call summarize_chat_title() guarded by the titled flag"
)
for fn_name in ("add_new_chat", "delete_chat"):
    fn_source = app_source[app_source.index(f"def {fn_name}("):]
    fn_source = fn_source[:fn_source.index("\n\n    def ") if "\n\n    def " in fn_source else 400]
    check(
        f"{fn_name}() initializes the titled flag",
        '"titled": False' in fn_source,
        f"{fn_name}() creates a chat dict without titled: False"
    )
```
(This reuses the `app_source` variable already computed in Task 4's checks — if Task 4 hasn't run yet in this execution order, add `app_source = inspect.getsource(b.streamlit_app)` here instead.)

- [ ] **Step 7: Run it, confirm it fails**

Run: `python run_tests.py`
Expected: `FAIL  process_chat_message titles the chat exactly once, using the titled flag` (the two `titled` flag checks should already pass from Step 5).

- [ ] **Step 8: Hook the title generation into `process_chat_message()`**

Edit `lucelec_rag_bot.py:3557-3560` (end of `process_chat_message`, right after the assistant reply is appended and persisted):
```python
# Before:
            # Save assistant reply to history
            st.session_state.messages.append(
                {"role": "assistant", "content": out["reply"], "hits": out["hits"]})
            persist_active_chat()

# After:
            # Save assistant reply to history
            st.session_state.messages.append(
                {"role": "assistant", "content": out["reply"], "hits": out["hits"]})
            persist_active_chat()

            # Title the chat from its first exchange, once. The "titled"
            # flag (not a message-count check) is what makes this
            # idempotent — it survives chats restored from
            # chat_sessions state without re-counting messages.
            active_id = st.session_state.get("active_chat_id")
            for chat in st.session_state.get("chat_sessions", []):
                if chat["id"] == active_id and not chat.get("titled", False):
                    chat["title"] = summarize_chat_title(q)
                    chat["titled"] = True
                    break
```

- [ ] **Step 9: Run it, confirm it passes**

Run: `python run_tests.py`
Expected: `PASS  process_chat_message titles the chat exactly once, using the titled flag`, and all other Task 7 checks still `PASS`.

- [ ] **Step 10: Manual verification — offline fallback path**

This environment has no configured LLM API keys during automated testing (confirmed by the existing "6 · Offline fallback" test section), so `summarize_chat_title()` will exercise its fallback path by construction. Verify directly:
```bash
cd "Template-bot/files"
python -c "
import lucelec_rag_bot as b
title = b.summarize_chat_title('How much does an old fridge cost to run compared to an inverter fridge?')
print(repr(title))
assert title and title != 'New chat'
print('OK')
"
```
Expected: prints a short, non-empty title (the heuristic output, since no provider is configured) and `OK`.

- [ ] **Step 11: Manual visual verification — end to end in the browser**

```bash
cd "Template-bot/files"
(python -m streamlit run lucelec_rag_bot.py --server.headless true --server.port 8512 > /tmp/st_task7.log 2>&1 &)
sleep 3
B="/c/Users/Vaughnroy Smith/.claude/skills/gstack/browse/dist/browse"
"$B" goto http://localhost:8512
"$B" fill "[data-testid='stChatInput'] textarea" "How much does an old fridge cost to run?"
"$B" press Enter
sleep 3
"$B" screenshot /tmp/task7_titled.png
```
Read `/tmp/task7_titled.png` — confirm the sidebar's active chat entry no longer reads "New chat" but shows a short phrase derived from the question. Click "+ New chat" and confirm the new (empty) chat still reads "New chat" until its own first message is sent — titling must be per-chat, not global.

- [ ] **Step 12: Commit**

```bash
git add Template-bot/files/lucelec_rag_bot.py Template-bot/files/run_tests.py
git commit -m "feat: generate chat titles from the first message instead of leaving them as 'New chat'"
```

---

## Self-Review

**Spec coverage:** Bug 1 (footer) → Task 3. Bug 2 (logo box) → Task 2. Bug 3 (dark title regression) → Task 1. Bug 4 (a11y font-size clobber + non-persistence) → Task 4. Bug 5 (voice widget dark mode) → Task 5. Bug 6 (mic glyph) → Task 5. Chat titles feature → Task 7. Animations + outlines → Task 6. All eight spec items have a task.

**Placeholder scan:** every step shows the actual before/after code, actual commands, and actual expected output — no TBD/TODO/"add appropriate X" phrasing.

**Type consistency:** `_heuristic_chat_title(text: str) -> str` and `summarize_chat_title(first_message: str) -> str` signatures are used identically everywhere they're referenced (Task 7 Steps 1, 3, 6, 8, 10). The `"titled": bool` key name is identical across all four creation sites (Task 7 Step 5) and the one read site (Task 7 Step 8) — no `is_titled`/`titled` mismatch.

**Task independence:** Tasks 1, 2, 4, 5, 7 touch disjoint line ranges and can run in any order relative to each other. Task 3 and Task 6 both touch `POLISH_CSS` — their Interfaces sections call this out explicitly so whichever runs second appends rather than redefining the constant.
