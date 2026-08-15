# Intent Routing Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `classify_intent()` from routing real customer questions ("can you help me register for an account?", "ok what is the first step?") into the fact-free social lane, where the bot has no document access and hallucinates a generic answer instead of citing the new-connections procedure.

**Architecture:** `classify_intent()` in `lucelec_rag_bot.py` is a pure string-matching function that picks "social" (small talk, no documents, `SOCIAL_PROMPT`) or "domain" (retrieval + `MASTER_PROMPT`) before any LLM call happens. The fix is two small, additive changes to that one function: (1) recognize registration/new-connection vocabulary as domain words, and (2) stop a leading filler word ("ok", "well", ...) from hijacking classification of the real question that follows it. No retrieval, prompt, or persona changes are needed — `source_documents/web-content-new-connections.md` (the approved 5-step new-connection procedure) is already indexed; it was simply never reached because the message never got to the domain lane.

**Tech Stack:** Python 3, no new dependencies. Test runner: `run_tests.py` (custom, no pytest) via the project venv at `Template-bot/venv`.

**Spec:** None on disk — this plan's spec is the root-cause analysis below, derived from the pasted bot conversation transcript and direct inspection of `lucelec_rag_bot.py`.

## Root cause (read this before touching code)

Transcript symptom:
- User: "can you help me register for an account?" → Bot gives a generic, off-topic answer about "managing your household budget."
- User: "ok what is the first step?" → Bot repeats the same generic non-answer, still no actual step.

Investigation (`lucelec_rag_bot.py`):
1. `classify_intent()` (function starts at line 2234) checks `domain_words` first, then falls back to `SOCIAL_SIGNALS` phrase matching, then a length heuristic, then defaults to `"domain"`.
2. `domain_words` (lines 2246-2254) has no registration/account/connection vocabulary. So `"can you help me register for an account?"` never hits the domain check.
3. It then matches `SOCIAL_SIGNALS["capability"]`, which includes the phrase `"can you help"` (line 2211) — a literal substring of the user's message. Intent → `"social"`.
4. The social lane's `SOCIAL_PROMPT` (line 2276) explicitly forbids stating any fact ("Do NOT state any rate, tariff, price, number, policy or fact about {client}") and never sees any retrieved document — by design, per the comment at line 2275 ("notice what is missing: any document"). It does inject `PERSONA["who"]` = `"a homeowner in Castries, 45, managing a tight household budget"` (line 507) as "who you're talking to," which is why the model's improvised, fact-free reply drifts toward budget language.
5. Second message `"ok what is the first step?"` — on its own (without "ok") this would correctly fall through to the final `return "domain"` default, since no domain word or social phrase matches it. But `SOCIAL_SIGNALS["chitchat"]` (line 2219) includes the bare word `"ok"`, which matches as the first word of the message. Intent → `"social"` again, same fact-free lane, same generic non-answer.
6. `source_documents/web-content-new-connections.md` is already approved and indexed (confirmed: `Status: APPROVED by vsmith on 2026-08-06`, and it's loaded by the `glob.glob(os.path.join(folder, "*"))` in the chunk loader). It contains the exact 5-step new-connection process the user needed. It was never reached because the message never reached the domain lane.
7. Confirmed the domain lane (`MASTER_PROMPT`, line 1986) is safe to route into: it's grounded ("Use ONLY the numbered excerpts... If they ask a non-outage factual question that is not in the excerpts, reply exactly: 'That isn't in my LUCELEC documents.'"), and `check_red_line()`'s `account_specific` refusal pattern (line 982) only matches `"my account"`, `"account number"`, `"balance"`, etc — not bare `"account"` — so routing "register for an account" to `domain` will not trip the privacy refusal.

Fix: teach `classify_intent()` (a) that registration/account/connection words mean a real question, and (b) that a leading filler word must not swallow a real question behind it.

## Global Constraints

- No new dependencies. Stdlib + existing `re` usage only.
- Match the existing code style in `lucelec_rag_bot.py`: trailing inline `#` comments explaining the "why", `# FIXED: ...` comments for bugfix additions (see line 2254 for the existing precedent).
- `classify_intent()` stays a pure function (no I/O, no LLM calls) — it's covered by the plain assertion checks in `run_tests.py`, not mocks.
- Run the full suite with the project venv: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`. Baseline today is **106/108** — 2 pre-existing, unrelated failures (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live` — both stale assertions from before `web-content-new-connections.md`/`web-index.md` were approved into `source_documents/`). This plan must not add to that failure count; it is not responsible for fixing those two.

---

### Task 1: Fix `classify_intent()` routing for registration questions and filler-prefixed follow-ups

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:2234-2271` (the `classify_intent` function)
- Test: `Template-bot/files/run_tests.py:110-124` (Section 4 · Intent routing)

**Interfaces:**
- Consumes: nothing new — `_phrase_in(phrase, text) -> bool` (existing, line 2224) and `SOCIAL_SIGNALS` (existing, line 2207) are unchanged.
- Produces: `classify_intent(message: str) -> str` keeps its existing signature and return values (`"social"` | `"domain"`). No caller elsewhere in the file needs to change.

- [ ] **Step 1: Write the failing tests**

Open `Template-bot/files/run_tests.py`. In Section 4 (starts at the `section("4 · Intent routing (social vs domain)")` call, around line 111), extend the existing `domain_cases` list and add one new guard check right after it. Replace this block:

```python
domain_cases = ["how much does an AC cost to run",
                "what appliance uses the most electricity",
                "explain my bill",
                "hi, how much does a fridge cost"]   # greeting + real question
for msg in domain_cases:
    check(f"'{msg[:34]}' → domain", b.classify_intent(msg) == "domain",
          f"got {b.classify_intent(msg)}")
```

with:

```python
domain_cases = ["how much does an AC cost to run",
                "what appliance uses the most electricity",
                "explain my bill",
                "hi, how much does a fridge cost",   # greeting + real question
                "can you help me register for an account?",  # "can you help" must not win
                "ok what is the first step?"]        # leading filler must not win
for msg in domain_cases:
    check(f"'{msg[:34]}' → domain", b.classify_intent(msg) == "domain",
          f"got {b.classify_intent(msg)}")

# A leading filler word must only be stripped when a real question follows
# it — a bare filler word, or filler + one more word, must stay social.
filler_only_cases = ["ok, thanks", "ok", "okay then"]
for msg in filler_only_cases:
    check(f"'{msg}' stays social", b.classify_intent(msg) == "social",
          f"got {b.classify_intent(msg)}")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 4 shows two new `FAIL` lines —
```
FAIL  'can you help me register f...' → domain  → got social
FAIL  'ok what is the first step...' → domain  → got social
```
The `filler_only_cases` checks should already `PASS` (they describe today's correct behavior, unchanged by the bug) — that's fine, they're regression guards for the fix in the next step, not new failing behavior.

- [ ] **Step 3: Implement the minimal fix**

Open `Template-bot/files/lucelec_rag_bot.py`. Replace the `classify_intent` function (lines 2234-2271) with:

```python
# A short filler word tacked onto the front of a real follow-up question
# must not steal the classification from the question behind it — e.g.
# "ok what is the first step?" is a domain question, not chitchat.
LEADING_FILLER = ("ok", "okay", "well", "so", "alright", "right", "yeah", "yep")


def classify_intent(message: str) -> str:
    """Decide which lane a message belongs in: "social" or "domain".

    This runs BEFORE the A.R.T. checks, and that is deliberate. You do not
    need to know somebody's customer category before you can say hello back.
    A.R.T. guards ANSWERS about the client's business, not basic manners.
    """
    low = message.lower().strip()                    # tidy it up for matching
    words = low.split()                              # split into words to measure length

    # Strip ONE leading filler word, but only when something substantial
    # follows it. A bare "ok" (or "ok, thanks") must still be social — only
    # a filler word followed by an actual question gets unwrapped.
    if len(words) > 1 and words[0].strip(",.!") in LEADING_FILLER:
        rest = low.split(None, 1)[1]
        if len(rest.split()) >= 2:                   # enough left to be a real question
            low = rest
            words = low.split()

    # Any electricity word at all means this is a real question, even if it
    # also says hello. "Hi, how much does an AC cost?" is a domain question.
    domain_words = ["kwh", "bill", "tariff", "rate", "cost", "appliance", "fridge",
                    "electricity", "power", "meter", "watt", "energy", "ac",
                    "air condition", "heater", "solar", "charge", "pay", "unit",
                    "expensive", "cheap", "save", "much", 
                    "calculate", "calc", "estimate", "math",
                    "domestic", "commercial", "industrial", "monthly", "yearly",
                    "monthly cost", "yearly cost", "monthly electricity", "price",
                    "difference", "compare", "between", "southern", "service location",
                    "vieux fort", "customer service", "technical presence",
                    "register", "registration", "account", "connection", "connect",
                    "new connection", "sign up", "signup", "apply", "application",
                    "new customer"] # FIXED: Added registration/new-connection vocabulary so "can you help me register for an account?" routes to domain, not the fact-free social lane.
    if any(_phrase_in(w, low) for w in domain_words):   # anything domain-ish present?
        return "domain"                              # treat it as a real question

    # Very long messages are almost never small talk.
    if len(words) > 12:                              # more than a dozen words
        return "domain"                              # send it down the serious lane

    for intent, phrases in SOCIAL_SIGNALS.items():   # check each social intent
        if any(_phrase_in(p, low) for p in phrases): # any of its phrases present?
            return "social"                          # this is small talk

    if len(words) <= 2 and "?" not in low:           # a two-word fragment with no question mark
        if low.replace(".", "").isdigit():           # NEW: If it's just a number (e.g. "350" or "8.5")
            return "domain"                          # It's a calculator answer, not small talk!
        return "social"                              # e.g. "morning", "ok then"

    return "domain"                                  # when unsure, treat it seriously                             
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 4 shows all `PASS`, including the two new domain cases and the three `filler_only_cases` guards. Total at the bottom should read **108/110 checks passed**, with the *same* two pre-existing, unrelated failures as baseline (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) and no new ones.

- [ ] **Step 5: Manually confirm against the original transcript**

If an LLM provider key is configured, run the app (`streamlit run lucelec_rag_bot.py` from `Template-bot/files/`) and re-ask the two questions from the transcript:
- "can you help me register for an account?"
- "ok what is the first step?"

Expected: the bot now cites the new-connections excerpt (electrician wiring inspection, National ID, land register, security deposit, distance-from-pole check) instead of the generic household-budget deflection. If no provider key is configured, this step is informational only — the routing fix itself is fully verified by Step 4.

- [ ] **Step 6: Commit**

```bash
git add "Template-bot/files/lucelec_rag_bot.py" "Template-bot/files/run_tests.py"
git commit -m "fix: route registration and filler-prefixed questions to the domain lane"
```

---

## Self-Review

**1. Spec coverage:** Both transcript symptoms (registration question, filler-prefixed follow-up) are covered by Task 1 — the domain-word addition fixes the first, the leading-filler strip fixes the second. Both are exercised by new test cases before the fix (Step 1/2) and confirmed after (Step 4).

**2. Placeholder scan:** No TBD/TODO markers. All code blocks are complete, runnable, copy-pasteable. No "similar to Task N" references — there's only one task.

**3. Type consistency:** `classify_intent(message: str) -> str` signature and return values (`"social"`/`"domain"`) are unchanged from the existing code, so every other caller in the file (routing before A.R.T. checks) keeps working without modification.

**Known pre-existing issue found during investigation, intentionally out of scope:** `run_tests.py` Section 8 has two failing checks (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) that predate this plan — they assert `web-content-new-connections.md` and `web-index.md` must NOT be in `source_documents/`, but both were legitimately approved and promoted there on 2026-08-06/07 (see the `Status: APPROVED` header in the doc). The tests need updating to assert against a still-pending example instead of a substring match that now catches approved content. Flagging for a separate, follow-up plan rather than bundling it here.
