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
import inspect
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

# The fuel variation charge must be included by default — this is the
# actual bug: the calculator was quoting customers a rate ~20% too low
# by silently omitting DEFAULT_FUEL_SURCHARGE.
effective = b.DEFAULT_RATE_PER_KWH + b.DEFAULT_FUEL_SURCHARGE
c_default = b.appliance_cost(watts=1000, hours_per_day=1)
check("appliance_cost default rate includes the fuel surcharge",
      abs(c_default["rate_per_kwh"] - effective) < 0.001,
      f"used rate {c_default['rate_per_kwh']}, expected {effective}")
check("appliance_cost cost_day reflects the surcharge, not the bare base rate",
      abs(c_default["cost_day"] - effective) < 0.01,
      str(c_default["cost_day"]))

cmp_default = b.compare_appliances(
    {"name": "Old", "watts": 350, "hours_per_day": 8, "price": 1500},
    {"name": "New", "watts": 150, "hours_per_day": 8, "price": 2600})
check("compare_appliances default rate includes the fuel surcharge",
      abs(cmp_default["Old"]["rate_per_kwh"] - effective) < 0.001,
      f"used rate {cmp_default['Old']['rate_per_kwh']}, expected {effective}")

# calculator_tool is the ONLY function actually bound to the LLM — this is
# the transcript-level check that the fix reaches what the bot really says.
tool_reply = b.calculator_tool.invoke({"watts": 1000, "hours_per_day": 1})
check("calculator_tool reply does not quote the bare base rate as the charged rate",
      f"EC${b.DEFAULT_RATE_PER_KWH}/kWh" not in tool_reply,
      tool_reply)
expected_month = round((1000 / 1000.0) * 1 * 30 * effective, 2)
check("calculator_tool reply's monthly figure includes the fuel surcharge",
      f"EC${expected_month}" in tool_reply,
      tool_reply)

# Regression guard: the two functions that already handled the surcharge
# correctly must still produce the same numbers as before this change.
payback = b.payback_with_surcharge(old_watts=1500, new_watts=900, hours_per_day=8, purchase_price=1500)
check("payback_with_surcharge still uses base rate + its own fuel_surcharge param",
      payback["monthly_saving"] > 0, str(payback))
kwh_convert = b.kwh_year_to_monthly_cost(360)
check("kwh_year_to_monthly_cost default rate unchanged (still base + surcharge)",
      abs(kwh_convert["rate_per_kwh"] - effective) < 0.001,
      str(kwh_convert["rate_per_kwh"]))


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
# FIXED (2026-08-18): a fresh session now opens on the customer gate, not
# straight into the chat — see Section 16 for the gate's own coverage.
check("opens on customer_gate",
      "st.session_state.page_state = 'customer_gate'" in src)
check("no orphaned homepage state", "'homepage'" not in src,
      "a button still routes to the deleted homepage")
check("admin login view exists", "page_state == 'admin_login'" in src)
check("customer gate view exists", "page_state == 'customer_gate'" in src)
check("sidebar has admin login button", "Admin login" in src)
check("sidebar has log out", "Log out" in src)
check("set_page_config is first st call",
      src.index("st.set_page_config") < src.index("st.cache_data"),
      "set_page_config must precede every other st.* call")


# =====================================================================
section("16 · Customer gate screen")
# =====================================================================
# Behavioral coverage for the gate's actual logic (as opposed to Section
# 11's static "does this route exist" source greps) would need Streamlit's
# AppTest harness, which nothing else in this suite uses — every other
# page_state/sidebar/CSS feature in this project has been verified live
# via the `browse` skill instead (see work notes). These are source-level
# structural checks: the right pieces exist and are wired to each other,
# not a substitute for the live walkthrough already done for this feature.
check("customer_gate is a recognized page_state",
      "'customer_view', 'admin_view', 'admin_login', 'customer_gate'" in src)
check("gate blocks Continue without a real Territory pick",
      "gate_territory_required_warning" in src and
      'if not segment or segment.startswith("(")' in src)
check("gate has a staff bypass that routes to admin_login, not admin_view directly",
      'set_state(\'admin_login\')' in src)
check("admin_login's Back returns to the gate, not straight past it",
      src.count("args=('customer_gate',)") >= 2,
      "expected 2 Back buttons (locked-out + normal) routed to customer_gate")
check("staff logout returns to the gate",
      "staff_account = None" in src and "set_state('customer_gate')" in src)
check("gate and Settings share ONE identity-fields definition, not two copies",
      src.count("def render_identity_fields") == 1 and
      src.count('t("territory_label")') == 1,
      "the widgets should be defined once in render_identity_fields() and called from both sites")
check("render_identity_fields is actually called from both the gate and Settings",
      "render_identity_fields(t, show_authority=False)" in src and
      "render_identity_fields(t)" in src,
      "expected 2 call sites: the customer gate (show_authority=False) and Settings (default)")
check("real customer identity no longer silently defaults to Domestic/verified",
      src.count("current_user_from_identity()") >= 2 and
      "sim_verified = st.checkbox" not in src,
      "the old inline sim_verified/sim_mood/sim_segment dict-building in Settings should be gone")

# FIXED (2026-08-18): a key-bound Streamlit widget's session_state entry
# is deleted at the end of any run that doesn't render that widget — the
# gate and Settings are mutually exclusive render sites, so every shared
# identity_*/ui_language field was silently resetting to its default the
# first time either site went a run without rendering it. Caught live
# (Territory reset to "(unknown)" after completing the gate with
# "Domestic" selected), fixed by shadowing each widget's value into a
# separate, plain (non-widget) session_state key every render.
check("sticky_* helpers exist to survive the widget-key GC gap",
      "def sticky_text_input" in src and "def sticky_checkbox" in src and
      "def sticky_selectbox" in src,
      "identity_*/ui_language fields must not rely on a bare widget key surviving across the gate<->Settings gap")
check("every sticky widget uses a disposable __widget key, not the plain shadow key, for its own Streamlit key=",
      src.count('key=f"{session_key}__widget"') == 3,
      "sticky_text_input/checkbox/selectbox should each pass key=f\"{session_key}__widget\"")
check("the language picker also goes through the sticky pattern (same bug, pre-existing, Settings-only)",
      "def render_language_picker" in src and
      "sticky_selectbox(t(\"language_label\")" in src and
      'key="ui_language"' not in src,
      "no remaining bare key=\"ui_language\" widget binding — must go through sticky_selectbox now")
check("gate and Settings language pickers are the same call, not two copies",
      src.count("def render_language_picker") == 1 and
      src.count("render_language_picker(t)") == 3,  # 1 def line + 2 real calls
      "expected exactly 1 definition and 2 call sites: the customer gate and Settings")


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
check(
    "footer bar is rendered",
    "lucelec-footer" in src_text,
    "no .lucelec-footer markup found in streamlit_app()"
)

# Final-review finding 2: POLISH_CSS and DARK_MODE_CSS both set
# .lucelec-footer-text color (and the footer icon fill) with !important at
# equal specificity, so the <style> tag injected LATER wins. POLISH_CSS used
# to inject down at the footer markup, i.e. after DARK_MODE_CSS, which let
# its light-mode navy beat the dark-mode override (~1.4:1 contrast).
# DARK_MODE_CSS must stay the last-injected style block in the file.
check(
    "POLISH_CSS injects before DARK_MODE_CSS",
    src_text.index("<style>{POLISH_CSS}</style>")
        < src_text.index("<style>{DARK_MODE_CSS}</style>"),
    "POLISH_CSS injects after DARK_MODE_CSS — its light-mode footer color will win the !important tie in dark mode"
)
check(
    "footer building icons take their fill from CSS, not an inline attribute",
    ".lucelec-footer-icon-building" in dark_css_block
        and 'class="lucelec-footer-icon-building"' in src_text,
    "footer silhouettes still hardcode fill=\"#2C3E50\" inline, so dark mode can't lighten them"
)

# Bug 4: build_accessibility_css() used a universal `!important` selector
# that clobbered the banner's .lucelec-title/.lucelec-subtitle font-size
# (and the footer text), and its injection only ran while the Settings
# expander was open so the chosen font size stopped applying the instant
# Settings was collapsed.
# Assert against the CSS the function actually emits, not its source text —
# the docstring discusses the broken :not() approach by name, so a source
# scan would match the prose instead of the rules.
a11y_css = b.build_accessibility_css(16)
check(
    "accessibility CSS re-asserts branded title/subtitle/footer sizes",
    all(f"{sel}, {sel} *" in a11y_css for sel in
        (".lucelec-title", ".lucelec-subtitle", ".lucelec-footer-text")),
    "build_accessibility_css() can still clobber branded text font-size — Streamlit's inner <span> needs the sizes re-asserted on descendants too"
)
# The `*:not(.lucelec-title):not(...)` exclusion approach is known-broken and
# must not come back: (a) it can't reach the inner <span> Streamlit wraps
# heading text in, and (b) `:not()` inherits its argument's specificity, so
# three chained :not() calls push the scaling rule to (0,4,0) and silently
# out-specify the (0,1,0) re-assertion above no matter what order they're in.
check(
    "accessibility CSS doesn't rely on :not() exclusions",
    ":not(.lucelec-" not in a11y_css,
    "build_accessibility_css() uses :not() exclusions again — they out-specify the branded-size re-assertion and silently shrink the banner"
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

# Task 7: LLM-generated chat titles
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

check(
    "process_chat_message titles the chat exactly once, using the titled flag",
    'chat.get("titled"' in app_source and "summarize_chat_title(" in app_source,
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

# Regression guard: the dark mode toggle must NOT bind directly to
# session_state["dark_mode"] via its own key — Streamlit clears a widget's
# session_state entry on any rerun where that widget isn't drawn, and the
# admin_login page (early return, no sidebar) skips drawing it entirely.
check("dark mode toggle does not bind directly to the persisted key",
      'st.toggle("🌙 Dark mode", key="dark_mode")' not in app_source,
      "the toggle is bound directly to session_state[\"dark_mode\"] again — "
      "this value gets wiped the moment the widget isn't drawn on a rerun, "
      "e.g. logging in via the admin_login page's early return")
check("dark mode toggle uses a separate widget key, written back explicitly",
      'key="dark_mode_toggle"' in app_source
      and "st.session_state.dark_mode = dark_mode_now" in app_source)

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


# =====================================================================
section("15 · Expanded personas, empathy maps, and wardrobe registers")
# =====================================================================

# PERSONA stays the primary teaching example (Blueprint tab, docs) — this
# fix only adds alongside it, never replaces its required fields.
check("PERSONA keeps its original required fields",
      {"name", "who", "goal", "need", "challenge", "quote"} <= set(b.PERSONA.keys()),
      list(b.PERSONA.keys()))

# PERSONAS is the secondary-archetype list; each entry must be shaped like
# PERSONA (same required fields) plus a "register" naming a real TONES key,
# so the Blueprint tab can render every archetype without a KeyError.
check("PERSONAS is a non-empty list", len(b.PERSONAS) > 0, len(b.PERSONAS))
for i, p in enumerate(b.PERSONAS):
    check(f"PERSONAS[{i}] has the required persona fields",
          {"name", "who", "goal", "need", "challenge", "quote", "register"} <= set(p.keys()),
          list(p.keys()))
    check(f"PERSONAS[{i}]['register'] names a real TONES voice",
          p["register"] in b.TONES, p["register"])

# EMPATHY_MAPS pairs one-to-one (by index) with PERSONAS.
check("EMPATHY_MAPS has one entry per PERSONAS entry",
      len(b.EMPATHY_MAPS) == len(b.PERSONAS),
      (len(b.EMPATHY_MAPS), len(b.PERSONAS)))
for i, e in enumerate(b.EMPATHY_MAPS):
    check(f"EMPATHY_MAPS[{i}] has the four empathy-map fields",
          set(e.keys()) == {"says", "thinks", "does", "feels"}, list(e.keys()))

# The wardrobe grew three new registers; dress() must still route every
# TONES key through its own voice, including the new ones, and unknown
# registers must still fall back to DEFAULT_REGISTER rather than raising.
for new_register in ("frustrated", "confused", "rushed"):
    check(f"TONES gained a '{new_register}' voice",
          new_register in b.TONES, list(b.TONES.keys()))
    check(f"dress('{new_register}', ...) wraps the text, doesn't just echo it",
          b.dress(new_register, "test") != "test", b.dress(new_register, "test"))
check("dress() still falls back to DEFAULT_REGISTER for an unknown mood",
      b.dress("not-a-real-register", "test") == b.dress(b.DEFAULT_REGISTER, "test"),
      b.dress("not-a-real-register", "test"))


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
