# L.I.A — Developer Handoff

**Project:** LUCELEC RAG Chatbot ("L.I.A" — LUCELEC Information Assistant)
**Last updated:** 2026-08-19
**Main file:** `files/lucelec_rag_bot.py` (~5,200 lines, single-file Streamlit app)
**Test suite:** `files/run_tests.py` — 197/197 passing as of this writing

This document is for whoever picks up this codebase next. It covers what the
app does, how it's built, where the sharp edges are, and what's still open.

---

## 1. What this is

A Streamlit chatbot that answers LUCELEC customer questions (appliance
running costs, tariff basics, energy-saving tips, outage status) from a set
of markdown source documents, with a real LLM (Groq/Gemini/OpenAI) on top of
retrieval when a key is configured, and a graceful offline fallback
(extractive answers + canned replies) when it isn't.

Core design rule baked into the whole app: **never invent a tariff, rate, or
account fact.** Everything customer-account-specific gets escalated to a
human desk instead of answered.

Run it:

```bash
cd Template-bot/files
pip install -r requirements.txt
streamlit run lucelec_rag_bot.py --server.port 8501
```

Staff/admin login is a link on the customer gate screen ("LUCELEC staff? Log
in here"). Credentials come from `ADMIN_USERNAME`/`ADMIN_PASSWORD` in
`.env` (first login seeds `.streamlit/users.json`, a PBKDF2-hashed
multi-user account store — see §4).

Test it:

```bash
python run_tests.py
```

---

## 2. Architecture

### 2.1 Request pipeline (LangGraph)

Every chat message goes through a LangGraph state machine, not a plain
function call:

```
guardrail → router → (social | art → chatbot → [tools loop]) → finalize
```

| Node | Job |
|---|---|
| `node_guardrail` | Hard safety refusals (red-line topics) — short-circuits straight to `END` if tripped |
| `node_router` | Classifies intent (`social` vs `domain`) and resolves the **register** (tone) for this reply |
| `node_social` | Small talk — greetings, "who are you", thanks/farewell. No document access on purpose |
| `node_art` | **A.R.T.** — Authority, Register, Territory checks (§2.2) before any domain answer is allowed |
| `chatbot` | The real answer: 7 phrase-matched "template-rule" instant replies, then RAG retrieval + LLM (or offline extractive fallback) |
| `tools` | Tool-calling loop (calculator etc.) if the LLM requests one |
| `finalize_reply` | Applies the tone wrapper (`dress()`) to the final text — **skips this if `reply` is already set** (template-rule/escalation paths set it directly) |

`GraphState` also carries `current_question` — **read this, not
`messages[0]`**, if you need "what did the customer just ask this turn."
`messages[0]` used to be safe when every turn started with exactly one
message; it stopped being safe the moment cross-turn history was added
(§2.4). `chatbot()`'s tool-calling loop can also independently grow
`messages` mid-turn, which is why it never used `messages[-1]` either.

### 2.2 A.R.T. — the three axes every domain question passes through

- **Authority** — is this person allowed to ask about a specific account? (`id_verified`)
- **Register** — what tone should the reply use? (`warm` / `formal` / `anxious` / `bereaved` / `frustrated` / `confused` / `rushed` — see `TONES`)
- **Territory** — which customer segment/rate-class rules apply? (`Domestic` / `Commercial` / `Industrial` / `Hotel / Tourism` / `Government / Public Sector` / `Agricultural`)

Any axis that can't be resolved escalates to a human desk with a specific,
non-generic reason (`escalate_message()`) instead of guessing.

**Register is sticky per session but lane-scoped**: `user["mood"]`
persists once set (so a whole worried-about-my-bill conversation stays in
that voice), but it only applies on the **domain** lane. The social lane
always re-derives register from the message itself — otherwise a mood set
during a real question bleeds into an unrelated "hi" (fixed 2026-08-19, see
§5).

**Territory can now be resolved from free chat text**, not just the
sidebar dropdown: if a domain question can't resolve territory,
`detect_territory()` checks the message against `TERRITORY_ALIASES`
("domestic", "hotel", "commercial", ...) before escalating. If it matches,
it writes straight to `st.session_state["identity_territory"]` — see the
widget-remount note in §4.

### 2.3 Retrieval

Plain TF-IDF (`tf * idf`, `retrieve_chunks()`) over `source_documents/*.md`
— no embeddings, no vector DB. `QUERY_SYNONYMS` / `expand_query_terms()`
bridges known customer-wording-vs-document-wording gaps (e.g. "create an
account" → "connection"/"application"). Adding a new synonym entry should
come with a demonstrated failing query, not a guess — see the Gotchas note
on the `"open"` regression in the project's decision history.

### 2.4 Conversation memory (added 2026-08-19)

`classify_and_route()` takes an optional `history` param — prior turns as
LangChain messages, prepended before the current one. `answer()` exposes
the same param. The UI side (`process_chat_message()`) builds it via
`build_history_messages()`, which converts `st.session_state.messages`
into LangChain messages, **bounded to the last `HISTORY_TURNS` (6)
exchanges** to cap prompt growth.

Before this, every turn was built from scratch with just the current
message — the LLM had no memory of its own prior questions. If you're
extending the pipeline, remember: `messages[0]` is no longer "the current
question" once history exists. Use `state["current_question"]`.

### 2.5 Providers

`PROVIDERS` dict (`~line 1987`) defines OpenAI / Gemini / Groq, each with a
`key_env` and a `model` default. `active_chain()` tries them in
`PROVIDER_CHAIN` order (`LLM_PROVIDER` env var pins one to the front),
falling through to the next on any exception, and finally to the offline
extractive/template path if all fail or none are configured.

**Model IDs go stale.** Groq retired `llama-3.3-70b-versatile` at some
point — every reply silently fell back to offline mode with no visible
error until someone called each provider directly to see the real
exceptions. Current default: `openai/gpt-oss-120b`. If replies look
suspiciously offline again, don't assume the code broke — check each
provider directly first:

```python
import lucelec_rag_bot as b
for p in b.active_chain():
    if b.is_configured(p):
        try:
            print(p, b.get_llm_for_provider(p).invoke([("user", "hi")]).content)
        except Exception as e:
            print(p, "FAILED:", e)
```

`GROQ_MODEL`/`GEMINI_MODEL`/`OPENAI_MODEL` env vars override the default
without a code change — check those first before editing `PROVIDERS`.

### 2.6 Streamlit UI structure

- **Customer gate** (`page_state == 'customer_gate'`, default) — Name +
  Territory (required) + Register, before any chat access.
- **Staff/admin** (`page_state == 'admin_login'` → `'admin_view'`) —
  multi-user accounts (PBKDF2-SHA256, 200k iterations, per-user salt),
  seeded from `.env` on first login attempt.
- Tabs (admin only, except Chat): Chat, Location status, Area tariffs,
  Cost calculator, Blueprint (teaching reference), Web harvest, Sources,
  Eval.
- 4 languages: English, Spanish, French, French Creole (Kwéyòl) — every
  offline fallback string and template reply is localized; live-LLM
  replies are instructed via `language=` in the system prompt.

---

## 3. The `sticky_*` widget helpers — read before touching any Settings/gate field

Three genuinely different Streamlit footguns bit this app, all around the
same pattern (a widget `key=` shared between the customer gate and the
Settings panel, which are mutually exclusive render sites):

1. **A `key`-bound widget's `session_state` entry is deleted at the end of
   any run that doesn't render it.** Fixed with `sticky_text_input` /
   `sticky_checkbox` / `sticky_selectbox` — each shadows its live value
   into a separate plain key every render, and reseeds the widget's
   `index=`/`value=` from that shadow key next render.
2. **Even with the shadow-key pattern, code positioned *earlier* in script
   order than the widget's own call site can read the shadow value one
   frame stale.** Fixed by syncing the shadow from the widget's own
   disposable key as early as possible in the script (right after
   `t()`/`t_option()` are defined), not at the widget's call site.
3. **Once a `key`-bound `st.selectbox` has rendered once, a later rerun
   that only changes `index=` does not reliably repaint the visible
   label** — even when `st.session_state` is provably correct (verified by
   querying the live DOM, not just `st.session_state`). Writing the
   widget's own key directly raises `StreamlitAPIException` if the widget
   already rendered earlier in the same script pass. Fixed with a
   `key_suffix` param on `sticky_selectbox()` — a nonce bumped only when
   *code* changes the value, forcing a genuine remount.

If you add a new field to `render_identity_fields()`, use `sticky_*`. If
you ever need to change a selectbox's value from outside the widget's own
`st.selectbox()` call, you need the `key_suffix` pattern too, not just a
session_state write.

---

## 4. Secrets & config

`.env` (gitignored) holds:

| Var | Purpose |
|---|---|
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `ELEVENLABS_API_KEY` | Provider keys |
| `LLM_PROVIDER` | Pin one provider to the front of the chain |
| `GROQ_MODEL` (etc.) | Override a provider's model without a code change |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Seeds the **first** staff account only — after that, accounts live in `.streamlit/users.json` (gitignored) |
| `SMTP_*` | Email settings, currently unused by the live login flow (see `-login_demo.py` below) |

If staff login stops working after a password change in `.env`, that's
expected — `users.json` only re-seeds on the **next login attempt with no
existing file**, not on every boot. Delete `users.json` to force a
re-seed from current `.env` values.

**`lucelec_rag_bot-login_demo.py`** is a deliberately-kept snapshot of a
2-step email/on-screen-code verification login build — built, then
reverted back to single-step login, kept for reference. Not dead code to
delete casually.

---

## 5. Known issues / open items

- **No git remote configured.** All work is local-only on `master`.
  `git push` needs a remote added first.
- **`worktree-replay-audio-dropdown` branch not merged** — a completed,
  tested replay-audio popover feature sitting on its own branch.
- **`os.environ["LLM_PROVIDER"]` mutation from the admin sidebar is
  process-wide, not per-session** — same class of bug as a prior
  session's `PERSONA` module-global leak (already fixed for that case).
  One staff member's provider choice currently affects every concurrent
  session. Flagged, not yet fixed.
- **Dark mode toggle label itself is untranslated** — low priority,
  consistent with other admin-only chrome.
- **Gemini free tier is rate-limited to 20 requests/day** — expect
  `429 RESOURCE_EXHAUSTED` under any real testing load. Groq is first in
  the provider chain specifically so this doesn't block demos.
- **As of 2026-08-19, `lucelec_rag_bot.py` and `run_tests.py` have
  uncommitted local changes** (6 bug fixes — see §6). Review and commit
  before anyone else pulls.

---

## 6. 2026-08-19 session — six live-reported bugs

All found from real user screenshots/transcripts, all fixed and
live-verified, all covered by `run_tests.py` (197/197):

1. **Sticky register bled into small talk** — "hi" got wrapped in the
   anxious-tone prefix. Fixed by lane-scoping the sticky mood (§2.2).
2. **Territory dropdown didn't visually update** after a spoken answer in
   chat, despite correct `session_state` — third widget-key gotcha (§3).
3. **Groq's model was retired**, silently forcing every reply offline —
   swapped model (§2.5).
4. **In-app Eval tab used live session identity**, not a fixed test
   persona — spurious failures. Added `EVAL_USER` fixture; also added 4
   register-coverage test cases fulfilling an old `TODO_students` comment.
5. **No conversation memory across turns** — the bot repeated its own
   clarifying questions and ignored customers' answers to them. Added
   history threading (§2.4). This was the significant one architecturally.
6. **"What does L.I.A stand for?" dead-ended** with "not in my
   documents" — added to the social-lane identity signals; both offline
   and live paths now state the acronym (LUCELEC Information Assistant).

Full narrative writeups (root cause, fix, verification) live in this
project's dev-log vault note if you have access to it — this section is
the condensed version.

---

## 7. Where to look for what

| Need to... | Look at |
|---|---|
| Change what counts as a domain vs. social question | `classify_intent()`, `SOCIAL_SIGNALS`, `domain_words` |
| Add/change a canned instant reply | `DOMAIN_TEMPLATE_REPLIES` + the phrase list at the top of `chatbot()` |
| Add a new tone/register | `TONES` dict, `dress()` |
| Add/change territory rules | `LOCATION_CONTEXT` |
| Change what the LLM is told | `build_prompt()` (domain), `SOCIAL_PROMPT` (social) |
| Add a knowledge document | `source_documents/*.md`, or the Web harvest tab (goes through `pending_review/` + `approve_harvest()` — never live until approved) |
| Add an eval regression case | `EVAL_SET` in `run_eval()`'s section — remember template-rule replies skip `dress()` |
