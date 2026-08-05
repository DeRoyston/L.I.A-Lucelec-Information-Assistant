# LUCELEC RAG Chatbot — Student Template

A working retrieval-augmented chatbot for LUCELEC that you extend. Bring an
OpenAI, Gemini, Groq, NVIDIA or Ollama key and it's a real AI chatbot. Bring none and
it still retrieves and cites, so nothing blocks you on day one.

The client's ask, in one line: help a customer work out what an appliance will
cost to run before they buy it — and never make up a tariff.

---

## Run it in Deepnote

1. Upload `lucelec_rag_bot.py`, `requirements.txt` and the `source_documents/`
   folder into the Deepnote file tree.
2. Deepnote installs `requirements.txt` on machine start. If it doesn't, run
   `!pip install -r requirements.txt` in a code block.
3. Add your API key — Deepnote → **Environment** → Environment variables (see
   the table below). Restart the machine so the variable loads.
4. In a **Terminal**, run:

   ```
   streamlit run lucelec_rag_bot.py --server.port 8501 --server.address 0.0.0.0
   ```

5. Open the URL Deepnote prints. Keep the terminal running.

Check your key worked before you demo anything:

```
python3 lucelec_rag_bot.py --providers     # shows READY / not configured, then pings each one
python3 lucelec_rag_bot.py --ask "what uses the most electricity"
```

---

## Plugging in an AI model

Set **one** environment variable and the bot becomes a real AI RAG chatbot. Set
several and it falls down the chain when one fails mid-demo.

| Provider | Variable | Where to get a key | Free? |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | platform.openai.com/api-keys | Paid |
| Google Gemini | `GEMINI_API_KEY` | aistudio.google.com/apikey | Free tier |
| Groq | `GROQ_API_KEY` | console.groq.com/keys (key starts `gsk_`) | Free tier, very fast |
| NVIDIA NIM | `NVIDIA_API_KEY` | build.nvidia.com (key starts `nvapi-`) | Free credits |
| Ollama | none needed | ollama.com/download, then `ollama pull llama3.2` | Free, runs locally |

Other variables you can set:

- `LLM_PROVIDER` — pin one: `openai`, `gemini`, `groq`, `nvidia` or `ollama`.
- `OPENAI_MODEL`, `GEMINI_MODEL`, `GROQ_MODEL`, `NVIDIA_MODEL`, `OLLAMA_MODEL` — override the
  model name without touching the code. Model IDs change every few months; if
  you get a 404, this is the fix.
- `OLLAMA_BASE_URL` — default `http://localhost:11434/v1`.

### Where the key actually lives

The bot never holds a key in the code. At startup it looks in three places,
in this order, and the first one that has a key wins:

1. **Environment variables** — Deepnote → Environment → Environment variables.
   Best option. The key never touches the file system of your project.
2. **`.streamlit/secrets.toml`** — written by the **Save to server** button in
   the sidebar. Created with permission `600` (owner-only) and with a
   `.gitignore` beside it, so it cannot be committed by accident.
3. **`.env`** — copy `.env.example` to `.env` and fill it in. Also gitignored.

That ordering matters. A real environment variable always beats a stale file
someone forgot about, which is usually the answer to "why is it still using the
old key".

Useful commands:

```
python3 lucelec_rag_bot.py --doctor      # where the bot is looking, and what it finds there
python3 lucelec_rag_bot.py --keys        # which keys are set, and which file they came from
python3 lucelec_rag_bot.py --providers   # ping each configured provider to prove it works
```

Run `--doctor` first whenever anything is "not found". Every folder the bot uses
is anchored to the folder `lucelec_rag_bot.py` lives in, **not** to wherever you
started Python — in Deepnote a notebook usually runs from `~/work` while the
file sits in `~/work/files`, and relative paths quietly point at the wrong
place. `--doctor` prints both folders so you can see the difference, then opens
every document individually, because a folder listing can show a file that
cannot actually be read. Broken shortcuts are reported and repaired on the next
run.

`--keys` never prints a whole key. It shows `gsk_...9xyz` — first four
characters and last four. Enough to tell two keys apart, useless to a thief.

**The warning that matters.** Anyone who can open your Deepnote project can
read `.streamlit/secrets.toml`. Use the camp-managed key, never a personal one,
and never duplicate or share a project that still has a key saved in it. If a
key does leak, revoke it in the provider's console — do not just delete the
file, because the key still works until you revoke it.

Never put a key in the code. Never commit a key. Never paste one into a
screenshot, a slide, or a chat.

**Why one function handles all five providers:** they all accept the same
OpenAI-style `POST /chat/completions` request. Only three things change —
`base_url`, the key, and the model name. That's the whole `PROVIDERS` dict in
section 4. Adding a sixth provider is one more row.

Groq is the easiest start for a classroom: free tier, no card, and it answers
fast enough that a room of twenty students isn't sitting there watching a
spinner. Ollama is the one to reach for when the wifi is bad or the camp key
hits its cap — it runs on the machine in front of you and costs nothing.

Groq retired the Llama chat models, so the default here is
`openai/gpt-oss-20b`. Switch to `openai/gpt-oss-120b` if answers come back thin.

**No provider configured?** The bot still retrieves and cites, using an
extractive fallback that stitches together the matching sentences. It reads
badly on purpose. That is the baseline a real model has to beat, and it means
your demo survives a dead key.

---

## What's in the file

Every line in `lucelec_rag_bot.py` carries a comment explaining what it does.
Read it top to bottom once without changing anything, then come back and change
one thing.

| Section | What it does |
|---|---|
| 0 · POD CONFIG | The handful of settings every Pod edits first. |
| 1 · THE KEY STORE | Where API keys are loaded from and saved to. Never in the code. |
| 2 · THE WEEK 1 BLUEPRINT | Persona, Empathy Map, Wardrobe, jargon, rulebook, A.R.T., memory policy. |
| 3 · GUARDRAILS | PII redaction and the Red Line refusals. Runs before anything else. |
| 4 · LOADING AND CHUNKING | Reads `source_documents/`, chunks it, and harvests pages into `pending_review/`. |
| 5 · RETRIEVAL | Keyword scoring with IDF. Returns the top 3 chunks only. |
| 6 · THE AI MODEL | Provider table for all five, one call function, fallback chain. |
| 7 · THE MASTER PROMPT (TCRDEI) | The TCRDEI Master Prompt, plus the social lane for small talk. |
| 8 · THE TOOL | Appliance cost calculator and comparison. |
| 9 · THE PIPELINE | `classify_and_route()` — Red Line, then lane, then A.R.T., then the AI. |
| 10 · THE EVAL SET | A test set. Run it after every change. |
| 11 · THE WEB APP | Chat, Calculator, Blueprint, Web harvest, Sources, Eval. |
| 12 · COMMAND LINE | `--demo`, `--keys`, `--providers`, `--ask`, `--harvest`, `--pending`, `--approve`. |

The flow, every single turn:

```
question → red line check → redact PII → retrieve top 3 → ground the prompt → answer with [1] citations
```

---

## The one rule

Every number the bot says out loud has to come from a document in
`source_documents/`. The sample documents shipped here are **placeholders** with
`TODO_` markers where the real figures go. Confirm each one with the client,
then log it in your Confirmation Register with their initials and the date.

A bot that invents a tariff is worse than no bot.

---

## Harvesting from the client's website

The bot can pull pages from `lucelec.com` — but downloading a page is not the
same as confirming a fact. A rate on a web page might be out of date, might be
for a different customer class, might be a draft nobody took down. If the bot
quotes it and it is wrong, the client carries the blame.

So harvested pages **do not go into `source_documents/`**. They go into
`pending_review/`, which retrieval never reads. A human has to read the text and
approve it with their initials before the bot can say any of it out loud.

**Scraping fills a waiting room, not the knowledge base.**

```
python3 lucelec_rag_bot.py --harvest "https://www.lucelec.com/content/customer-service"
python3 lucelec_rag_bot.py --pending
python3 lucelec_rag_bot.py --approve content-customer-service.md --by KJ
python3 lucelec_rag_bot.py --reject  content-customer-service.md
python3 lucelec_rag_bot.py --robots  "https://www.lucelec.com/content/services"
```

Run `--robots` whenever a fetch is refused. It tells you which of three things
happened: the site's rules say no, there is no robots.txt at all (which means
yes), or the server refused to show it (which means we refuse too).

Or use the **Web harvest** tab, which shows the waiting room with a preview and
Approve / Reject buttons. Approving without initials is refused — someone has to
own it. Approved files arrive as `web-*.md` so the origin is obvious in every
citation, and the file keeps a header saying where it came from, when, and who
signed it off.

Three limits are built in and you should not remove them:

- **Allowlist.** `ALLOWED_DOMAINS` holds **hostnames**, not page addresses.
  `lucelec.com` is right. A full URL gets tidied up for you, but putting a path
  in that list does nothing — the allowlist controls which *site* may be
  fetched, and every page on it is then allowed. Allowing `lucelec.com` also
  allows `www.lucelec.com`. Every other address is refused before a single byte
  is fetched. Add a host only if the client tells you to in writing.
- **robots.txt.** Checked on every fetch, and fetched **using our own
  User-Agent**. That detail matters more than it sounds: Python's built-in
  `RobotFileParser.read()` downloads robots.txt as `Python-urllib/3.x`, which
  plenty of firewalls block with a 403 — and the parser then silently decides
  every page is forbidden. You get a bot that refuses a site which actually
  allows it, for a reason that never appears in the rules. We download the file
  ourselves and hand the text to the parser, so this cannot happen.

  Two further caveats. Python's reader returns the *first* matching rule rather
  than the most specific one, so it is a floor, not a ceiling. And if robots.txt
  cannot be read at all, the answer is no.
- **Politeness.** We wait however long the site asks for. LUCELEC's robots.txt
  states `Crawl-delay: 10`, so a fetch takes at least ten seconds and the app
  will sit on a spinner for that long — that is the code obeying the client,
  not a bug. Our own two-second minimum applies only when a site states nothing.
  Also: a 2MB cap, and a `User-Agent` that says who you are. Put a real contact
  address in it before you run this.

PDFs work if you `pip install pypdf`; otherwise the fetch tells you so.

**Ask the client before you point this at their site.** They may have a
staging server, a rate-limited host, or a page they would rather you didn't use.
A one-line email on Day 3 avoids an awkward conversation on Demo Day.

---

## Two lanes: small talk and real questions

A person who types "hi" has not asked a question about electricity. Answering
"That isn't in my LUCELEC documents" is technically correct and completely
useless — and it teaches them the bot is a search box, so they stop talking to
it like a person.

So every message goes down one of two lanes:

**Social lane** — greetings, thank yous, goodbyes, "who are you", "what can you
do". The AI writes the reply freely so it sounds like a person. But it is given
no documents and is explicitly forbidden to state any rate, price, policy or
fact. It can be friendly. It cannot be a source.

**Domain lane** — anything about bills, appliances, tariffs or electricity.
Full A.R.T., full retrieval, citations, the lot. Unchanged.

The rule that keeps this honest: **warmth is free, facts are not.**

Two consequences worth understanding:

- **A greeting no longer needs a customer category.** `classify_intent()` runs
  before the Territory check, because you don't need to know somebody's customer
  segment to say hello back. A.R.T. guards *answers about the client's
  business*, not basic manners.
- **The Red Line still runs first.** "Hi, what's my account balance?" is still
  refused. Small talk cannot be used as a way in.

Unknown Territory now asks instead of dead-ending: *"Before I answer that, which
kind of customer are you — Domestic, Commercial or Industrial?"* That matches
the Week 2 rule that cross-territory queries must ask for clarification rather
than guess.

With no API key the social lane still works, using fixed replies per intent. It
sounds like a leaflet rather than a person — which is exactly the argument for
plugging a key in.

The chat caption shows which lane each reply came from, so students can watch
the routing decision happen.

---

## Your assignments

**Build 1 — Fill the knowledge base.** Replace the three sample files in
`source_documents/` with real LUCELEC material. Add PDF support with `pypdf` so
the client can drop their own documents in without you converting anything.

**Build 2 — Wire the tool to the bot.** Right now `decide_action()` exists but
nothing calls it. Make the pipeline route cost questions to
`appliance_cost()` and explanation questions to retrieval, then say in the reply
which path it took.

**Build 3 — Grow the eval set.** Ten questions minimum, including two the
documents genuinely cannot answer. The bot must say "That isn't in my LUCELEC
documents" for those. Record your pass rate before and after every change.

**Build 4 — Better retrieval (stretch).** Swap the keyword scorer for
`sentence-transformers` embeddings. Keep the old one. Report both numbers on the
same eval set — that comparison is the point, not the upgrade.

**Build 5 — Compare the providers.** Run the same eval set through Gemini, Groq
and Ollama. Same documents, same questions, three different models.
Which one refuses correctly? Which one invents a tariff? Bring that table to the
client — it's the most useful slide you will make all camp.

**Build 6 — Harvest and verify.** Pull three pages from the client's website
into the waiting room. Read each one properly. Approve the ones that are current
and reject the ones that are not — then explain to the client, in the Demo Day
Q&A, why you rejected what you rejected. That judgement is the job.

**Build 7 — Make the small talk yours.** The social replies are deliberately
plain. Rewrite `SOCIAL_PROMPT` and the fixed fallbacks in your client's actual
voice, in Saint Lucian English, and test that the bot still refuses to state a
single number in that lane. Warmth is free; facts are not.

**Build 8 — Your own feature.** Standby-power calculator. Bill estimator from a
whole house of appliances. Kwéyòl replies. Whatsapp-length answers. A retailer
mode that compares three models at once. Pick one and own it.

---

## Where students usually break it

- Editing a document and not clicking **Reload documents** in the sidebar. The
  index is cached.
- **`FileNotFoundError` on a file that is clearly there.** Usually a broken
  shortcut, or a stale listing after a sync. The bot now skips unreadable files
  with a warning instead of crashing, and rewrites missing sample documents.
  Run `--doctor` to see which file is at fault.
- Chunks too big. If `TOP_K = 3` chunks blow past the context window, drop
  `CHUNK_WORDS` before you drop `TOP_K`.
- Retrieval returning nothing because the question uses words that appear in no
  document. That's a knowledge-base gap, not a bug — write the missing document.
- Putting the API key in the code. Use the key store — section 1, or the
  sidebar's Save to server button, or Deepnote's Environment tab.
- Saving a key, then wondering why the old one is still being used. An
  environment variable beats the file. Run `--keys` to see which one won.
- A 404 or "model not found" from the provider. The model ID moved. Override it
  with `OPENAI_MODEL` / `GEMINI_MODEL` / `GROQ_MODEL` / `NVIDIA_MODEL` — don't
  edit the file.
- A 401. The key is wrong, or it belongs to a different provider than the one
  selected. Run `--providers` to see which key the bot actually picked up.
- **`403 ... error code: 1010`.** Cloudflare refused the request because it did
  not come from a client it recognises. This only happens on the built-in
  fallback route. Fix: `pip install openai`. The bot then uses that library
  automatically and the problem goes away. The sidebar warns you when the
  package is missing.
- **`no usable text (finish_reason=length)`.** A reasoning model — Gemini 3.x
  does this — spent its whole token budget thinking and wrote nothing. The bot
  now retries once with three times the room. If it still fails, either raise
  `max_tokens` in `chat_completion()` or pick a non-reasoning model.
- **An answer arrives but it is blank.** Some providers return the words in
  `reasoning_content` rather than `content`, or as a list of parts. The
  extractor handles all three; if you see a blank reply, the error text will
  now say which shape came back rather than crashing.
- Ollama showing "not configured". The server isn't running. `ollama serve`.
