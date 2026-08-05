"""
Test suite for the LUCELEC RAG bot.

Run it from the project folder:   python3 run_tests.py

It checks the things that actually break in front of a client: the safety
guardrails, the routing lanes, the offline fallback, the harvest quarantine,
and the file paths. Each check prints PASS or FAIL with a reason.
"""

import io
import os
import sys
import glob
import shutil
import contextlib

# Windows consoles often use a codepage that can't encode the arrow/dot
# characters this script prints (e.g. cp437/cp1252 vs. the → in FAIL lines),
# which crashes the run partway through with UnicodeEncodeError.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASSES = []
FAILS = []


def check(name, condition, detail=""):
    """Record one result."""
    if condition:
        PASSES.append(name)
        print(f"  PASS  {name}")
    else:
        FAILS.append((name, detail))
        print(f"  FAIL  {name}" + (f"  → {detail}" if detail else ""))


def section(title):
    print(f"\n{title}\n" + "-" * len(title))


# Silence the bot's own console noise while we drive it.
@contextlib.contextmanager
def quiet():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        yield buf


# =====================================================================
section("1 · Import and structure")
# =====================================================================
import lucelec_rag_bot as b   # noqa: E402

check("module imports", True)
for fn in ["answer", "classify_and_route", "load_chunks", "build_index",
           "retrieve_chunks", "check_red_line", "redact", "classify_intent",
           "social_reply", "appliance_cost", "compare_appliances",
           "harvest", "list_pending", "approve_harvest", "reject_harvest",
           "robots_allows", "is_allowed_domain", "run_eval", "doctor",
           "save_key", "delete_key", "mask_key", "extractive_answer"]:
    check(f"has {fn}()", hasattr(b, fn), f"{fn} is missing")

check("LangGraph app compiled", hasattr(b, "bot_app") and b.bot_app is not None)
check("calculator tool registered", hasattr(b, "calculator_tool"))


# =====================================================================
section("2 · Documents and paths")
# =====================================================================
with quiet():
    chunks = b.load_chunks()
    index = b.build_index(chunks)

check("documents load", len(chunks) > 0, f"got {len(chunks)} chunks")
check("index has idf scores", len(index.get("idf", {})) > 0)
check("BASE_DIR is absolute", os.path.isabs(b.BASE_DIR), b.BASE_DIR)
check("paths anchored to file, not cwd",
      b.project_path("x").startswith(b.BASE_DIR))

sources = {c["source"] for c in chunks}
check("all three seed docs indexed", len(sources) >= 3, f"sources={sources}")

# The harvested pages must NOT be in the knowledge base.
check("unapproved harvest is NOT retrievable",
      not any("new-connections" in s or s == "index.md" for s in sources),
      f"leaked into KB: {sources}")


# =====================================================================
section("3 · Guardrails and PII (the safety net)")
# =====================================================================
check("account question refused",
      b.check_red_line("what is my account balance") is not None)
check("wiring question refused",
      b.check_red_line("how do I bypass the meter") is not None)
check("ordinary question allowed",
      b.check_red_line("how much does a fridge cost to run") is None)

red = b.redact("my account is 12345678 and email me at bob@example.com")
check("account number redacted", "12345678" not in red, red)
check("email redacted", "bob@example.com" not in red, red)

phone = b.redact("call me on 758-123-4567")
check("phone redacted", "123-4567" not in phone, phone)


# =====================================================================
section("4 · Intent routing (social vs domain)")
# =====================================================================
social_cases = ["hi", "hello", "thanks", "bye", "who are you",
                "what can you do", "how are you"]
for msg in social_cases:
    check(f"'{msg}' → social", b.classify_intent(msg) == "social",
          f"got {b.classify_intent(msg)}")

domain_cases = ["how much does an AC cost to run",
                "what appliance uses the most electricity",
                "explain my bill",
                "hi, how much does a fridge cost"]   # greeting + real question
for msg in domain_cases:
    check(f"'{msg[:34]}' → domain", b.classify_intent(msg) == "domain",
          f"got {b.classify_intent(msg)}")

# The bug I fixed earlier: "yo" matching inside "you".
check("'who are you' is identity, not greeting",
      b.social_intent_kind("who are you") == "identity",
      f"got {b.social_intent_kind('who are you')}")


# =====================================================================
section("5 · A.R.T. axes")
# =====================================================================
verified = {"id_verified": True, "mood": "warm", "segment": "Domestic"}
unverified = {"id_verified": False, "mood": "warm", "segment": "Domestic"}
no_segment = {"id_verified": True, "mood": None, "segment": None}

with quiet():
    r_ok = b.answer("what appliance uses the most electricity", index, verified)
    r_unver = b.answer("what appliance uses the most electricity", index, unverified)
    r_noseg = b.answer("how much does an AC cost to run", index, no_segment)
    r_social_noseg = b.answer("hi", index, no_segment)
    r_redline = b.answer("what is my account balance", index, verified)

check("verified user gets an answer", not r_ok.get("escalated"),
      r_ok["reply"][:60])
check("unverified user escalates", r_unver.get("escalated") is True,
      r_unver["reply"][:60])
check("unknown segment escalates", r_noseg.get("escalated") is True,
      r_noseg["reply"][:60])
check("territory msg ASKS rather than dead-ends",
      "which kind of customer" in r_noseg["reply"].lower(),
      r_noseg["reply"][:80])
check("greeting works WITHOUT a segment (the screenshot bug)",
      not r_social_noseg.get("escalated"),
      r_social_noseg["reply"][:60])
check("red line beats small talk",
      "can't look at anything on your account" in r_redline["reply"].lower()
      or "can't" in r_redline["reply"].lower(),
      r_redline["reply"][:60])

# Small talk must never be answered from documents.
check("social reply cites no sources", len(r_social_noseg.get("hits", [])) == 0)


# =====================================================================
section("6 · Offline fallback (works with no API key)")
# =====================================================================
saved = {k: os.environ.pop(k, None)
         for k in ["OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
                   "NVIDIA_API_KEY", "LLM_PROVIDER"]}
try:
    with quiet():
        off = b.answer("how do I read an energy label", index, verified)
    check("offline still answers", len(off["reply"]) > 40, off["reply"][:60])
    check("offline does NOT apologise and give up",
          "all ai providers are currently unavailable" not in off["reply"].lower(),
          off["reply"][:80])
    check("offline answer is grounded in documents", len(off.get("hits", [])) > 0)
    check("offline cites a source marker", "[1]" in off["reply"], off["reply"][:80])
finally:
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


# =====================================================================
section("7 · The calculator tool")
# =====================================================================
c = b.appliance_cost(watts=1000, hours_per_day=1, rate_per_kwh=1.0)
check("1000W for 1h = 1 kWh", abs(c["kwh_day"] - 1.0) < 0.001, str(c["kwh_day"]))
check("cost matches rate", abs(c["cost_day"] - 1.0) < 0.001, str(c["cost_day"]))
check("yearly = daily x 365", abs(c["cost_year"] - 365.0) < 0.01, str(c["cost_year"]))

cmp = b.compare_appliances(
    {"name": "Old", "watts": 350, "hours_per_day": 8, "price": 1500},
    {"name": "New", "watts": 150, "hours_per_day": 8, "price": 2600}, 1.0)
check("cheaper-to-run identified", cmp["cheaper_to_run"] == "New", str(cmp["cheaper_to_run"]))
check("payback computed", cmp["payback_years"] is not None and cmp["payback_years"] > 0,
      str(cmp["payback_years"]))

# Zero-watt appliance must not divide by zero or crash.
try:
    z = b.appliance_cost(watts=0, hours_per_day=8)
    check("zero watts handled", z["cost_year"] == 0.0, str(z["cost_year"]))
except Exception as e:
    check("zero watts handled", False, f"{type(e).__name__}: {e}")


# =====================================================================
section("8 · Web harvest safety")
# =====================================================================
check("client domain allowed", b.is_allowed_domain("https://www.lucelec.com/x"))
check("bare domain allowed", b.is_allowed_domain("https://lucelec.com/x"))
check("stranger domain refused", not b.is_allowed_domain("https://example.com/x"))
check("lookalike domain refused",
      not b.is_allowed_domain("https://lucelec.com.evil.net/x"))
check("no-scheme URL refused", not b.is_allowed_domain("www.lucelec.com/x"))

pending = b.list_pending()
check("waiting room readable", isinstance(pending, list), str(type(pending)))
check("harvested pages are pending, not live", len(pending) == 2,
      f"{[p['file'] for p in pending]}")
check("pending files carry a source URL",
      all(p["url"].startswith("http") for p in pending),
      str([p["url"] for p in pending]))

# Approval must require initials.
res = b.approve_harvest("index.md", "")
check("approval refused without initials", res.get("ok") is not True, str(res))


# =====================================================================
section("9 · Key store")
# =====================================================================
check("mask hides the middle", b.mask_key("gsk_ABCDEFGHIJKLMNOP") == "gsk_...MNOP",
      b.mask_key("gsk_ABCDEFGHIJKLMNOP"))
check("mask handles empty", b.mask_key("") == "(not set)")
check("mask hides short strings", "*" in b.mask_key("abc"))

rep = b.key_report()
check("key report lists all providers", len(rep) >= 4, str(len(rep)))
check("key report never leaks a full key",
      all(len(r["masked"]) < 20 for r in rep),
      str([r["masked"] for r in rep]))


# =====================================================================
section("10 · Eval suite")
# =====================================================================
with quiet():
    rows = b.run_eval(index, verified)
passed = sum(1 for r in rows if r["passed"])
check("eval runs", len(rows) >= 6, f"{len(rows)} cases")
check("eval includes a must-refuse case",
      any("account balance" in r["question"].lower() for r in rows))
check("eval includes small talk",
      any(r["question"].strip().lower() == "hi" for r in rows))
print(f"        (offline baseline score: {passed}/{len(rows)} — "
      f"2 fails expected without an API key)")


# =====================================================================
section("11 · Streamlit routing states")
# =====================================================================
src = open(b.__file__, encoding="utf-8").read()
check("opens on customer_view",
      "st.session_state.page_state = 'customer_view'" in src)
check("no orphaned homepage state", "'homepage'" not in src,
      "a button still routes to the deleted homepage")
check("admin login view exists", "page_state == 'admin_login'" in src)
check("sidebar has admin login button", "Admin login" in src)
check("sidebar has log out", "Log out" in src)
check("set_page_config is first st call",
      src.index("st.set_page_config") < src.index("st.cache_data"),
      "set_page_config must precede every other st.* call")


# =====================================================================
section("RESULTS")
# =====================================================================
total = len(PASSES) + len(FAILS)
print(f"\n  {len(PASSES)}/{total} checks passed\n")
if FAILS:
    print("  Failures:")
    for name, detail in FAILS:
        print(f"    · {name}  → {detail}")
    sys.exit(1)
else:
    print("  No failures.")
    sys.exit(0)
