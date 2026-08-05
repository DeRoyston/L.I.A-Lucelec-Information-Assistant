# Fix run_tests.py Windows console crash

## Problem

`Template-bot/files/run_tests.py` crashes partway through (section 4 of 4,
"Intent routing") on Windows when the terminal's active codepage doesn't
support the Unicode characters the script prints (`→` U+2192, `·` U+00B7).
`·` happens to render (garbled) in some codepages; `→` raises
`UnicodeEncodeError` and kills the run, so sections 4+ never execute and
their real pass/fail results are unknown.

## Approach

Reconfigure `sys.stdout` and `sys.stderr` to UTF-8 with `errors="replace"`
at the top of `run_tests.py`, right after the `import sys`. This is a
2-line change, keeps the existing arrow/dot characters in the output
(no wording changes elsewhere in the file), and is the standard fix for
this class of Windows-console encoding crash on Python 3.7+
(`sys.stdout.reconfigure(...)`).

Rejected alternatives:
- Strip all Unicode chars from the file (`→` → `->`, `·` → `.`): more
  invasive, touches every print/f-string in the file for no benefit over
  the reconfigure fix.
- Wrap each `print()` call in error handling: same effect as the
  reconfigure fix but repeated at every call site instead of once.

## Scope

In scope:
1. Fix the encoding crash in `run_tests.py`.
2. Re-run the suite to completion.
3. Fix any genuine (non-encoding) test failures the completed run reveals.

Out of scope: a full manual code audit of `lucelec_rag_bot.py` beyond what
the test suite exercises (explicitly declined in favor of the narrower fix).

## Testing

`python run_tests.py` from `Template-bot/files/` must run to completion
(all 4 sections print) with no `UnicodeEncodeError`. Any FAIL lines in the
completed output get triaged and fixed as follow-up within this same task.
