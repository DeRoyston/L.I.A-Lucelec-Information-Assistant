# Retrieval Vocabulary Gap Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the bot from missing an on-topic, approved document in retrieval just because the customer's wording ("create an account") never literally appears in it (which says "new connection", "application") — and from instead surfacing an irrelevant homepage-nav chunk that happens to contain the literal word "Account".

**Architecture:** `retrieve_chunks()` (`lucelec_rag_bot.py:1685`) is plain TF-IDF keyword overlap with zero semantic understanding — the function's own comment already flags this as a known limitation (`TODO_students (stretch): replace this with sentence-transformers embeddings`). The fix does not touch that scoring math or add an embeddings dependency (out of scope, flagged by the codebase itself as future stretch work). Instead it adds a small, literal query-term synonym expansion applied before scoring: a handful of customer-phrasing words get a few extra document-phrasing words added to the same scoring bag, so genuine topical overlap can be found even when the exact words differ. Every existing scoring line is untouched; only the list of terms fed into it grows for a few specific trigger words.

**Tech Stack:** Python 3, stdlib only (`re`, `collections.Counter`, `math` — all already imported). No new dependencies. Test runner: `run_tests.py` via `../venv/Scripts/python.exe` from `Template-bot/files/`.

**Spec:** None on disk — this plan's spec is the root-cause analysis below, derived from a live transcript ("can you tell me how to create an account?" → "That isn't in my LUCELEC documents", citing only `web-index.md` at score 0.3153) and direct empirical measurement against the real document index in this repo.

## Root cause (read this before touching code)

1. `tokenize()` (`1660-1666`) does plain lowercase word-splitting with stopword removal — no stemming, no synonyms. `create` and `applying` are different tokens forever; they never overlap no matter how related the ideas are.
2. `retrieve_chunks()` (`1685-1709`) scores every chunk by summing `tf(term) * idf(term)` for each term in the tokenized query, normalized by chunk length. This is pure literal-string overlap.
3. The approved, indexed document that actually answers "how do I create an account" is `source_documents/web-content-new-connections.md` — it describes the 5-step new-connection process. It never uses the words "account" or "create" anywhere; it consistently says "connection", "application", "applying", "applicant". Verified directly: `grep -oE "[a-zA-Z]+" web-content-new-connections.md | sort -u` contains `application`, `applications`, `applying`, `connection`, `connections`, `register` — never `account` or `create`.
4. Meanwhile `source_documents/web-index.md` (the harvested homepage) contains the nav link text "Check Your Account Now" — the literal word "Account" — so it scores a nonzero match on the customer's query purely by coincidence, despite having zero actual instructional content.
5. **Measured directly against this repo's real index** (`Template-bot/files/`, via `load_chunks()`/`build_index()`):
   ```
   query: "can you help me create an account" → tokenize() → ['help', 'create', 'account']
   retrieve_chunks(query, index, k=5):
     0.3153  web-index.md              (nav dump — no instructional content)
   ```
   `web-content-new-connections.md` doesn't even appear — its score is 0 (zero term overlap). This is exactly the transcript's bug: the model gets one weak, irrelevant chunk, correctly judges it insufficient per `MASTER_PROMPT`'s rule ("If they ask a non-outage factual question that is not in the excerpts, reply exactly: 'That isn't in my LUCELEC documents.'"), and refuses — even though the real answer was sitting in the index the whole time.
6. **Confirmed the fix works**, same measurement, terms `['help', 'create', 'account']` expanded with `['connection', 'application', 'applying']`:
   ```
     0.5497  web-content-new-connections.md  (the actual 5-step process)
     0.4938  web-content-new-connections.md
     0.4812  web-content-new-connections.md
     0.3455  web-content-new-connections.md
     0.3294  web-content-new-connections.md
   ```
   `web-content-new-connections.md` now dominates the top 5, `web-index.md` drops out of contention entirely (its own score is unchanged at 0.3153, now correctly ranked below the on-topic content instead of being the only hit).

Fix: a small, explicit synonym table for words known to cause this exact class of mismatch (starting with the one proven in the transcript), applied as a pure term-expansion step before scoring — safe by construction, since any synonym absent from a given chunk contributes exactly 0 to that chunk's score (`idf.get(t, 0.0)`), and the expansion only activates for the specific trigger words in the table, leaving every other query's ranking untouched.

## Global Constraints

- No new dependencies. Stdlib only.
- Do not modify the TF-IDF scoring formula itself (`tf`, `idf`, the `score /=` normalization line) — the fix is additive (more terms in, same scoring), not a rewrite.
- Do not touch `source_documents/*.md` content in this task — this is a retrieval-code fix, not a content-editing fix (content-stuffing a doc with extra keywords is fragile and doesn't generalize to the next vocabulary mismatch; the synonym table does, and is the more defensible root-cause fix).
- Keep the synonym table small and evidence-based: only add entries you can point to a real, demonstrated mismatch for (the plan currently has exactly one, "account" — expand cautiously, don't pre-guess a large taxonomy).
- Match existing code style: trailing `#` why-comments, `# FIXED: ...` markers for bugfix additions.
- Run the full suite via the project venv (`../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`). Baseline before this task: 120/122 passing, with the same 2 pre-existing, unrelated failures as always (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) — not this task's responsibility, must not regress further.

---

### Task 1: Bridge customer-vs-document vocabulary gaps in retrieval

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:1685` (`retrieve_chunks()`) and immediately above it
- Test: `Template-bot/files/run_tests.py` (new Section 14, before RESULTS)

**Interfaces:**
- Consumes: nothing new from other tasks (this plan has one task).
- Produces:
  - `QUERY_SYNONYMS: dict[str, list[str]]` — module-level constant, term → list of document-vocabulary synonyms.
  - `expand_query_terms(q_terms: list) -> list` — new pure function, takes tokenized query terms, returns the same list with each term's known synonyms appended.
  - `retrieve_chunks()`'s signature and return shape are unchanged; only its internal term list is expanded before scoring.

- [ ] **Step 1: Write the failing tests**

Open `Template-bot/files/run_tests.py`. Insert a new section immediately before the `RESULTS` section (after the persona `answer()` check that ends around line 479, before the `# ====` / `section("RESULTS")` block at line 482). Insert this block:

```python
# =====================================================================
section("14 · Retrieval vocabulary gaps (customer wording vs. document wording)")
# =====================================================================

# expand_query_terms() must add known synonyms and leave everything else
# untouched — a pure, safe-by-default transformation.
check("expand_query_terms adds connection/application for 'account'",
      set(b.expand_query_terms(["account"])) >= {"account", "connection", "application"},
      b.expand_query_terms(["account"]))
check("expand_query_terms is a no-op for terms with no synonym entry",
      b.expand_query_terms(["fridge", "kwh"]) == ["fridge", "kwh"],
      b.expand_query_terms(["fridge", "kwh"]))
check("expand_query_terms never drops the original terms",
      "account" in b.expand_query_terms(["account"]),
      b.expand_query_terms(["account"]))

# The actual transcript bug: this exact query must now surface the real
# new-connections procedure, not just the homepage nav dump.
hits = b.retrieve_chunks("can you help me create an account", index, k=5)
hit_sources = [h["source"] for h in hits]
check("'create an account' retrieves the new-connections document",
      "web-content-new-connections.md" in hit_sources, hit_sources)
check("'create an account' ranks new-connections above the homepage nav dump",
      hits and hits[0]["source"] == "web-content-new-connections.md",
      hit_sources)

# Regression guard: an unrelated query must not be affected by the
# synonym table (none of its terms are trigger words).
unrelated_hits = b.retrieve_chunks("how much does an AC cost to run", index, k=3)
check("unrelated query retrieval is unaffected by the synonym table",
      unrelated_hits and unrelated_hits[0]["source"] != "web-content-new-connections.md",
      [h["source"] for h in unrelated_hits])

# End-to-end: the offline pipeline (no API key needed, see Section 6)
# must now cite the real document for the transcript's exact question.
with quiet():
    account_answer = b.answer("can you help me create an account?", index, verified)
check("offline answer to 'create an account' cites the new-connections document",
      any(h["source"] == "web-content-new-connections.md" for h in account_answer.get("hits", [])),
      [h["source"] for h in account_answer.get("hits", [])])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 14 fails on every check — `expand_query_terms` doesn't exist yet (`AttributeError`), and the retrieval checks fail because `web-content-new-connections.md` isn't in the hit list for the account query (matches the empirical measurement in the root-cause section above: 0 hits from that document today).

- [ ] **Step 3: Add `QUERY_SYNONYMS` and `expand_query_terms()`, wire into `retrieve_chunks()`**

Find, in `Template-bot/files/lucelec_rag_bot.py`:

```python
def retrieve_chunks(query: str, index: dict, k: int = TOP_K) -> list:
    """Score every chunk against the question and return only the best k.

    Sending all chunks would be slow, expensive, and would bury the good
    paragraph in noise. Sending the best three is called Selective Retrieval.

    TODO_students (stretch): replace this with sentence-transformers
    embeddings and compare both on your eval set. The comparison is the point.
    """
    q_terms = tokenize(query)                        # clean up the question into words
    if not q_terms:                                  # nothing searchable left?
        return []                                    # return an empty list
```

Replace with:

```python
# Words customers actually type that never literally appear in the
# approved source documents, mapped to the vocabulary the documents DO
# use. retrieve_chunks() is plain TF-IDF keyword overlap with no semantic
# understanding (see its TODO_students note below), so "create an
# account" and "new connection" score zero overlap even though they're
# the same request. This bridges that specific, demonstrated gap without
# an embeddings model. Keep this table small — only add an entry once
# you've measured a real mismatch, the same way "account" was added here.
QUERY_SYNONYMS = {
    "account": ["connection", "application"],
    "create":  ["application", "applying"],
    "open":    ["application", "applying"],
}


def expand_query_terms(q_terms: list) -> list:
    """Add each term's known synonyms to the scoring bag, so a customer's
    wording and a document's wording can overlap even when the exact
    words differ. A term with no entry in QUERY_SYNONYMS passes through
    unchanged, and a synonym absent from a given chunk contributes 0 to
    that chunk's score (see idf.get(t, 0.0) below) — so this is a safe
    no-op for every query that doesn't hit the table."""
    expanded = list(q_terms)
    for t in q_terms:
        expanded.extend(QUERY_SYNONYMS.get(t, []))
    return expanded


def retrieve_chunks(query: str, index: dict, k: int = TOP_K) -> list:
    """Score every chunk against the question and return only the best k.

    Sending all chunks would be slow, expensive, and would bury the good
    paragraph in noise. Sending the best three is called Selective Retrieval.

    TODO_students (stretch): replace this with sentence-transformers
    embeddings and compare both on your eval set. The comparison is the point.
    """
    q_terms = tokenize(query)                        # clean up the question into words
    if not q_terms:                                  # nothing searchable left?
        return []                                    # return an empty list
    q_terms = expand_query_terms(q_terms)             # FIXED: bridge customer-vs-document vocabulary gaps (e.g. "account" -> "connection")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: Section 14 all `PASS`. Total at the bottom should read **128/130 checks passed** (120 baseline + 8 new checks in Section 14, all passing), with the same 2 pre-existing, unrelated failures as always and no new ones.

- [ ] **Step 5: Manually confirm against the original transcript**

If an LLM provider key is configured, run the app (`streamlit run lucelec_rag_bot.py` from `Template-bot/files/`) and ask: "can you tell me how to create an account?"

Expected: the bot now cites `web-content-new-connections.md` and describes the actual 5-step process (licensed-electrician inspection, National ID, land register, security deposit, distance-from-pole check) instead of replying "That isn't in my LUCELEC documents." If no provider key is configured, this step is informational only — the fix itself is fully verified by Step 4.

- [ ] **Step 6: Commit**

```bash
git add "Template-bot/files/lucelec_rag_bot.py" "Template-bot/files/run_tests.py"
git commit -m "fix: bridge customer-vs-document vocabulary gaps in chunk retrieval"
```

---

## Self-Review

**1. Spec coverage:** The transcript symptom (bot refuses "how do I create an account" despite the answer being indexed) is covered end-to-end: Step 3 adds the synonym expansion, proven against this repo's real index in the root-cause section before writing any code. Both the direct unit-level checks (`expand_query_terms` behavior) and the end-to-end check (`answer()` citing the right document for the exact transcript question) are exercised by Section 14 before the fix (Step 2) and confirmed after (Step 4).

**2. Placeholder scan:** No TBD/TODO markers introduced (the pre-existing `TODO_students (stretch)` comment is left untouched, as required — it correctly describes a much larger future change, not this task). Every code block is complete and copy-pasteable. Only one task, so no "similar to Task N" references.

**3. Type consistency:** `expand_query_terms(q_terms: list) -> list` is called exactly once, inside `retrieve_chunks()`, immediately after the existing `tokenize()` call — no other function needs to know about it. `QUERY_SYNONYMS` is read only inside `expand_query_terms()`. No other function signature in the file changes.

**Deliberately out of scope:** replacing TF-IDF with semantic embeddings (the codebase's own `TODO_students (stretch)` marker — a real dependency addition and index-rebuild, not a bugfix); rewriting `source_documents/*.md` content to include more keywords (content-editing is fragile per-document, the synonym table is the reusable fix); and expanding `QUERY_SYNONYMS` beyond the one measured, demonstrated mismatch plus its two closest variants (`create`, `open` — the same "start new service" intent family) — adding more entries without a measured failure to point at would be speculative, not root-cause-driven.
