# Lucelec Bot UI Polish Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement the plan built from this spec.

**Goal:** Polish the Lucelec Streamlit bot's UI before starting larger feature work — fix visual bugs found against the design reference (`Template-bot/files/Lucelec_bot_design.png`), add LLM-generated chat titles, and add light animation/outline polish.

**Non-goals:** No redesign of the four content tabs (Chat / Location status / Area tariffs / Cost calculator) — audited against the design reference and found structurally fine, no branding mismatches. No retroactive re-titling of chat sessions that existed before this change. No perfect dark-mode sync for the voice-recorder iframe (sandboxed from parent CSS — see Bug 5).

## Context

A prior session already fixed one dark-mode cascade bug (moving `DARK_MODE_CSS` injection to fire after the banner's own `<style>` block, so `.lucelec-subtitle`'s dark color wins the `!important` tie against the banner's light-mode color). That fix is committed in working tree already (uncommitted, see `git diff Template-bot/files/lucelec_rag_bot.py`). This spec's Bug 3 below is a regression introduced by that same fix — `.lucelec-title` was not added to `DARK_MODE_CSS`'s override list, so it now loses the same tie the other direction.

Audit method: ran the app locally (`streamlit run lucelec_rag_bot.py --server.headless true`), used the `browse` skill to screenshot every tab, Settings panel, and dark mode, and compared against `Lucelec_bot_design.png`.

## Architecture

Single file (`Template-bot/files/lucelec_rag_bot.py`), no new dependencies. One new small CSS block (`POLISH_CSS`, defined next to the existing `DARK_MODE_CSS` and `build_accessibility_css()`) injected once near app start — not gated behind any toggle, unlike the buggy accessibility CSS this spec also fixes. One new asset for the footer (building-silhouette graphic, inlined as base64 the same way the header logo already is via `get_base64_of_bin_file()`). One new small function for chat-title generation, reusing the existing LLM provider call path.

## Bug Fixes

### Bug 1: Missing footer bar
Design reference shows a bottom banner: light blue background, building silhouettes left and right, centered text "The Power Of Caring". The app currently renders nothing at the bottom.

Add a `.lucelec-footer` block, rendered via `st.markdown(..., unsafe_allow_html=True)` near the end of `streamlit_app()`, following the same structural pattern as the existing header banner (`lucelec_rag_bot.py:3150-3169`):
```css
.lucelec-footer {
    background-color: #5DADE2; padding: 1rem; border-radius: 10px;
    display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 2rem;
}
.lucelec-footer-text { font-size: 1.4rem; font-weight: 700; color: #2C3E50 !important; font-style: italic; }
```
Building-silhouette images: reuse whichever asset the design PNG's silhouettes came from if present among project files; if none exists, render them as inline SVG (same technique as the loading-screen logo SVG at `lucelec_rag_bot.py:2923-2928`) rather than adding a new binary asset.

Dark-mode override added to `DARK_MODE_CSS` alongside the banner's own override (same pattern as `.lucelec-banner`/`.lucelec-subtitle` at `lucelec_rag_bot.py:133-134`):
```css
.lucelec-footer { background-color: #1a2733 !important; }
.lucelec-footer-text { color: #85c1e9 !important; }
```

### Bug 2: Logo renders inside a white box
Design shows the circular LUCELEC seal sitting directly on the blue banner. The app currently shows it inside a visible white square.

Root cause: the source PNG (`Lucelec_logo.png`) has a baked-in white background — this isn't a CSS bug. Fix, in order of preference:
1. If a transparent-background version of the logo exists among the project's asset files, use that instead.
2. Otherwise apply `mix-blend-mode: multiply` to `.lucelec-logo` in `POLISH_CSS` — makes the white background transparent against the blue banner without needing a new asset, works in both light and dark banner backgrounds.

### Bug 3: Banner title turns white in dark mode (regression)
`DARK_MODE_CSS` overrides `.lucelec-subtitle`'s color (`lucelec_rag_bot.py:134`) but not `.lucelec-title`'s. Now that `DARK_MODE_CSS` injects after the banner's own `<style>` block (prior session's fix), the generic `[data-testid="stMarkdownContainer"] *` color rule in `DARK_MODE_CSS` (`lucelec_rag_bot.py:92-95`) ties in specificity with `.lucelec-title`'s own color rule and wins on source order — turning the brand-yellow "LUCELEC" wordmark plain white.

Fix: add one line to `DARK_MODE_CSS`, same pattern as the existing subtitle override:
```css
.lucelec-title { color: #F7DC6F !important; }
```

### Bug 4: Accessibility font-size CSS clobbers the banner title, and doesn't persist
Two related problems in `build_accessibility_css()` (`lucelec_rag_bot.py:71-81`) and its call site (`lucelec_rag_bot.py:3366-3367`):

1. Its selector — `html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stMain"], [data-testid="stAppViewContainer"] *, [data-testid="stSidebar"] *, [data-testid="stMain"] *` with `font-size: ... !important` — matches every descendant including `.lucelec-title`, whose own `font-size: 4rem` has no `!important`. The `!important` universal rule always wins regardless of specificity, so opening Settings visibly shrinks the giant banner title to the accessibility font size.
2. The `st.markdown(f"<style>{css}</style>", ...)` call only executes inside `if st.session_state.get("show_settings", False): with st.expander(...):` (`lucelec_rag_bot.py:3316-3367`). Since Streamlit reruns the whole script every interaction, this means the chosen font-size preference stops applying the instant the user collapses Settings — the accessibility feature doesn't actually persist across the session.

Fix:
- Move the `css = build_accessibility_css(...)` / `st.markdown(...)` call out of the `show_settings` conditional so it runs unconditionally every rerun, using whatever `font_size_value` is already stored in `st.session_state.accessibility_settings` (defaulting to 16 as today).
- Change `build_accessibility_css()`'s selector to exclude the banner/footer brand text: append `:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text)` to each `*` clause.

### Bug 5: Voice recorder widget ignores dark mode
`voice_recorder_component/index.html` is a Streamlit custom component rendered in a sandboxed iframe — parent-page CSS injection (`DARK_MODE_CSS`) cannot reach into it. It hardcodes light colors (`#mic-btn { background: #f0f2f6; color: #262730; }`).

Fix: add a `@media (prefers-color-scheme: dark)` block inside the component's own `<style>` tag, mirroring the parent app's dark palette (`#1e222b` background, `#fafafa` text, matching `DARK_MODE_CSS`'s chat-input colors). This follows the *browser's* dark-mode preference, not the in-app toggle state — the iframe has no way to read Streamlit session state. Documented here as a known limitation, not a full fix: a user with a light OS theme who flips the in-app toggle to dark will still see a light mic button. Acceptable given the sandboxing constraint.

### Bug 6: Mic icon renders as a broken glyph
The 🎤 emoji (used at the mic button in `render_voice_recorder()`'s caller and inside `voice_recorder_component/index.html`) doesn't render as a microphone on this environment's font stack — shows as a fallback/tofu glyph.

Fix: replace the emoji with an inline SVG mic icon, same technique as the existing header-logo and loading-screen SVGs (`lucelec_rag_bot.py:2923-2928`) — self-contained, no font dependency, recolorable via `fill` to match either theme.

## Feature: LLM-Generated Chat Titles

New function, placed near the other chat-session helpers (`add_new_chat()`, `set_active_chat()`, `lucelec_rag_bot.py:3258-3264`):

```python
def summarize_chat_title(first_message: str) -> str:
    """Generate a short chat title from the user's first message.

    Tries the active LLM provider first; falls back to a local heuristic
    (strip stopwords/punctuation, title-case, cap ~40 chars) on any
    failure — no API key, network error, timeout, or offline mode.
    """
```

- Calls the same provider-selection path `answer()` already uses (`lucelec_rag_bot.py` provider dispatch) with a fixed prompt: "Summarize this customer question as a 3-6 word title, no trailing punctuation." — input is only the first user message, not the bot's reply, keeping it a single one-shot call.
- Wrapped in the same try/except pattern the rest of the file uses around provider calls, falling back to the heuristic truncation described above on any exception.
- Fires exactly once per chat: called from the chat-send handler right after the first message in a session receives its response (not from inside `answer()` — title generation is a UI concern). The result overwrites `chat["title"]` (currently defaults to `t("new_chat_title")`, i.e. "New chat").
- Once `chat["title"]` differs from the default, it is never regenerated — locks in after message 1, per your call.
- Chats created before this feature shipped keep their existing "New chat" title — no retroactive batch re-titling.

## Animations (light touch)

All pure CSS in `POLISH_CSS`, no JavaScript, no new libraries:

- **Chat messages**: fade + slight upward slide on append. Target `[data-testid="stChatMessage"]`, `~200ms ease-out`, `opacity 0→1` + `transform: translateY(4px)→translateY(0)`.
- **Buttons/tabs hover**: `transition: background-color 150ms ease, border-color 150ms ease` on sidebar chat buttons, the tab bar, and the Settings button — replaces instant color snaps with a soft transition.
- **Sidebar active-chat switch**: same transition property applied to the chat-list buttons' background-color, so switching the active chat fades rather than cuts.

## Outlines

Consistent `1px solid` border added to elements that currently have no visible edge and blend into their background — using the theme's existing border color (`#3a3f4b` in dark mode per `DARK_MODE_CSS`'s existing button borders; a matching mid-gray for light mode):

- `.parish-badge` — currently a flat background fill with no boundary
- Inactive tabs in the tab bar — only the active tab currently has a visible (underline) treatment
- The chat input box (`[data-testid="stChatInput"]`) — currently distinguished only by background-color
- Sidebar chat-list buttons — same flat-fill issue

Not applied to elements that already have clear boundaries (banner, expander, dataframes, footer) — this is about adding definition where it's currently missing, not adding chrome everywhere.

## Testing

- `python -m py_compile lucelec_rag_bot.py && python run_tests.py` after every change — must stay at the current 88/90 pass rate (the 2 pre-existing failures are unrelated KB-leak test issues from untracked source docs, out of scope here).
- Manual browser verification via the `browse` skill, re-screenshotting: light-mode banner + new footer, dark-mode banner + footer + title color (Bug 3 fix), Settings panel open with title no longer shrinking (Bug 4 fix) and font-size still applied after collapsing Settings, a new chat's title after the first message in both online (LLM path) and offline/no-API-key (heuristic fallback) modes.
- No automated test covers LLM-generated titles' *content quality* — inherently non-deterministic. Coverage is: title gets set at all, falls back correctly when the provider call fails, and never fires a second time on the same chat.

## Self-Review

**Placeholder scan:** no TBD/TODO markers — every fix has an exact selector, file line reference, or concrete CSS rule.

**Internal consistency:** Bug 3's fix (`.lucelec-title` color override) and the prior session's subtitle fix follow the identical pattern — no contradiction. Bug 4's selector change and the footer/outline CSS additions don't overlap in selectors, so no fix undoes another.

**Scope check:** focused on one implementation plan — bug fixes, one feature (chat titles), and CSS-only polish (animations, outlines), all confined to one file plus optional new inline SVG/asset. Not decomposed further; tasks below are independent enough for subagent-driven-development.

**Ambiguity check:** "outlines... of your choosing" resolved to four named elements in the Outlines section above, with an explicit non-goal list, so no implementer has to guess scope.
