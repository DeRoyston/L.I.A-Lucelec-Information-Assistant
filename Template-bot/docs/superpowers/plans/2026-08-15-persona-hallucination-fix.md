# Persona Hallucination Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the bot from addressing real customers by a fabricated name ("Mrs. Augustin") and inventing a fake backstory for them, and stop that identity data from being a shared global that can leak between concurrent staff sessions.

**Architecture:** `PERSONA` is a module-level Python dict — a "Week 1 Blueprint" teaching artifact (see `lucelec_rag_bot.py:501-512`) meant as design-doc reference, showing what one archetypal target user looks like. It is currently also read directly by both live prompt templates (`MASTER_PROMPT` via `build_prompt()`, `SOCIAL_PROMPT` via `social_reply()`) as if it described whoever is actually chatting right now. The fix threads a real, session-scoped `persona_name`/`persona_who` — sourced from the existing "who's in front of you" sidebar field, defaulting to an explicit "don't guess" instruction when nothing was entered — through `st.session_state` → `classify_and_route()` → `GraphState` → `chatbot()`/`node_social()` → `build_prompt()`/`social_reply()`. The module-level `PERSONA` dict itself is untouched; it keeps its documentation role (still shown in the admin "Blueprint" tab).

**Tech Stack:** Python 3, Streamlit `st.session_state`, LangGraph `GraphState`. No new dependencies. Test runner: `run_tests.py` via `../venv/Scripts/python.exe` from `Template-bot/files/`.

**Spec:** None on disk — this plan's spec is the root-cause analysis below, derived from a live transcript ("hi can you help me register a new account?" → "Hello Mrs. Augustin, I'd be happy to help...") and direct inspection of `lucelec_rag_bot.py`.

## Root cause (read this before touching code)

1. `PERSONA` (`lucelec_rag_bot.py:505-512`) is a **module-level global dict**, seeded with a fictional teaching example: `"name": "Mrs. Augustin"`, `"who": "a homeowner in Castries, 45, managing a tight household budget"`. Its comment block (`501-503`) makes clear this is a Week-1 prompt-engineering exercise ("One person, not 'customers'. If you cannot picture them standing in front of you, the persona is not finished") — a design reference, not live session data.
2. Two live prompt templates read it directly as fact about whoever is chatting:
   - `build_prompt()` (`2023-2043`, the domain-lane `MASTER_PROMPT` builder): `persona=PERSONA["who"]` at line 2029.
   - `social_reply()` (`2333-2373`, the social-lane `SOCIAL_PROMPT` builder): `persona_name=PERSONA.get("name", ...)`, `persona_who=PERSONA.get("who", ...)` at lines 2341-2342.
3. There IS an override mechanism — the "who's in front of you" sidebar field (`3775-3784`, `t("user_in_front_header")`/`c_name` text input) — but it mutates the SAME module-level `PERSONA` dict:
   ```python
   if c_name.strip():
       PERSONA["name"] = c_name.strip()
       PERSONA["who"] = f"a customer named {c_name.strip()}"
   else:
       PERSONA["name"] = "a customer"
       PERSONA["who"] = "a LUCELEC customer"
   ```
   Two problems: (a) if that sidebar code path never runs for a given session (e.g. a script/CLI/eval call through `answer()` directly, bypassing the full Streamlit render), `PERSONA` never leaves its hardcoded "Mrs. Augustin" seed — which is exactly what the transcript shows; (b) because Streamlit reruns execute inside the same server **process**, mutating a module-level dict is **shared mutable state across every concurrent session** on that process — one staff member typing a customer's name can bleed into another staff member's simultaneous conversation. This app already supports multiple concurrent staff logins (`list_staff_accounts()`, `is_admin` branching nearby), so this is a real cross-session leak risk, not just a hypothetical.
4. Net effect: the model is handed a specific fabricated name and backstory as established fact ("You are speaking to: a homeowner in Castries, 45, managing a tight household budget" / "You are talking to Mrs. Augustin, who a homeowner..."), and — being told to "reply like a friendly human being would" — it greets the real customer by that fictional name.

Fix: make `persona_name`/`persona_who` per-session (`st.session_state`, seeded to `None` by `initialize_sidebar_state()`), thread them explicitly through every layer between the sidebar and the two prompt builders (mirroring how `language` is already threaded end-to-end), and give both prompt builders a safe, explicit fallback when nothing is known — an instruction not to guess — instead of a fabricated identity.

## Global Constraints

- No new dependencies.
- `PERSONA` module dict (`505-512`) and its display in the admin "Blueprint" tab (`4201-4206`, `tab_blueprint`) are untouched — they remain valid design-doc reference material. Only the two live prompt builders stop *reading* from it.
- Preserve existing behavior for real names: when a session has confirmed a customer name, both lanes must still use it (this is not a "remove personalization" fix, only a "don't fabricate one" fix).
- `build_prompt()` stays a pure function (already is); the new `build_social_prompt()` helper introduced for the social lane must also be pure (string in, string out, no I/O) so it's directly testable without a live LLM call, mirroring `build_prompt()`'s existing pattern.
- Match the existing code style: trailing `#` why-comments, `# FIXED: ...` markers for bugfix additions (see the precedent already in the file).
- Run the full suite via the project venv (`../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`). Baseline before this task: 111/113 passing, with the same 2 pre-existing, unrelated failures as always (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) — not this task's responsibility, must not regress further.

---

### Task 1: Session-scope the customer persona; stop fabricating identity when none is known

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py` (8 edit points, listed in Steps 3-10 below)
- Test: `Template-bot/files/run_tests.py` (new Section 13, before RESULTS)

**Interfaces:**
- Consumes: nothing new from other tasks (this plan has one task).
- Produces:
  - `build_prompt(question, hits, register=DEFAULT_REGISTER, territory=None, excel_context="", language="English", persona_who: Optional[str] = None) -> str` — signature gains one new optional kwarg; all existing callers keep working unchanged.
  - `build_social_prompt(persona_name: Optional[str], persona_who: Optional[str], language: str) -> str` — new pure function, the social-lane analogue of `build_prompt()`.
  - `social_reply(message, register, language="English", persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict` — signature gains two new optional kwargs.
  - `classify_and_route(user, message, index, excel_data=None, language="English", persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict` and `answer(question, index, user=None, excel_data=None, language="English", persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict` — both gain the same two new optional kwargs, threaded straight into `GraphState`.
  - `GraphState` gains two new optional fields: `persona_name: Optional[str]`, `persona_who: Optional[str]`.
  - `initialize_sidebar_state(state=None)` seeds `state["persona_name"] = None` and `state["persona_who"] = None` by default.

- [ ] **Step 1: Write the failing tests**

Open `Template-bot/files/run_tests.py`. Insert a new section immediately before the `RESULTS` section (after the `add_new_chat`/`delete_chat` loop that ends around line 423, before the `# ====` / `section("RESULTS")` block). Insert this block:

```python
# =====================================================================
section("13 · Persona identity (session-scoped, no fabricated names)")
# =====================================================================

# initialize_sidebar_state() must seed persona fields to None, not the
# Week 1 teaching example and not even a vague "a customer" placeholder —
# the prompt builders supply the safe "don't guess" default themselves.
fresh_state = b.initialize_sidebar_state({})
check("initialize_sidebar_state seeds persona_name to None",
      fresh_state.get("persona_name") is None, fresh_state.get("persona_name"))
check("initialize_sidebar_state seeds persona_who to None",
      fresh_state.get("persona_who") is None, fresh_state.get("persona_who"))

# build_prompt() must not fall back to the module-level PERSONA teaching
# example. Poison it with a sentinel to prove real decoupling, not just
# "the test happens not to notice".
_real_persona_who = b.PERSONA["who"]
b.PERSONA["who"] = "SENTINEL_WEEK1_EXAMPLE_MUST_NOT_LEAK"
try:
    no_persona_prompt = b.build_prompt("how much does a fridge cost to run", [],
                                        b.DEFAULT_REGISTER, None)
    check("build_prompt with no persona_who does not leak the module PERSONA",
          "SENTINEL_WEEK1_EXAMPLE_MUST_NOT_LEAK" not in no_persona_prompt,
          no_persona_prompt[:200])
    check("build_prompt with no persona_who states it must not guess",
          "do not guess" in no_persona_prompt.lower(),
          no_persona_prompt[:200])

    named_prompt = b.build_prompt("how much does a fridge cost to run", [],
                                   b.DEFAULT_REGISTER, None,
                                   persona_who="a customer named Ms. Felicien")
    check("build_prompt with a real persona_who includes it",
          "Ms. Felicien" in named_prompt, named_prompt[:200])
finally:
    b.PERSONA["who"] = _real_persona_who

# build_social_prompt() is the social-lane analogue — same two guarantees.
no_persona_social = b.build_social_prompt(None, None, "English")
check("build_social_prompt with no persona does not mention Augustin",
      "Augustin" not in no_persona_social, no_persona_social[:200])
check("build_social_prompt with no persona states it must not guess",
      "do not guess" in no_persona_social.lower(), no_persona_social[:200])

named_social = b.build_social_prompt("Ms. Felicien", "a customer named Ms. Felicien", "English")
check("build_social_prompt with a real persona includes it",
      "Ms. Felicien" in named_social, named_social[:200])

# End-to-end: answer() must accept persona_name/persona_who without
# raising, and thread them all the way through GraphState.
with quiet():
    persona_answer = b.answer("how much does a fridge cost to run", index, verified,
                               persona_name="Ms. Felicien",
                               persona_who="a customer named Ms. Felicien")
check("answer() accepts persona_name/persona_who and still replies",
      len(persona_answer["reply"]) > 0, persona_answer.get("reply", "")[:80])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 13 fails with `AttributeError`/`TypeError`-shaped messages — `build_social_prompt` doesn't exist yet, `build_prompt()` doesn't accept `persona_who`, `initialize_sidebar_state({})` doesn't set `persona_name`/`persona_who` keys (so `.get()` returns `None` today by accident, but poisoning `PERSONA["who"]` and checking it doesn't leak into `build_prompt()`'s output WILL fail since today it does leak).

- [ ] **Step 3: `initialize_sidebar_state()` — seed persona defaults**

In `Template-bot/files/lucelec_rag_bot.py`, find:

```python
    state.setdefault("pending_voice_text", "")
    state.setdefault("show_voice_widget", False)
    state.setdefault("show_settings", False)
    return state
```

Replace with:

```python
    state.setdefault("pending_voice_text", "")
    state.setdefault("show_voice_widget", False)
    state.setdefault("show_settings", False)
    # Who the bot is actually speaking to THIS session, from the "who's in
    # front of you" sidebar field — never the Week 1 PERSONA teaching
    # example, and never guessed. None until a staff member confirms a name.
    state.setdefault("persona_name", None)
    state.setdefault("persona_who", None)
    return state
```

- [ ] **Step 4: `build_prompt()` — accept `persona_who`, stop reading the module global**

Find:

```python
def build_prompt(question: str, hits: list, register: str = DEFAULT_REGISTER,
                 territory: Optional[dict] = None, excel_context: str = "", language: str = "English") -> str:
    """Fill in MASTER_PROMPT with blueprint, document chunks, Excel knowledge, and language."""
    return MASTER_PROMPT.format(
        bot_name=BOT_NAME,
        client=CLIENT,
        persona=PERSONA["who"],
        feeling=EMPATHY_MAP["feels"],
```

Replace with:

```python
def build_prompt(question: str, hits: list, register: str = DEFAULT_REGISTER,
                 territory: Optional[dict] = None, excel_context: str = "", language: str = "English",
                 persona_who: Optional[str] = None) -> str:
    """Fill in MASTER_PROMPT with blueprint, document chunks, Excel knowledge, and language.

    persona_who comes from THIS session's "who's in front of you" sidebar
    field — never the Week 1 PERSONA teaching example (that dict is design
    documentation, not live session data), and never guessed when unknown.
    """
    # FIXED: Was PERSONA["who"] — leaked the Week 1 teaching example's fake
    # name/backstory into every real conversation that never touched the
    # sidebar field. Now session-scoped, with an explicit anti-guessing
    # instruction when the session hasn't told us who this is.
    persona_text = persona_who or (
        "a LUCELEC customer whose name has not been given — do not guess or invent one"
    )
    return MASTER_PROMPT.format(
        bot_name=BOT_NAME,
        client=CLIENT,
        persona=persona_text,
        feeling=EMPATHY_MAP["feels"],
```

- [ ] **Step 5: Add `build_social_prompt()`, rewrite `social_reply()` to use it**

Find:

```python
def social_reply(message: str, register: str, language: str = "English") -> dict:
    """Answer small talk in the user's chosen language."""
    kind = social_intent_kind(message)

    # FIXED: Added language=language to prompt formatting
    system = SOCIAL_PROMPT.format(
        bot_name=BOT_NAME,
        client=CLIENT,
        persona_name=PERSONA.get("name", "a customer"),
        persona_who=PERSONA.get("who", "is a LUCELEC customer"),
        language=language
    )
```

Replace with:

```python
def build_social_prompt(persona_name: Optional[str], persona_who: Optional[str], language: str) -> str:
    """Fill in SOCIAL_PROMPT. Same rule as build_prompt(): persona_name/
    persona_who come from THIS session's sidebar field, never the Week 1
    PERSONA teaching example, and never guessed when unknown."""
    # FIXED: Was PERSONA.get("name"/"who") — same leak as build_prompt(),
    # in the lane with the LEAST grounding (no documents, so nothing stops
    # the model running with a fabricated identity once it's been handed one).
    name = persona_name or "the customer"
    who = persona_who or (
        "a LUCELEC customer whose name has not been given — do not guess or invent one"
    )
    return SOCIAL_PROMPT.format(
        bot_name=BOT_NAME,
        client=CLIENT,
        persona_name=name,
        persona_who=who,
        language=language
    )


def social_reply(message: str, register: str, language: str = "English",
                  persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict:
    """Answer small talk in the user's chosen language."""
    kind = social_intent_kind(message)

    system = build_social_prompt(persona_name, persona_who, language)
```

- [ ] **Step 6: `GraphState` — add the two new fields**

Find:

```python
class GraphState(TypedDict):
    messages: Annotated[list, add_messages] 
    user: dict 
    index: dict 
    excel_data: list # <--- MUST BE HERE
    language: str # NEW: Tracks the user's chosen language
    register: str # The tone to dress the final reply in
```

Replace with:

```python
class GraphState(TypedDict):
    messages: Annotated[list, add_messages] 
    user: dict 
    index: dict 
    excel_data: list # <--- MUST BE HERE
    language: str # NEW: Tracks the user's chosen language
    persona_name: Optional[str] # Confirmed customer name for THIS session, or None
    persona_who: Optional[str] # Confirmed customer description for THIS session, or None
    register: str # The tone to dress the final reply in
```

- [ ] **Step 7: `node_social()` — pass persona through to `social_reply()`**

Find:

```python
def node_social(state: GraphState):
    """Answers small talk using language and register rules."""
    user_msg = state["messages"][-1].content
    
    # FIXED: Passes state["language"] into social_reply!
    chat = social_reply(
        user_msg, 
        state["register"], 
        language=state.get("language", "English")
    )
```

Replace with:

```python
def node_social(state: GraphState):
    """Answers small talk using language and register rules."""
    user_msg = state["messages"][-1].content
    
    # FIXED: Passes state["language"] into social_reply!
    chat = social_reply(
        user_msg, 
        state["register"], 
        language=state.get("language", "English"),
        persona_name=state.get("persona_name"),
        persona_who=state.get("persona_who")
    )
```

- [ ] **Step 8: `chatbot()` node — pass persona through to `build_prompt()`**

Find:

```python
    # 3. Build prompt with Excel context and Language
    system_prompt = build_prompt(safe_q, hits, state["register"], state["territory"], excel_context=excel_context, language=state["language"])
```

Replace with:

```python
    # 3. Build prompt with Excel context and Language
    system_prompt = build_prompt(safe_q, hits, state["register"], state["territory"], excel_context=excel_context,
                                  language=state["language"], persona_who=state.get("persona_who"))
```

- [ ] **Step 9: `classify_and_route()`/`answer()` — accept and thread persona through**

Find:

```python
def classify_and_route(user: dict, message: str, index: dict, excel_data: list = None, language: str = "English") -> dict: 
    initial_state = { 
        "messages": [HumanMessage(content=message)], 
        "user": user, 
        "index": index, 
        "excel_data": excel_data or [], 
        "language": language, # NEW: Feed into memory
        "reply": "",
        "hits": [], 
        "escalated": False, 
        "axis": "-",
        "register": "", 
        "territory": None,
        "intent": "domain", # Default, overridden by router
        "provider": "",
        "model": ""
    }
```

Replace with:

```python
def classify_and_route(user: dict, message: str, index: dict, excel_data: list = None, language: str = "English",
                        persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict: 
    initial_state = { 
        "messages": [HumanMessage(content=message)], 
        "user": user, 
        "index": index, 
        "excel_data": excel_data or [], 
        "language": language, # NEW: Feed into memory
        "persona_name": persona_name, # FIXED: Session-scoped, was a module global
        "persona_who": persona_who,
        "reply": "",
        "hits": [], 
        "escalated": False, 
        "axis": "-",
        "register": "", 
        "territory": None,
        "intent": "domain", # Default, overridden by router
        "provider": "",
        "model": ""
    }
```

Find:

```python
def answer(question: str, index: dict, user: Optional[dict] = None, excel_data: list = None, language: str = "English") -> dict: 
    user = user or {"id_verified": True, "mood": DEFAULT_REGISTER, "segment": "Domestic"} 
    return classify_and_route(user, question, index, excel_data, language)
```

Replace with:

```python
def answer(question: str, index: dict, user: Optional[dict] = None, excel_data: list = None, language: str = "English",
           persona_name: Optional[str] = None, persona_who: Optional[str] = None) -> dict: 
    user = user or {"id_verified": True, "mood": DEFAULT_REGISTER, "segment": "Domestic"} 
    return classify_and_route(user, question, index, excel_data, language, persona_name, persona_who)
```

- [ ] **Step 10: Sidebar "who's in front of you" field — write to `st.session_state`, not the module global**

Find:

```python
                c_name = st.text_input(t("customer_name_label"), placeholder=t("customer_name_placeholder"))

                if c_name.strip():
                    PERSONA["name"] = c_name.strip()
                    PERSONA["who"] = f"a customer named {c_name.strip()}"
                else:
                    PERSONA["name"] = "a customer"
                    PERSONA["who"] = "a LUCELEC customer"
```

Replace with:

```python
                c_name = st.text_input(t("customer_name_label"), placeholder=t("customer_name_placeholder"))

                # FIXED: Was mutating the module-level PERSONA dict, which
                # is shared across every concurrent Streamlit session on
                # this process — one staff member's typed name could leak
                # into another staff member's simultaneous chat. Now
                # session-scoped, and blank stays None (build_prompt()/
                # build_social_prompt() supply the "don't guess" instruction
                # themselves) instead of the vague "a customer" placeholder.
                if c_name.strip():
                    st.session_state["persona_name"] = c_name.strip()
                    st.session_state["persona_who"] = f"a customer named {c_name.strip()}"
                else:
                    st.session_state["persona_name"] = None
                    st.session_state["persona_who"] = None
```

Then find the live chat call site immediately after it in the same function:

```python
                        out = answer(q, active_index, user, excel_data=excel_row_records, language=sim_language)
```

Replace with:

```python
                        out = answer(q, active_index, user, excel_data=excel_row_records, language=sim_language,
                                     persona_name=st.session_state.get("persona_name"),
                                     persona_who=st.session_state.get("persona_who"))
```

- [ ] **Step 11: Run the tests to verify they pass**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 13 all `PASS`. Total at the bottom should read **119/121 checks passed** (111 baseline + 8 new checks in Section 13), with the same 2 pre-existing, unrelated failures as always and no new ones.

- [ ] **Step 12: Manually confirm against the original transcript**

If an LLM provider key is configured, run the app (`streamlit run lucelec_rag_bot.py` from `Template-bot/files/`), leave the "who's in front of you" field blank, and ask: "hi can you help me register a new account?"

Expected: the bot no longer greets you as "Mrs. Augustin" or references a household-budget backstory you never gave it — it either omits a name entirely or asks who it's speaking with, and (per the Task 1 intent-routing fix already merged) still correctly cites the new-connections procedure. Then type a name into the sidebar field and ask again — expected: the bot now may address you by that name, proving personalization still works when a name is actually confirmed. If no provider key is configured, this step is informational only — the fix itself is fully verified by Step 11.

- [ ] **Step 13: Commit**

```bash
git add "Template-bot/files/lucelec_rag_bot.py" "Template-bot/files/run_tests.py"
git commit -m "fix: stop fabricating customer identity from the Week 1 teaching persona"
```

---

## Self-Review

**1. Spec coverage:** The transcript symptom (bot invents "Mrs. Augustin" and a household-budget backstory for a real customer) is covered end-to-end: Step 3 stops the default from being fabricated data, Steps 4-5 stop both prompt builders from reading the module global, Steps 6-9 thread real session data all the way from `GraphState` down through `classify_and_route`/`answer`, and Step 10 fixes the actual leak source (module-global mutation from the sidebar) plus its cross-session risk. All of it is exercised by the new Section 13 tests before the fix (Step 2) and confirmed after (Step 11).

**2. Placeholder scan:** No TBD/TODO markers. Every code block is complete and copy-pasteable. Only one task, so no "similar to Task N" references.

**3. Type consistency:** `build_prompt()`'s new `persona_who: Optional[str] = None` parameter name matches what `chatbot()` (Step 8) and `GraphState` (Step 6) call it. `social_reply()`'s new `persona_name`/`persona_who` parameters match what `node_social()` (Step 7) passes and what `build_social_prompt()` (Step 5) accepts as its first two positional parameters, in the same order. `classify_and_route()`/`answer()`'s new parameters match what the sidebar call site (Step 10) passes as keyword arguments. `initialize_sidebar_state()`'s new `persona_name`/`persona_who` keys (Step 3) match what the sidebar block (Step 10) and the UI call site (Step 10) read via `st.session_state.get(...)`.

**Deliberately out of scope:** the module-level `PERSONA` dict itself, and its display in the admin "Blueprint" tab (`4201-4206`) — both remain exactly as-is; they are legitimate design-doc reference material, not the bug. Also out of scope: the pre-existing grammar quirk where `SOCIAL_PROMPT`'s "{persona_name}, who {persona_who}" template has never actually included a linking "is" (e.g. renders "...who a customer named X" rather than "...who is a customer named X") — this predates this fix, applies identically to both the fabricated and the real-name cases, and is a cosmetic wording issue, not a hallucination risk.
