# Dollar-Sign Markdown Render Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop chat replies and source excerpts from rendering as garbled, squished, unparsed-Markdown text whenever they contain two or more literal `$` (dollar) characters — which is every calculator answer, since every one quotes at least two `EC$` amounts.

**Architecture:** Streamlit's markdown renderer (used by `st.markdown`, `st.caption`, and `st.write_stream`) supports inline LaTeX math via a single-`$` delimiter pair, the same convention KaTeX/MathJax use. Any text with two literal `$` characters gets everything between them treated as a math expression instead of plain text — bold markers (`**`) inside that span stop being parsed as bold, spacing collapses, and the whole thing renders italicized and squished. The fix adds one small, pure escaping function and applies it at every place the app renders LLM-or-document text that can legitimately contain `$` — it does not touch the raw reply text used for TTS or stored in chat history, only the copy that actually gets handed to a markdown-rendering call.

**Tech Stack:** Python 3, Streamlit. No new dependencies. Test runner: `run_tests.py` via `../venv/Scripts/python.exe` from `Template-bot/files/`.

**Spec:** None on disk — this plan's spec is the root-cause analysis below, derived from live browser testing (screenshot evidence) against the running app on `localhost:8501`.

## Root cause (read this before touching code)

1. Live-tested the actual running app (not just code inspection): asked the chat "how much does a fridge cost to run?" (correctly asked for wattage/hours per `MASTER_PROMPT`'s own instruction — not a bug), then supplied "150 watts, 24 hours a day". The bot correctly computed the cost using the fuel-surcharge-corrected rate (EC$135.54/month, EC$1,649.07/year — verified these numbers are exactly right: `150W × 24h = 3.6 kWh/day`, `× 30 × 1.255 = 135.54`, `× 365 × 1.255 = 1649.075 → 1649.07`), but the on-screen reply rendered as:
   > Based on your input, running a 150-watt appliance for 24 hours a day will cost you approximately EC*135.54permonth**(orabout**EC*1,649.07 per year).
   The `**bold**` markers show up as literal asterisks, "EC$135.54" loses its `$` and its spacing and renders squished and italicized, and this pattern repeats between the two dollar amounts. Everything *outside* the two `$` signs (the sentence before "EC$135.54" and after the closing math span) renders normally.
2. This is Streamlit's built-in inline-LaTeX support (present in the installed version, 1.54.0 — added well before that release) doing exactly what it's designed to do: treat a single `$` as "start math mode" and the next `$` as "end math mode", then hand everything in between to the KaTeX renderer instead of the plain Markdown parser. Two dollar-amounts in one message is exactly the two-`$`-characters trigger.
3. This is **not new** — it was not introduced by today's fuel-surcharge fix. `calculator_tool()`'s reply format has always been `"...costs EC$X per month and EC$Y per year at a rate of EC$Z/kWh"` (three literal `$` characters, always). It simply never got caught before because, per this project's own established pattern (see the "only live-browser QA catches it" gotchas already logged for this codebase), no earlier session completed a full live round-trip through the actual calculator conversation flow with the rendered page actually inspected — a static check (`py_compile`, `run_tests.py`, a headless boot check) cannot catch a markdown-rendering artifact, only actually looking at the rendered page can.
4. Five call sites in `streamlit_app()` render text that can contain a customer-facing `$` amount and are exposed to this bug:
   - `lucelec_rag_bot.py:3968` — `st.markdown(m["content"])`, the chat-history redisplay loop (every past reply, every time the page reruns).
   - `lucelec_rag_bot.py:3973` — `st.caption(h["text"])`, source-excerpt text inside the history loop's "Sources used" expander (document excerpts can themselves contain `EC$` amounts, e.g. tariff figures).
   - `lucelec_rag_bot.py:4020` — `st.write_stream(_stream_words(out["reply"]))`, the live streaming reply for the current turn — this is the one directly reproduced above.
   - `lucelec_rag_bot.py:4062` — `st.caption(h["text"])`, source-excerpt text in the live turn's "Sources used" expander.
   - `lucelec_rag_bot.py:4322` — `st.caption(h["text"])`, the admin-only "RAG Search Test" diagnostic tab (`tab_sources`) — same pattern, staff-facing.
5. The text stored in `st.session_state.messages` (line 4066: `{"role": "assistant", "content": out["reply"], ...}`) and the text passed to TTS (`generate_google_tts(out["reply"], ...)`, `generate_elevenlabs_tts(out["reply"])`, lines ~4039-4044) must stay **unescaped** — escaping is a display-time concern only. TTS would mispronounce or speak a literal backslash if given escaped text, and history should store what the model actually said, re-escaping fresh every time it's rendered.

Fix: one small, pure function that escapes literal `$` to `\$` (Streamlit's documented way to render a literal dollar sign instead of triggering math mode), applied only at the five markdown-rendering call sites — nothing about the model's raw output, TTS input, or stored history changes.

## Global Constraints

- No new dependencies.
- The new function must be pure (string in, string out, no Streamlit calls) and module-level (not nested inside `streamlit_app()`), so it's directly unit-testable via `run_tests.py` the way `dress()`/`translate()` are — this project's existing tests can only reach into `streamlit_app()`'s nested functions via `inspect.getsource()` string-matching, which is a weaker test than a real function call.
- Do not change what `st.session_state.messages` stores, and do not change what's passed to `generate_google_tts()`/`generate_elevenlabs_tts()` — both must keep receiving the raw, unescaped reply text.
- Match existing code style: trailing `#` why-comments, `# FIXED: ...` markers for bugfix additions.
- Run the full suite via the project venv (`../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`). Baseline before this task: 134/136 passing, with the same 2 pre-existing, unrelated failures as always (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) — not this task's responsibility, must not regress further.

---

### Task 1: Escape literal dollar signs at every markdown-rendering call site

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py` (1 new function near `dress()`, 5 call-site wraps)
- Test: `Template-bot/files/run_tests.py` (extending Section 12 · UI polish, which already tests other `streamlit_app()` rendering behavior via `app_source`)

**Interfaces:**
- Consumes: nothing new from other tasks (this plan has one task).
- Produces:
  - `escape_markdown_dollars(text: str) -> str` — new pure module-level function, escapes every literal `$` to `\$`.
  - No other function's signature changes. `_stream_words()`, `process_chat_message()`, and the history-render loop keep their existing shapes; only what's passed *into* the render calls changes.

- [ ] **Step 1: Write the failing tests**

Open `Template-bot/files/run_tests.py`. Find Section 12 (`section("12 · UI polish")`, around line 290) and its `app_source = inspect.getsource(b.streamlit_app)` line (around line 397, near the top of that section). Immediately after the existing checks that use `app_source` (find the block ending with the `add_new_chat`/`delete_chat` loop, right before the Section 13 · Persona identity block that already exists), insert:

```python
# The reply and every source excerpt render through Streamlit's markdown
# pipeline, which treats a PAIR of literal "$" characters as inline LaTeX
# math delimiters — every calculator reply quotes 2-3 "EC$" amounts, so
# without escaping, replies render as garbled, unparsed Markdown.
check("escape_markdown_dollars exists", hasattr(b, "escape_markdown_dollars"))
check("escape_markdown_dollars escapes a single dollar sign",
      b.escape_markdown_dollars("EC$135.54") == "EC\\$135.54",
      b.escape_markdown_dollars("EC$135.54"))
check("escape_markdown_dollars escapes multiple dollar signs",
      b.escape_markdown_dollars("EC$135.54 per month and EC$1,649.07 per year")
      == "EC\\$135.54 per month and EC\\$1,649.07 per year",
      b.escape_markdown_dollars("EC$135.54 per month and EC$1,649.07 per year"))
check("escape_markdown_dollars is a no-op when there is no dollar sign",
      b.escape_markdown_dollars("no currency figures here") == "no currency figures here",
      b.escape_markdown_dollars("no currency figures here"))

check("chat history redisplay escapes dollar signs before st.markdown",
      'st.markdown(escape_markdown_dollars(m["content"]))' in app_source,
      "st.markdown(m[\"content\"]) is not wrapped with escape_markdown_dollars()")
check("live streamed reply escapes dollar signs before st.write_stream",
      'st.write_stream(_stream_words(escape_markdown_dollars(out["reply"])))' in app_source,
      "st.write_stream(_stream_words(out[\"reply\"])) is not wrapped with escape_markdown_dollars()")
caption_escape_count = app_source.count('st.caption(escape_markdown_dollars(h["text"]))')
check("every source-excerpt caption escapes dollar signs",
      caption_escape_count >= 3,
      f"expected at least 3 escaped st.caption(h['text']) call sites, found {caption_escape_count}")

# Regression guard: the raw, unescaped reply must still be what's stored in
# history and what's handed to TTS — only the render call sites should change.
check("chat history still stores the raw (unescaped) reply text",
      '{"role": "assistant", "content": out["reply"], "hits": out["hits"]}' in app_source,
      "history storage line changed shape — TTS/history must keep the raw reply")
check("TTS still receives the raw (unescaped) reply text",
      "generate_google_tts(out[\"reply\"]" in app_source
      and "generate_elevenlabs_tts(out[\"reply\"])" in app_source,
      "TTS call sites must keep passing the raw, unescaped out[\"reply\"]")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: the `escape_markdown_dollars` existence/behavior checks fail with `AttributeError` (function doesn't exist yet), and the `app_source`-based wiring checks fail because none of the five call sites are wrapped yet. The two regression-guard checks should already `PASS` — they're proving today's correct behavior (raw text in history/TTS), not new behavior.

- [ ] **Step 3: Add `escape_markdown_dollars()`**

Find, in `Template-bot/files/lucelec_rag_bot.py`:

```python
def dress(register: str, text: str) -> str:
    """Put one of the Wardrobe's outfits on a plain piece of text.

    Every part of the app dresses text through this one function, so if you
    change how a register works you change it in exactly one place.
    """
    voice = TONES.get(register, TONES[DEFAULT_REGISTER])   # .get() avoids a crash on an unknown mood
    return voice(text)                               # call that register's little function

# ---------------------------------------------------------------------
# 2.4 · DIGNITY IN WORDS (Day 4) — jargon translated into plain English
```

Replace with:

```python
def dress(register: str, text: str) -> str:
    """Put one of the Wardrobe's outfits on a plain piece of text.

    Every part of the app dresses text through this one function, so if you
    change how a register works you change it in exactly one place.
    """
    voice = TONES.get(register, TONES[DEFAULT_REGISTER])   # .get() avoids a crash on an unknown mood
    return voice(text)                               # call that register's little function


def escape_markdown_dollars(text: str) -> str:
    """Escape literal "$" so Streamlit's markdown renderer doesn't treat a
    pair of them as inline LaTeX math delimiters. Every calculator reply
    quotes 2-3 EC$ amounts, which collide with that by design — without
    this, a reply with two dollar signs renders as garbled, unparsed
    Markdown between them (bold markers show up literally, spacing
    collapses). Display-time only: the raw text stored in chat history and
    handed to text-to-speech must NOT be escaped — only what actually gets
    passed to st.markdown/st.caption/st.write_stream.
    """
    # FIXED: was unescaped everywhere the reply/source-excerpt text got
    # rendered, so any answer quoting two or more EC$ amounts (i.e. every
    # calculator answer) rendered broken.
    return text.replace("$", "\\$")

# ---------------------------------------------------------------------
# 2.4 · DIGNITY IN WORDS (Day 4) — jargon translated into plain English
```

- [ ] **Step 4: Wrap the chat-history redisplay loop**

Find:

```python
                with st.chat_message(m["role"], avatar=msg_avatar):
                    st.markdown(m["content"])
                    if m.get("hits"):
                        with st.expander(t("sources_used")):
                            for i, h in enumerate(m["hits"], 1):
                                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                                st.caption(h["text"])
```

Replace with:

```python
                with st.chat_message(m["role"], avatar=msg_avatar):
                    st.markdown(escape_markdown_dollars(m["content"]))
                    if m.get("hits"):
                        with st.expander(t("sources_used")):
                            for i, h in enumerate(m["hits"], 1):
                                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                                st.caption(escape_markdown_dollars(h["text"]))
```

- [ ] **Step 5: Wrap the live streamed reply and its source captions**

Find:

```python
                    st.write_stream(_stream_words(out["reply"]))
```

Replace with:

```python
                    st.write_stream(_stream_words(escape_markdown_dollars(out["reply"])))
```

Find (the live turn's "Sources used" expander, immediately after the `lane: ... · register: ...` caption):

```python
                    if out["hits"]:
                        with st.expander(t("sources_used")):
                            for i, h in enumerate(out["hits"], 1):
                                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                                st.caption(h["text"])
```

Replace with:

```python
                    if out["hits"]:
                        with st.expander(t("sources_used")):
                            for i, h in enumerate(out["hits"], 1):
                                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                                st.caption(escape_markdown_dollars(h["text"]))
```

- [ ] **Step 6: Wrap the admin "RAG Search Test" tab's source captions**

Find:

```python
        with tab_sources:                                
            st.subheader("RAG Search Test")
            probe = st.text_input("Test query", "how much does an ac cost") 
            for i, h in enumerate(retrieve_chunks(probe, index), 1): 
                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")   
                st.caption(h["text"])                    
```

Replace with:

```python
        with tab_sources:                                
            st.subheader("RAG Search Test")
            probe = st.text_input("Test query", "how much does an ac cost") 
            for i, h in enumerate(retrieve_chunks(probe, index), 1): 
                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")   
                st.caption(escape_markdown_dollars(h["text"]))                    
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: all Section 12 checks `PASS`, including the 9 new ones (3 pure-function behavior checks, 4 wiring checks, 2 regression guards). Total at the bottom should read **143/145 checks passed** (134 baseline + 9 new checks, all passing), with the same 2 pre-existing, unrelated failures as always and no new ones.

- [ ] **Step 8: Manually confirm against the live app**

Run the app (`streamlit run lucelec_rag_bot.py` from `Template-bot/files/`), ask the chat "how much does a 150 watt fridge cost to run for 24 hours a day", and read the rendered reply.

Expected: the reply reads as clean prose with real bold formatting — "...will cost you approximately **EC$135.54 per month** (or about **EC$1,649.07 per year**)." — not the garbled, squished, unparsed-asterisk version from the root-cause section above. Scroll away and back (or send a second message) to confirm the same reply, now in history, still renders correctly on redisplay. If accessibility TTS is enabled, confirm the spoken audio still says "one hundred thirty-five dollars fifty-four cents" (or however the TTS engine reads it) naturally, not "backslash dollar" — proving the escape never reached the TTS call.

- [ ] **Step 9: Commit**

```bash
git add "Template-bot/files/lucelec_rag_bot.py" "Template-bot/files/run_tests.py"
git commit -m "fix: escape dollar signs so Streamlit stops rendering them as LaTeX math"
```

---

## Self-Review

**1. Spec coverage:** The root-cause finding (any reply/excerpt with 2+ literal `$` renders as garbled LaTeX-math markdown) is covered end-to-end: Step 3 adds the one shared escaping function, Steps 4-6 apply it at all five identified render call sites, and Step 1's tests prove both the function's correctness in isolation and that every call site is actually wired (via `app_source` string checks, matching this file's existing convention for testing code nested inside `streamlit_app()`). The two regression guards make sure the fix didn't leak into TTS or history storage, where raw text is required.

**2. Placeholder scan:** No TBD/TODO markers. All code blocks are complete, copy-pasteable find/replace pairs. Only one task, so no "similar to Task N" references.

**3. Type consistency:** `escape_markdown_dollars(text: str) -> str` is called identically at all five sites — same function, same single positional argument, no signature drift. Nothing else in the file changes shape.

**Deliberately out of scope:** the two `st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")` lines (immediately above two of the wrapped `st.caption` calls) are NOT wrapped — `h['source']` is always a filename and `h['score']` is always a float, neither can contain a `$`, so there's nothing to escape there. Also out of scope: whether Streamlit has a global setting to disable inline LaTeX entirely instead of escaping per-call-site — escaping at the render boundary is more targeted (a future feature that legitimately wants to show real math wouldn't be silently broken) and doesn't require touching Streamlit's config.
