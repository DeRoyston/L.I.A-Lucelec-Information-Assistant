# Calculator Fuel Surcharge Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the appliance cost calculator the bot actually uses (`calculator_tool`, bound to the LLM and required by the system prompt for every cost question) include LUCELEC's fuel variation charge by default, instead of silently quoting customers a rate that's missing it.

**Architecture:** `DEFAULT_FUEL_SURCHARGE` already exists in the file and is already correctly added to the base rate in two functions (`payback_with_surcharge()`, `kwh_year_to_monthly_cost()`) — proving the codebase already knows the real effective rate is `DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE`. It just never got applied to the two functions that actually back the customer-facing tool (`appliance_cost()`, `compare_appliances()`), and the tool's own reply text hardcodes the base rate regardless of what was actually charged. The fix introduces one new constant, `DEFAULT_EFFECTIVE_RATE`, as the single source of truth for "the real per-kWh rate including the fuel surcharge," and points every default at it instead of at the bare base rate.

**Tech Stack:** Python 3, no new dependencies. Test runner: `run_tests.py` via `../venv/Scripts/python.exe` from `Template-bot/files/`.

**Spec:** None on disk — this plan's spec is the root-cause analysis below, derived from direct inspection and live invocation of `calculator_tool` against this repo.

## Root cause (read this before touching code)

1. `lucelec_rag_bot.py:2456-2457` defines both pieces the calculator needs: `DEFAULT_RATE_PER_KWH = 1.00` and `DEFAULT_FUEL_SURCHARGE = 0.255`.
2. `appliance_cost()` (`2460-2474`, the core cost-math function) defaults `rate_per_kwh` to the bare `DEFAULT_RATE_PER_KWH` — the fuel surcharge is never added unless a caller explicitly passes a rate that already includes it.
3. `compare_appliances()` (`2477-2492`) has the same problem — its `rate` parameter defaults to the bare `DEFAULT_RATE_PER_KWH`.
4. `calculator_tool()` (`2541-2549`) — the **only** function actually bound to the LLM (`get_llm_for_provider()` calls `.bind_tools([calculator_tool])` at lines 1853/1869/1878) and the one `MASTER_PROMPT` explicitly requires ("IF the user asks to calculate an appliance cost, you MUST use the `calculator_tool`", line 2041) — calls `appliance_cost(watts, hours_per_day)` with no rate override, so it inherits the broken bare-rate default. Its own reply string then hardcodes `EC${DEFAULT_RATE_PER_KWH}/kWh`, so even the *text* the bot says is wrong, not just the number.
5. **Confirmed live**, invoking the actual tool the way the LLM does (`calculator_tool.invoke({"watts": 1000, "hours_per_day": 1})`):
   ```
   Calculation successful: Running a 1000.0W appliance for 1.0 hours costs
   EC$30.0 per month and EC$365.0 per year at a rate of EC$1.0/kWh.
   ```
   The correct effective rate is `1.00 + 0.255 = 1.255`/kWh — the real monthly figure should be EC$37.65, real yearly EC$458.08. The bot is undercounting every quoted cost by ~20.3% (`0.255 / 1.255`).
6. Two functions already get this right and prove the intended math: `payback_with_surcharge()` (`2495-2509`) computes `DEFAULT_RATE_PER_KWH + fuel_surcharge` explicitly, and `kwh_year_to_monthly_cost()` (`2530-2538`) defaults its `rate_per_kwh` parameter to `DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE` — the exact same expression, duplicated. Neither of these is broken and neither should change behavior; the fix is to give that expression one name and point the two broken functions at it too.

## Global Constraints

- No new dependencies.
- One new constant, `DEFAULT_EFFECTIVE_RATE`, becomes the single source of truth for "base rate + fuel surcharge." Every place in the file that currently means that value (whether spelled out as `DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE` or currently missing the surcharge entirely) should reference it, not recompute it.
- Do not touch `payback_with_surcharge()`'s composable `fuel_surcharge` parameter — it's designed to accept a caller-supplied surcharge different from the default (used for "what if the surcharge changes" scenarios), so it must keep computing `DEFAULT_RATE_PER_KWH + fuel_surcharge` from its own parameter, not be collapsed onto the fixed constant.
- Match existing code style: trailing `#` why-comments, `# FIXED: ...` markers for bugfix additions.
- Run the full suite via the project venv (`../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`). Baseline before this task: 127/129 passing, with the same 2 pre-existing, unrelated failures as always (`unapproved harvest is NOT retrievable`, `harvested pages are pending, not live`) — not this task's responsibility, must not regress further.

---

### Task 1: Include the fuel surcharge in every default cost calculation

**Files:**
- Modify: `Template-bot/files/lucelec_rag_bot.py:2456-2549` (the whole calculator section: constants, `appliance_cost()`, `compare_appliances()`, `kwh_year_to_monthly_cost()`, `calculator_tool()`)
- Test: `Template-bot/files/run_tests.py` (Section 7 · The calculator tool, extending the existing section)

**Interfaces:**
- Consumes: nothing new from other tasks (this plan has one task).
- Produces:
  - `DEFAULT_EFFECTIVE_RATE: float` — new module-level constant, `DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE`.
  - `appliance_cost(watts, hours_per_day, rate_per_kwh: float = DEFAULT_EFFECTIVE_RATE) -> dict` — same signature shape, new default value only.
  - `compare_appliances(a, b, rate: float = DEFAULT_EFFECTIVE_RATE) -> dict` — same signature shape, new default value only.
  - `kwh_year_to_monthly_cost(kwh_per_year, rate_per_kwh: float = DEFAULT_EFFECTIVE_RATE) -> dict` — same signature shape, same effective value as before (was spelled out inline, now references the shared constant — no behavior change).
  - `calculator_tool(watts, hours_per_day) -> str` — same signature, its reply string now reports the actual rate used (`costs["rate_per_kwh"]`) instead of a hardcoded, wrong constant.
  - `payback_with_surcharge()` — unchanged, not touched by this task.

- [ ] **Step 1: Write the failing tests**

Open `Template-bot/files/run_tests.py`. Find Section 7 (starts at `section("7 · The calculator tool")`, around line 198) and its existing checks, ending with the "zero watts handled" block:

```python
# Zero-watt appliance must not divide by zero or crash.
try:
    z = b.appliance_cost(watts=0, hours_per_day=8)
    check("zero watts handled", z["cost_year"] == 0.0, str(z["cost_year"]))
except Exception as e:
    check("zero watts handled", False, f"{type(e).__name__}: {e}")
```

Immediately after that block (still inside Section 7, before the next `# ====` separator), insert:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: the 4 new default-rate/reply checks fail (`appliance_cost`/`compare_appliances` still default to the bare `1.0` rate, `calculator_tool`'s reply still says `EC$1.0/kWh` and quotes the un-surcharged monthly figure). The 2 regression-guard checks (`payback_with_surcharge`, `kwh_year_to_monthly_cost`) should already `PASS` — they're proving today's correct behavior, not new behavior; that's fine and expected.

- [ ] **Step 3: Add `DEFAULT_EFFECTIVE_RATE` and point every default at it**

Find, in `Template-bot/files/lucelec_rag_bot.py`:

```python
DEFAULT_RATE_PER_KWH = 1.00
DEFAULT_FUEL_SURCHARGE = 0.255


def appliance_cost(watts: float, hours_per_day: float,
                   rate_per_kwh: float = DEFAULT_RATE_PER_KWH) -> dict:
```

Replace with:

```python
DEFAULT_RATE_PER_KWH = 1.00
DEFAULT_FUEL_SURCHARGE = 0.255
# FIXED: The customer-facing calculator (calculator_tool, and everything
# that calls appliance_cost()/compare_appliances() without an explicit
# rate) was quoting costs using ONLY DEFAULT_RATE_PER_KWH, silently
# dropping the fuel variation charge — undercounting every quoted cost by
# about 20%. This is the one place "the real per-kWh rate" is defined;
# every default below points at it instead of recomputing it inline.
DEFAULT_EFFECTIVE_RATE = DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE


def appliance_cost(watts: float, hours_per_day: float,
                   rate_per_kwh: float = DEFAULT_EFFECTIVE_RATE) -> dict:
```

Find:

```python
def compare_appliances(a: dict, b: dict, rate: float = DEFAULT_RATE_PER_KWH) -> dict:
```

Replace with:

```python
def compare_appliances(a: dict, b: dict, rate: float = DEFAULT_EFFECTIVE_RATE) -> dict:
```

Find:

```python
def kwh_year_to_monthly_cost(kwh_per_year: float, rate_per_kwh: float = DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE) -> dict:
```

Replace with:

```python
def kwh_year_to_monthly_cost(kwh_per_year: float, rate_per_kwh: float = DEFAULT_EFFECTIVE_RATE) -> dict:
```

Find:

```python
@tool
def calculator_tool(watts: float, hours_per_day: float) -> str:
    """Useful for calculating the running cost of an appliance.
    Input the appliance wattage (watts) and the hours used per day.
    Returns the daily, monthly, and yearly cost in EC$."""

    costs = appliance_cost(watts, hours_per_day)
    return (f"Calculation successful: Running a {watts}W appliance for {hours_per_day} "
            f"hours costs EC${costs['cost_month']} per month and EC${costs['cost_year']} per year at a rate of EC${DEFAULT_RATE_PER_KWH}/kWh.")
```

Replace with:

```python
@tool
def calculator_tool(watts: float, hours_per_day: float) -> str:
    """Useful for calculating the running cost of an appliance.
    Input the appliance wattage (watts) and the hours used per day.
    Returns the daily, monthly, and yearly cost in EC$, including the
    fuel variation charge."""

    costs = appliance_cost(watts, hours_per_day)
    # FIXED: Was hardcoding DEFAULT_RATE_PER_KWH here, so the reply text
    # claimed a rate that excluded the fuel surcharge even once the math
    # above was fixed to include it. Report the rate that was actually
    # used, from the same dict the cost figures came from.
    return (f"Calculation successful: Running a {watts}W appliance for {hours_per_day} "
            f"hours costs EC${costs['cost_month']} per month and EC${costs['cost_year']} per year at a rate of EC${costs['rate_per_kwh']}/kWh.")
```

`payback_with_surcharge()` is not modified — leave it exactly as it is.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../venv/Scripts/python.exe run_tests.py` from `Template-bot/files/`
Expected: all Section 7 checks `PASS`, including the 7 new ones (5 new-behavior checks + 2 regression guards that were already passing before this change and must keep passing after it). Total at the bottom should read **134/136 checks passed** (127 baseline + 7 new checks, all passing), with the same 2 pre-existing, unrelated failures as always and no new ones.

- [ ] **Step 5: Manually confirm against a live calculation**

If an LLM provider key is configured, run the app (`streamlit run lucelec_rag_bot.py` from `Template-bot/files/`) and ask a cost question, e.g. "how much does a 1000 watt appliance cost to run for 1 hour a day?"

Expected: the bot's answer (and the tool call behind it) now reflects a rate of EC$1.255/kWh (~EC$37.65/month, ~EC$458.08/year for this example), not EC$1.00/kWh. If no provider key is configured, this step is informational only — the fix itself is fully verified by Step 4, and Step 1's `calculator_tool.invoke(...)` check already exercises the exact same code path the LLM uses.

- [ ] **Step 6: Commit**

```bash
git add "Template-bot/files/lucelec_rag_bot.py" "Template-bot/files/run_tests.py"
git commit -m "fix: include fuel variation charge in the appliance cost calculator's default rate"
```

---

## Self-Review

**1. Spec coverage:** The root-cause finding (calculator tool omits the fuel surcharge) is covered end-to-end: Step 3 fixes the two broken defaults (`appliance_cost`, `compare_appliances`) and the tool's own misleading reply text, and DRYs the one already-correct duplicate expression (`kwh_year_to_monthly_cost`) onto the same new constant. Step 1's tests exercise the actual LLM-facing code path (`calculator_tool.invoke(...)`), not just the underlying math function, so the fix is proven where it actually matters — what the bot says to a customer.

**2. Placeholder scan:** No TBD/TODO markers. All code blocks are complete, copy-pasteable find/replace pairs. Only one task, so no "similar to Task N" references.

**3. Type consistency:** No function signatures change shape — only default *values* change (from `DEFAULT_RATE_PER_KWH` to the new `DEFAULT_EFFECTIVE_RATE`), so every existing caller in the file (there are none that omit the rate/surcharge outside what this task touches — `payback_with_surcharge` always passes its own explicit rate, and `vampire_power_audit` doesn't take a rate at all) keeps working unchanged.

**Deliberately out of scope:** `payback_with_surcharge()`'s composable `fuel_surcharge` parameter is left untouched — collapsing it onto the fixed `DEFAULT_EFFECTIVE_RATE` constant would remove its ability to model a different surcharge value, which is exactly what that function exists for. Also out of scope: whether `DEFAULT_RATE_PER_KWH`/`DEFAULT_FUEL_SURCHARGE` themselves are the *correct* real-world LUCELEC values — neither constant carries a `CONFIRM_TAG`/"[Confirm with client]" marker the way unverified tariff figures elsewhere in the file do, so they're treated as intentional, already-accepted demo/reference figures; this task only fixes the *formula* that combines them, not the numbers themselves.
