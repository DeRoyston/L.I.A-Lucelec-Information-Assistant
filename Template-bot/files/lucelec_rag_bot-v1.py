# =====================================================================
#   LUCELEC RAG CHATBOT — STUDENT TEMPLATE
#   Client: Saint Lucia Electricity Services Limited (LUCELEC)
#
#   WHAT THIS FILE IS
#   A chatbot that answers questions using YOUR documents instead of
#   whatever the AI model happens to remember. That is what "RAG" means:
#     R = Retrieval  (find the right paragraphs in your documents)
#     A = Augmented  (paste those paragraphs into the question)
#     G = Generation (let the AI write the answer from ONLY those paragraphs)
#
#   HOW TO READ THIS FILE
#   Every line has a comment explaining what it does. Read top to bottom
#   once without changing anything. Then come back and change one thing.
#   A "#" means everything after it is a note for humans, not code.
#
#   RUNNING IT
#     python3 lucelec_rag_bot.py --demo        <- quick test, no website
#     python3 lucelec_rag_bot.py --providers   <- check if your API key works
#     python3 lucelec_rag_bot.py --keys        <- see where keys are stored
#     streamlit run lucelec_rag_bot.py --server.port 8501 --server.address 0.0.0.0
#
#   Central Rule: The Bot is the GPS. The Human is the Driver.
#   The bot NEVER states a tariff that is not in source_documents/.
# =====================================================================

# --- IMPORTS: borrowing tools other people already wrote ---------------
import os          # talks to the computer: files, folders, environment variables
import re          # "regular expressions" — find patterns inside text
import json        # converts Python data <-> JSON text (the language APIs speak)
import math        # square roots and logarithms, used by the search scoring
import glob        # lists files matching a pattern, e.g. every .md in a folder
import stat        # file permission constants, used to lock down the key file
import argparse    # reads the options you type after the filename, like --demo
from collections import Counter    # counts how many times each word appears
from typing import Optional        # lets us say "this might return nothing"


# =====================================================================
# SECTION 0 · POD CONFIG — the only part every Pod must edit
# =====================================================================

BOT_NAME = "TODO_pod_bot_name"   # your bot's name, shown at the top of the app
POD      = "TODO_pod_name"       # your Pod's name, shown under the title
CLIENT   = "LUCELEC (Saint Lucia Electricity Services Limited)"  # who this is for

# WHERE AM I? This matters more than it looks.
# A relative path like "source_documents" is worked out from the folder the
# PROGRAM was started in, not the folder this file lives in. In Deepnote a
# notebook usually runs from ~/work while this file sits in ~/work/files, so
# relative paths quietly point at the wrong place — or at a stale listing,
# which produces the baffling error "glob found the file but open() could not".
# Anchoring everything to this file's own folder makes that whole class of
# bug impossible.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))    # the folder holding THIS file


def project_path(*parts) -> str:
    """Build an absolute path next to this file, wherever it was started from."""
    return os.path.join(BASE_DIR, *parts)            # BASE_DIR + the pieces you passed in


DOCS_DIR = "source_documents"    # the folder holding the client's documents
TOP_K    = 3                     # how many document chunks to send to the AI
CHUNK_WORDS   = 120              # how many words go in one chunk
CHUNK_OVERLAP = 25               # words repeated between neighbouring chunks

# THE RED LINE — things the bot must never do. Your Product Owner signs this off.
MUST_NEVER_DO = [                                                    # a list of rules
    "Never quote a tariff, rate or fee that is not in the source documents.",
    "Never confirm or discuss a specific customer account, meter or balance.",
    "Never give electrical wiring, meter-tampering or repair instructions.",
    "Never promise a refund, credit, reconnection or dispute outcome.",
]                                                                    # list ends here

ESCALATION_LINE = "LUCELEC Customer Service — TODO_phone / TODO_email"  # where to send people


# =====================================================================
# SECTION 1 · THE KEY STORE — where API keys live (the "back end")
# =====================================================================
#   An API key is a password that lets your bot use an AI model. Treat it
#   like a bank card PIN. If someone copies it, they spend YOUR credits.
#
#   THREE RULES, NO EXCEPTIONS:
#     1. A key NEVER goes inside a .py file.
#     2. A key NEVER goes into GitHub.
#     3. A key NEVER gets pasted into a chat, screenshot, or slide.
#
#   So where does it go? Into the "back end" — a file on the server that
#   the app reads at startup and nobody ever sees in the browser.
#
#   This template looks for your key in three places, in this order:
#     1. Environment variables  (best — Deepnote's Environment tab)
#     2. .streamlit/secrets.toml (the file the Save button writes to)
#     3. .env                    (a plain text file, common in tutorials)
#   The first place it finds a key wins. That order matters: it means a
#   real environment variable always beats an old file you forgot about.
# =====================================================================

SECRETS_DIR  = ".streamlit"                          # folder Streamlit looks in
SECRETS_FILE = os.path.join(SECRETS_DIR, "secrets.toml")   # relative name, for display
ENV_FILE     = ".env"                                # the other common key file

# Every key name this bot understands. Section 6 uses the same names.
KEY_NAMES = [                                        # a list of environment variable names
    "OPENAI_API_KEY",                                # for OpenAI
    "GEMINI_API_KEY",                                # for Google Gemini
    "GROQ_API_KEY",                                  # for Groq
    "NVIDIA_API_KEY",                                # for NVIDIA NIM
    "OLLAMA_API_KEY",                                # for Ollama (not actually needed)
]                                                    # list ends here

# Remembers where each key was originally found. Filled in by load_keys().
_ORIGINS = {}                                        # starts empty, fills in at startup


def _parse_simple_toml(text: str) -> dict:
    """Read NAME = "value" lines out of a text file.

    A real TOML parser handles far more than this, but our key file only
    ever holds simple NAME = "value" lines, so twelve lines of code is
    enough and saves students installing another library.
    """
    found = {}                                       # start with an empty dictionary
    for line in text.splitlines():                   # go through the file one line at a time
        line = line.strip()                          # remove spaces at the start and end
        if not line or line.startswith("#"):         # skip blank lines and comments
            continue                                 # "continue" means: next line please
        if "=" not in line:                          # a key line must contain an "="
            continue                                 # no "=" means it is not a key line
        name, _, value = line.partition("=")         # split "A = B" into "A", "=", "B"
        name  = name.strip()                         # tidy the name
        value = value.strip().strip('"').strip("'")  # tidy the value, remove any quotes
        if name:                                     # if there is actually a name left
            found[name] = value                      # store it in the dictionary
    return found                                     # hand the dictionary back


def _read_key_file(path: str) -> dict:
    """Open a key file and return what is inside it. Missing file = empty dict."""
    if not os.path.exists(path):                     # does the file exist?
        return {}                                    # no file, so no keys — return empty
    try:                                             # "try" = attempt this, but do not crash
        with open(path, "r", encoding="utf-8") as f: # open the file for reading
            return _parse_simple_toml(f.read())      # parse everything inside it
    except OSError:                                  # if reading failed for any reason
        return {}                                    # give back nothing rather than crashing


def load_keys() -> dict:
    """Load keys from the back end into the environment, and report where each came from.

    Called once at startup. After this runs, os.getenv("GROQ_API_KEY")
    works everywhere else in the file, no matter which file it came from.

    We remember each key's original source in _ORIGINS. Without that, the
    second time this runs every key would look like it came from the
    environment — because the first run is what put it there.
    """
    from_secrets = _read_key_file(project_path(SECRETS_FILE))   # read .streamlit/secrets.toml
    from_env     = _read_key_file(project_path(ENV_FILE))       # read .env

    for name in KEY_NAMES:                           # check each key name we support
        if name in _ORIGINS and os.getenv(name):     # already worked this one out earlier?
            continue                                 # keep the original answer, skip ahead

        if os.getenv(name):                          # already an environment variable?
            _ORIGINS[name] = "environment"           # note that it came from the environment
        elif name in from_secrets and from_secrets[name]:   # otherwise, in secrets.toml?
            os.environ[name] = from_secrets[name]    # copy it into the environment
            _ORIGINS[name] = SECRETS_FILE            # note which file it came from
        elif name in from_env and from_env[name]:    # otherwise, in .env?
            os.environ[name] = from_env[name]        # copy it into the environment
            _ORIGINS[name] = ENV_FILE                # note which file it came from
        else:                                        # not found anywhere
            _ORIGINS[name] = None                    # note that this key is missing

    # LLM_PROVIDER is not a key, but it is a setting worth loading the same way.
    for setting in ("LLM_PROVIDER",):                # a short list of extra settings
        if not os.getenv(setting):                   # only if not already set
            value = from_secrets.get(setting) or from_env.get(setting)  # look in both files
            if value:                                # if we found something
                os.environ[setting] = value          # load it into the environment

    return dict(_ORIGINS)                            # hand back a copy of the where-from report


def save_key(name: str, value: str) -> str:
    """Write one key into .streamlit/secrets.toml so it survives a restart.

    This is what the Save button in the sidebar calls. The file is created
    with permission 0600, which means "only the owner of this machine can
    read it". It also creates a .gitignore so the key can never be
    committed to GitHub by accident.
    """
    os.makedirs(project_path(SECRETS_DIR), exist_ok=True)   # create .streamlit/ if missing

    gitignore = project_path(SECRETS_DIR, ".gitignore")   # path to a safety file
    if not os.path.exists(gitignore):                # only write it once
        with open(gitignore, "w", encoding="utf-8") as f:  # create the file
            f.write("secrets.toml\n")                # tell git to ignore the key file

    existing = _read_key_file(project_path(SECRETS_FILE))   # load whatever keys are saved
    existing[name] = value.strip()                   # add or replace this one key

    lines = ["# API keys for the LUCELEC bot. NEVER commit this file.",  # a helpful header
             "# Written by save_key(). Delete a line to remove that key.",
             ""]                                     # a blank line for readability
    for k, v in existing.items():                    # go through every saved key
        lines.append(f'{k} = "{v}"')                 # write it as NAME = "value"

    with open(project_path(SECRETS_FILE), "w", encoding="utf-8") as f:   # open for writing
        f.write("\n".join(lines) + "\n")             # join the lines and save

    try:                                             # try to lock the file down
        os.chmod(project_path(SECRETS_FILE), stat.S_IRUSR | stat.S_IWUSR)   # owner only
    except OSError:                                  # some systems will not allow this
        pass                                         # not fatal, so carry on

    os.environ[name] = value.strip()                 # use the new key immediately
    _ORIGINS[name] = SECRETS_FILE                    # remember it came from the key file
    return SECRETS_FILE                              # tell the caller where it went


def delete_key(name: str) -> bool:
    """Remove one key from the saved file and from the running program."""
    existing = _read_key_file(project_path(SECRETS_FILE))   # load the saved keys
    if name not in existing:                         # nothing saved under that name?
        os.environ.pop(name, None)                   # clear it from memory anyway
        return False                                 # report that nothing was deleted
    existing.pop(name)                               # remove it from the dictionary
    lines = [f'{k} = "{v}"' for k, v in existing.items()]   # rebuild the remaining lines
    with open(project_path(SECRETS_FILE), "w", encoding="utf-8") as f:    # open for writing
        f.write("\n".join(lines) + "\n")             # save what is left
    os.environ.pop(name, None)                       # stop using it right now
    _ORIGINS.pop(name, None)                         # forget where it used to come from
    return True                                      # report success


def mask_key(value: str) -> str:
    """Turn 'gsk_abc123456789xyz' into 'gsk_...9xyz' so it is safe to show on screen.

    Never print a whole key. Screens get photographed and screenshots get shared.
    """
    if not value:                                    # empty string or None?
        return "(not set)"                           # say so plainly
    if len(value) <= 8:                              # suspiciously short for a real key
        return "****"                                # hide it completely
    return f"{value[:4]}...{value[-4:]}"             # first four + last four characters


def key_report() -> list:
    """Build the table shown by --keys and by the sidebar: what is set, and from where."""
    where = load_keys()                              # load keys and find out their source
    rows = []                                        # start with an empty list of rows
    for name in KEY_NAMES:                           # one row per key name
        value = os.getenv(name, "")                  # read the value, "" if missing
        rows.append({                                # build a small dictionary per row
            "name":   name,                          # e.g. "GROQ_API_KEY"
            "set":    bool(value),                   # True if there is a value
            "masked": mask_key(value),               # safe-to-display version
            "source": where.get(name) or "-",        # environment, file path, or "-"
        })                                           # row finished
    return rows                                      # hand back all the rows


# Run the loader as soon as this file starts, so keys are ready for everything below.
KEY_SOURCES = load_keys()                            # do it now, once, at import time


# =====================================================================
# SECTION 2 · THE WEEK 1 BLUEPRINT — persona, wardrobe, rulebook, A.R.T.
# =====================================================================
#   Everything your Pod decided in Week 1 lives here, in code.
#   Week 1 asked: WHO is this for, HOW should it sound, WHAT is it
#   allowed to say? Week 4 adds documents. It does not replace any of it.
#
#   The order never changes:  A.R.T. first, then the AI.
#   The classifier is the bouncer at the door. The AI is the person
#   behind the bar. The bouncer does not ask the barman for permission.
# =====================================================================

# ---------------------------------------------------------------------
# 2.1 · USER PERSONA (Day 1) — who you are actually building for
# ---------------------------------------------------------------------
#   One person, not "customers". If you cannot picture them standing in
#   front of you, the persona is not finished.
PERSONA = {                                          # a dictionary describing one real user
    "name":      "TODO_persona_name",                # give them a name, e.g. "Ms. Felicien"
    "who":       "TODO_who_they_are",                # e.g. "a shopkeeper in Vieux Fort, 54"
    "goal":      "TODO_what_they_want",              # what they came to the bot to achieve
    "need":      "TODO_what_they_need_to_know",      # what they must learn to achieve it
    "challenge": "TODO_what_makes_it_hard",          # what stops them today
    "quote":     "TODO_something_they_would_say",    # in their own words, from the interview
}                                                    # persona ends here


# ---------------------------------------------------------------------
# 2.2 · EMPATHY MAP (Day 1) — how they feel at the moment they type
# ---------------------------------------------------------------------
#   This is not decoration. The "feels" line is what picks the register
#   in section 2.3, so a wrong empathy map produces a bot with the wrong
#   voice at the worst possible moment.
EMPATHY_MAP = {                                      # four sides of one moment
    "says":   "TODO_what_they_say_out_loud",         # their actual words to the bot
    "thinks": "TODO_what_they_think_privately",      # what they do not say
    "does":   "TODO_what_they_do",                   # the action they take
    "feels":  "TODO_the_dominant_emotion",           # anxious? rushed? embarrassed? grieving?
}                                                    # empathy map ends here


# ---------------------------------------------------------------------
# 2.3 · THE WARDROBE (Day 1) — the bot's voices, one per mood
# ---------------------------------------------------------------------
#   Code-switching. A person who is frightened about a bill does not want
#   the same voice as a builder pricing up a job. Same facts, different
#   clothes. The facts never change — only the wrapping.
#
#   "lambda t: ..." is a tiny function with no name. It takes text t and
#   returns dressed-up text. TONES["urgent"]("Hello") gives "HELLO ⚡".
TONES = {                                            # dictionary: mood -> a function
    "warm":     lambda t: f"{t} 💛",                  # the default: friendly, unhurried
    "formal":   lambda t: f"Dear customer — {t}",     # for businesses and written records
    "urgent":   lambda t: f"{t.upper()} ⚡",           # for someone who needs it now
    "bereaved": lambda t: f"I'm very sorry for your loss. {t}",   # for an account after a death
    # TODO_students: change these to match YOUR Empathy Map. If your persona
    # is never "urgent", delete urgent and add the register they really need.
}                                                    # wardrobe ends here

DEFAULT_REGISTER = "warm"                            # used when we cannot tell the mood


def dress(register: str, text: str) -> str:
    """Put one of the Wardrobe's outfits on a plain piece of text.

    Every part of the app dresses text through this one function, so if you
    change how a register works you change it in exactly one place.
    """
    voice = TONES.get(register, TONES[DEFAULT_REGISTER])   # .get() avoids a crash on an unknown mood
    return voice(text)                               # call that register's little function


# ---------------------------------------------------------------------
# 2.4 · DIGNITY IN WORDS (Day 4) — jargon translated into plain English
# ---------------------------------------------------------------------
#   Every word on the left is one the client uses and the customer does
#   not. Five minimum, from your Day 4 rewrite exercise.
JARGON_TO_PLAIN = {                                  # dictionary: jargon -> plain English
    "kWh":        "units of electricity",            # the unit on every bill
    "tariff":     "price per unit",                  # what the client calls their price list
    "surcharge":  "extra charge",                    # sounds official, means "you pay more"
    "arrears":    "unpaid amount",                   # a word that frightens people
    "disconnection": "having your power switched off",   # say the real thing, plainly
    # TODO_students: add your own five from the Day 4 exercise.
}                                                    # dictionary ends here


def translate(msg: str) -> str:
    """Swap every jargon word in a sentence for its plain-English version.

    The Week 1 version used msg.split(), which misses "kWh," and "tariff."
    because the punctuation is stuck to the word. This version matches whole
    words wherever they appear and leaves the punctuation alone. Same idea,
    one bug fewer.
    """
    out = msg                                        # start with the original sentence
    for jargon, plain in JARGON_TO_PLAIN.items():    # go through each pair
        pattern = r"\b" + re.escape(jargon) + r"\b"  # \b = word boundary, so "rate" ≠ "grateful"
        out = re.sub(pattern, plain, out, flags=re.IGNORECASE)   # swap every occurrence
    return out                                       # hand back the plain-English sentence


# ---------------------------------------------------------------------
# 2.5 · LOCATION & CONTEXT (Day 4) — the territory rulebook
# ---------------------------------------------------------------------
#   Territory answers: which rules apply to THIS person? For LUCELEC the
#   segment is the customer category, because the rate and the right desk
#   both depend on it.
#
#   Anything the client has not confirmed stays tagged. Never invent a
#   rate to fill a gap — an empty cell is honest, a guess is a liability.
LOCATION_CONTEXT = {                                 # dictionary: segment -> its rules
    "Domestic": {                                    # ordinary households
        "desk":  "LUCELEC Customer Service",         # where to escalate this person
        "rate":  "[Confirm with client]",            # EC$ per unit — NOT yet verified
        "notes": "Household supply. Most appliance questions land here.",
    },
    "Commercial": {                                  # shops, offices, small businesses
        "desk":  "LUCELEC Commercial Desk",
        "rate":  "[Confirm with client]",
        "notes": "Different rate structure from Domestic. Confirm before quoting.",
    },
    "Industrial": {                                  # factories and large plant
        "desk":  "LUCELEC Key Accounts",
        "rate":  "[Confirm with client]",
        "notes": "Demand charges may apply. Always escalate pricing questions.",
    },
    # TODO_students: add the segments YOUR client named in the Day 3 interview.
}                                                    # rulebook ends here


def get_location_context(segment: str):
    """Look up a segment's rules. Returns None if we do not recognise it.

    Returning None matters: section 2.7 treats None as "we do not know
    where this person is", and an unknown territory means escalate.
    """
    return LOCATION_CONTEXT.get(segment)             # .get() gives None instead of crashing


# ---------------------------------------------------------------------
# 2.6 · THE CONFIRMATION REGISTER (Day 3) — nothing fabricated, ever
# ---------------------------------------------------------------------
#   Every fact from the client interview is either confirmed or tagged.
#   There is no third category and no "probably".
CONFIRM_TAG = "[Confirm with client]"                # the exact sticker used all camp


# The two questions every Pod prepared for the Day 3 interview. Keep them
# here so the next person can see what was actually asked, and what came back.
INTERVIEW_QUESTIONS = {                              # Day 3 preparation, kept as a record
    "fact": {                                        # a CLOSED question — one right answer
        "asked":  "TODO_your_FACT_question",         # e.g. "What is the domestic rate per kWh?"
        "answer": "TODO_what_the_client_said",       # write down their exact answer
    },
    "tone": {                                        # an OPEN question — no right answer
        "asked":  "TODO_your_TONE_question",         # e.g. "How should we sound to a worried customer?"
        "answer": "TODO_what_the_client_said",       # their words matter more than your summary
    },
}


# Every fact the client has not yet signed off. This should reach zero
# before Demo Day. An empty "confirmed_by" means the bot must not state it.
CONFIRMATION_REGISTER = [                            # one row per outstanding fact
    {"item": "Domestic energy charge per kWh",       # what needs confirming
     "source": "Day 3 interview",                    # where the claim came from
     "confirmed_by": "",                             # the client's initials, once they confirm
     "date": ""},                                    # the date they confirmed it
    {"item": "Fuel surcharge rate",
     "source": "Day 3 interview",
     "confirmed_by": "",
     "date": ""},
    {"item": "Escalation phone number and email",
     "source": "Day 3 interview",
     "confirmed_by": "",
     "date": ""},
    # TODO_students: one row for every sticker you collected on Day 3 and Day 4.
]


def open_confirmations() -> list:
    """List the facts still waiting on the client. Your homework, in one function."""
    return [row for row in CONFIRMATION_REGISTER     # keep a row...
            if not row["confirmed_by"].strip()]      # ...only if nobody has signed it off


def needs_confirmation(text: str) -> bool:
    """Is this value still waiting on the client? True means do not say it out loud."""
    return CONFIRM_TAG.lower() in str(text).lower()  # str() in case a number was passed in


def scan_for_unconfirmed(index: dict) -> list:
    """Find every chunk still carrying a tag or a TODO_, so the Pod can chase them.

    The Sources tab shows this list. It is your homework, generated automatically.
    """
    flagged = []                                     # chunks that are not client-ready
    for c in index["chunks"]:                        # go through every chunk
        if needs_confirmation(c["text"]) or "TODO_" in c["text"]:   # tagged or unfinished?
            flagged.append({"id": c["id"],           # which chunk
                            "source": c["source"],   # which document
                            "preview": c["text"][:90] + "…"})    # first 90 characters
    return flagged                                   # hand the list back


# ---------------------------------------------------------------------
# 2.7 · THE A.R.T. CLASSIFIER (Day 5) — the VIP bouncer, three checks
# ---------------------------------------------------------------------
#   Authority — am I allowed to answer this at all?
#   Register  — do I know how this person is feeling?
#   Territory — do I know which rules apply to them?
#
#   If ANY check returns None, we escalate. Not "have a guess". Escalate.
#   That strict rule is the whole reason a client trusts a student bot.

def check_authority(user: dict, message: str) -> Optional[str]:
    """Axis 1 — The ID Check. Returns "ok" if allowed to answer, None to escalate.

    Two ways to fail. The person is not verified, OR the question is about
    their own case, which no bot should ever answer.
    """
    if not user.get("id_verified"):                  # has this person been verified?
        return None                                  # no — escalate

    case_specific = ["my account", "my bill", "my meter",        # phrases that mean
                     "am i eligible", "my balance", "my case"]   # "this is about ME"
    low = message.lower()                            # lowercase so capitals do not matter
    if any(phrase in low for phrase in case_specific):   # any of those phrases present?
        return None                                  # yes — escalate, do not answer

    return "ok"                                      # both checks passed


def check_register(user: dict, message: str) -> Optional[str]:
    """Axis 2 — The Vibe Check. Returns the register to use, or None to escalate.

    The Pod's chosen mood wins. If none was chosen, we read the message
    for clues, exactly as in Week 2.
    """
    mood = user.get("mood")                          # did the person tell us how they feel?
    if mood in TONES:                                # is it a register we actually own?
        return mood                                  # use it

    low = message.lower()                            # otherwise, guess from the words
    if "passed away" in low or "died" in low or "deceased" in low:
        return "bereaved"                            # someone has died — soften everything
    if "urgent" in low or "asap" in low or "right now" in low:
        return "urgent"                              # they are in a hurry
    if "invoice" in low or "business" in low or "company" in low:
        return "formal"                              # this is a business conversation

    return DEFAULT_REGISTER                          # no clues — use the safe default


def check_territory(user: dict) -> Optional[dict]:
    """Axis 3 — The Map & Rulebook. Returns the segment's rules, or None to escalate."""
    return get_location_context(user.get("segment"))     # None if we do not know the segment


def _english_list(items: list) -> str:
    """Join a list the way a person speaks it: "A, B or C", not "A or B or C"."""
    if not items:                                    # nothing to list
        return "one of our customer categories"      # a safe general phrase
    if len(items) == 1:                              # only one option
        return items[0]                              # just say it
    return ", ".join(items[:-1]) + " or " + items[-1]    # commas, then "or" for the last


def escalate_message(axis: str, user: dict) -> str:
    """The words the person sees when an axis fails. Say WHY, and say where to go.

    "Something went wrong" helps nobody. Name the reason.
    """
    context = check_territory(user)                  # do we at least know their desk?
    desk = context["desk"] if context else ESCALATION_LINE   # the specific desk, or the default

    reasons = {                                      # a plain sentence per failing axis
        "authority":          "That's about your own account, so a person needs to look at it with you.",
        "authority_unverified": "I haven't been able to confirm who you are, so I can't go further here.",
        "register":  "I'm not sure how best to help with this one.",
        "territory": ("Before I answer that, which kind of customer are you — "
                      + _english_list(list(LOCATION_CONTEXT.keys())) +
                      "? The rules and the rates are different for each, and I'd "
                      "rather ask than guess."),
    }
    # Each axis gets its own closing line. A question that ends "Please contact
    # Customer Service" is not really a question — it is a brush-off wearing a
    # question mark, and the person will read it that way.
    endings = {                                      # axis -> how the message finishes
        "territory": f"If you'd rather not say, {desk} can help you directly.",
        "register":  f"Please contact {desk}.",
        "authority": f"Please contact {desk}.",
        "authority_unverified": f"Please contact {desk}.",
    }
    body   = reasons.get(axis, "I need to hand this over.")   # the explanation
    ending = endings.get(axis, f"Please contact {desk}.")     # the closing line
    return f"{body} {ending}"                        # glue them together


# ---------------------------------------------------------------------
# 2.8 · MEMORY & PRIVACY (Day 2, Responsible AI) — what the bot may remember
# ---------------------------------------------------------------------
#   "What should our chatbot know about its users?" For a bot this young,
#   the honest answer is: almost nothing. Remembering something is a
#   promise to protect it, and you cannot keep that promise yet.
#
#   This is written down as data, not as a paragraph in a document,
#   because the Blueprint tab shows it to the client and because you
#   should have to edit code to change your mind about it.
MEMORY_POLICY = {                                    # the promise, in a form the app can display
    "remember_during_the_conversation": [            # held in memory while the tab is open
        "the register we are speaking in",           # so the voice does not lurch about
        "the segment the person told us they are in",# so we do not ask them twice
        "the appliance numbers they typed",          # so the calculator can use them
    ],
    "never_store": [                                 # never written to disk. Not once.
        "account numbers",                           # Section 3 redacts these before we see them
        "meter numbers",
        "phone numbers and email addresses",
        "anything at all about a named person's bill",
    ],
    "forgotten_when": "The browser tab closes. Nothing is written to a file.",
    # TODO_students: if you add chat logging for Week 3 analysis, you must
    # come back and change this, tell the client, and redact before writing.
}

# =====================================================================
# SECTION 3 · GUARDRAILS — the safety checks, run before anything else
# =====================================================================
#   A guardrail is a check that stops the bot doing something harmful.
#   These run FIRST, before the bot even looks at the documents, because
#   a question we should refuse is not a question we should search.
# =====================================================================

# Patterns that look like personal information. r"..." means "raw text" —
# it stops Python treating backslashes as special.
PII_PATTERNS = {                                     # a dictionary: label -> pattern
    "account_no": r"\b\d{6,12}\b",                   # 6 to 12 digits in a row
    "email":      r"[\w\.-]+@[\w\.-]+\.\w+",         # something@something.something
    "phone":      r"\b(?:\+1[- ]?)?(?:758)?[- ]?\d{3}[- ]?\d{4}\b",   # a phone number
    # TODO_students: add the LUCELEC meter-number pattern once the client confirms it.
}                                                    # dictionary ends here


def redact(text: str) -> str:
    """Replace personal information with [REDACTED] before we store or send anything.

    If a customer types their account number, it should never reach an AI
    company's servers or a log file. This is the last moment we can stop that.
    """
    safe = text                                      # start with the original text
    for label, pattern in PII_PATTERNS.items():      # go through every pattern
        safe = re.sub(pattern, f"[REDACTED_{label.upper()}]", safe)   # swap matches for a label
    return safe                                      # return the cleaned-up text


# Patterns for questions the bot must refuse outright.
REFUSE_PATTERNS = {                                  # dictionary: reason -> pattern
    "account_specific": r"\b(my account|my bill|my meter|account number|balance|disconnect(ed)?|reconnect)\b",
    "unsafe_electrical": r"\b(rewire|wiring|bypass|tamper|open the meter|live wire|transformer)\b",
}                                                    # dictionary ends here


def check_red_line(message: str) -> Optional[str]:
    """Decide whether to refuse. Returns a refusal message, or None to continue.

    "Optional[str]" means: this gives back either some text, or nothing at all.
    """
    low = message.lower()                            # lowercase so "BILL" matches "bill"
    if re.search(REFUSE_PATTERNS["account_specific"], low):   # asking about their own account?
        return ("I can explain how electricity costs work in general, but I can't look at "
                f"anything on your account. For that, please contact {ESCALATION_LINE}.")
    if re.search(REFUSE_PATTERNS["unsafe_electrical"], low):  # asking about wiring or meters?
        return ("I can't help with anything involving electrical equipment or meters — that's "
                f"unsafe and it's LUCELEC's job. Please call {ESCALATION_LINE}.")
    return None                                      # nothing matched, so carry on


# =====================================================================
# SECTION 4 · LOADING AND CHUNKING — turning documents into searchable pieces
# =====================================================================
#   An AI model cannot read a whole folder. We cut documents into small
#   pieces called "chunks", then search the chunks. A chunk is roughly a
#   paragraph: big enough to make sense, small enough to be specific.
# =====================================================================

# Starter documents, written into source_documents/ the first time you run this.
# Replace all of them with real LUCELEC material.
SEED_DOCS = {                                        # dictionary: filename -> file contents
    "tariff_basics.md": """# LUCELEC Tariff Basics (SAMPLE — NOT VERIFIED)

TODO_students: replace every number below with figures confirmed by the client
and log each one as a row in your Confirmation Register.

Domestic customers are billed per kilowatt-hour (kWh) consumed. A kilowatt-hour
is one thousand watts drawn for one hour.

Sample domestic energy charge: TODO_rate EC$ per kWh.
Sample fuel surcharge: TODO_fuel EC$ per kWh, adjusted monthly.
A fixed monthly customer charge may also apply.

To estimate a bill: multiply the kWh used by the energy charge, add the fuel
surcharge on the same kWh, then add the fixed charge.
""",
    "appliance_wattage.md": """# Typical Appliance Wattage (SAMPLE — NOT VERIFIED)

TODO_students: confirm these ratings against the appliance energy label.
The energy label on the appliance always beats this table.

Refrigerator (inverter, 18 cu ft): about 150 watts while running.
Refrigerator (older, non-inverter): about 350 watts while running.
Window air conditioner (12,000 BTU): about 1200 watts.
Inverter split air conditioner (12,000 BTU): about 900 watts.
Electric water heater (40 gallon): about 4000 watts.
Solar water heater: about 0 watts for heating.
Clothes iron: about 1100 watts.
LED bulb: about 9 watts. Incandescent bulb: about 60 watts.
Television (LED, 43 inch): about 70 watts.
Standby power for a television left plugged in: about 1 watt.
""",
    "energy_saving_faq.md": """# Energy Saving FAQ (SAMPLE — NOT VERIFIED)

Which appliances use the most electricity?
Anything that makes heat or cold for long periods: water heaters, air
conditioners, refrigerators, and clothes dryers.

Does leaving a device on standby cost anything?
Yes, but very little per device. The cost adds up across many devices left
plugged in all year.

How do I read an energy label?
The label states the appliance's power draw in watts, or its estimated annual
consumption in kilowatt-hours. Lower annual kWh means a cheaper appliance to run.

Is a more expensive efficient appliance worth it?
Compare the purchase price difference against the running-cost difference over
the years you expect to own it. The cheaper appliance to buy is often the more
expensive one to own.
""",
}                                                    # dictionary of seed documents ends here


def ensure_docs():
    """Create source_documents/ with the sample files if they are missing.

    Checks each seed file individually rather than just asking "is the folder
    empty". A folder can list a file that cannot actually be opened — a broken
    shortcut, a half-finished sync — and in that case we want to write a good
    copy rather than trust the listing.
    """
    folder = project_path(DOCS_DIR)                  # the absolute path, not a relative guess
    os.makedirs(folder, exist_ok=True)               # make it; fine if it already exists

    for name, body in SEED_DOCS.items():             # go through each sample document
        path = os.path.join(folder, name)            # where it should be
        try:                                         # can we actually READ it?
            with open(path, "r", encoding="utf-8") as f:   # try to open it
                if f.read(1):                        # and is there something inside?
                    continue                         # yes — leave it alone
        except OSError:                              # missing, broken, or unreadable
            pass                                     # fall through and write a fresh copy

        # A broken shortcut is the awkward case: the folder lists the name, but
        # opening it for writing ALSO fails, because the computer follows the
        # shortcut to a place that does not exist. Remove the dead shortcut
        # first, then write a real file in its place.
        if os.path.islink(path) and not os.path.exists(os.path.realpath(path)):
            try:                                     # try to clear the dead link
                os.unlink(path)                      # delete the shortcut, not its target
                print(f"[ensure_docs] removed a broken shortcut: {name}")
            except OSError:                          # could not remove it
                pass                                 # the write below will report the problem

        try:                                         # write the sample document
            with open(path, "w", encoding="utf-8") as f:   # create or replace it
                f.write(body)                        # put the text in
        except OSError as e:                         # the disk said no
            print(f"[ensure_docs] could not write {path}: {e}")   # say so, do not crash


def chunk_text(text: str, source: str) -> list:
    """Cut one document into overlapping windows of words.

    Why overlap? If a sentence is split across two chunks, neither chunk
    makes sense on its own. Repeating the last 25 words in the next chunk
    means an idea that straddles the join still appears whole somewhere.
    """
    words = text.split()                             # split the text into a list of words
    chunks = []                                      # the finished chunks go here
    start = 0                                        # which word to start the next chunk at
    n = 0                                            # counts chunks, used for the chunk id
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)       # how far to jump: 120 - 25 = 95 words

    while start < len(words):                        # keep going until we run out of words
        window = words[start:start + CHUNK_WORDS]    # take the next 120 words
        if window:                                   # if we actually got some words
            n += 1                                   # this is chunk number n
            chunks.append({                          # add a dictionary describing this chunk
                "id":     f"{source}#{n}",           # e.g. "tariff_basics.md#2"
                "source": source,                    # which file it came from
                "text":   " ".join(window),          # the words joined back into a sentence
            })                                       # chunk dictionary ends here
        start += step                                # jump forward, leaving the overlap
    return chunks                                    # hand back every chunk from this document


def load_chunks() -> list:
    """Read every document in source_documents/ and chunk them all into one big list.

    TODO_students: add PDF support with pypdf so the client can drop their
    own PDFs straight in without converting anything first.
    """
    ensure_docs()                                    # make sure there is something to read
    chunks = []                                      # all chunks from all documents
    skipped = []                                     # files we could not read, for the warning

    folder = project_path(DOCS_DIR)                  # absolute, so the cwd cannot mislead us
    for path in sorted(glob.glob(os.path.join(folder, "*"))):   # every file, alphabetically
        if not path.lower().endswith((".md", ".txt")):   # we only understand .md and .txt
            continue                                 # skip anything else for now
        try:                                         # a listed file is not always a readable one
            with open(path, "r", encoding="utf-8", errors="ignore") as f:   # open the document
                text = f.read()                      # read the whole thing
        except OSError as e:                         # broken shortcut, permissions, half-synced
            skipped.append(f"{os.path.basename(path)} ({type(e).__name__})")  # note it
            continue                                 # skip this one, keep the rest working
        chunks.extend(chunk_text(text, os.path.basename(path)))   # chunk it, add to the list

    if skipped:                                      # tell somebody, but do not crash
        print(f"[load_chunks] skipped unreadable files: {', '.join(skipped)}. "
              f"Run: python3 lucelec_rag_bot.py --doctor")
    return chunks                                    # hand back every chunk we could read



# ---------------------------------------------------------------------
# 4.5 · HARVESTING FROM THE CLIENT'S WEBSITE
# ---------------------------------------------------------------------
#   READ THIS BEFORE YOU USE IT.
#
#   Downloading a page is NOT the same as confirming a fact. A rate on a
#   web page might be out of date, might be for a different customer
#   class, might be a draft nobody took down. If the bot quotes it to a
#   customer and it is wrong, the client carries the blame, not the page.
#
#   So harvested pages DO NOT go into source_documents/. They go into
#   pending_review/, which retrieval never reads. A human being has to
#   look at the text and approve it with their initials before the bot
#   can ever say it out loud. Scraping fills a waiting room, not the
#   knowledge base.
#
#   Three more rules, which are about being a good guest on someone
#   else's server:
#     1. ONLY the client's own domain. Never the whole internet.
#     2. Obey robots.txt. It is the site owner saying what is allowed.
#     3. Go slowly, and say who you are in the User-Agent.
# ---------------------------------------------------------------------

# Only these domains may ever be fetched. Everything else is refused.
#   Put HOSTNAMES here, not page addresses. "lucelec.com" is a hostname;
#   "https://www.lucelec.com/content/services" is a page. A full URL is
#   tidied up automatically, but a path in this list does nothing useful —
#   the allowlist controls which SITE may be fetched, and every page on
#   that site is then allowed (subject to robots.txt).
ALLOWED_DOMAINS = [                                  # the client's own website, nothing else
    "lucelec.com",                                   # LUCELEC's domain (www. is accepted too)
    # TODO_students: add another host ONLY if the client tells you to in writing.
]

PENDING_DIR = "pending_review"                       # the waiting room. Retrieval never looks here.

# Tells LUCELEC's server who is knocking. Rude to leave this as a default.
HARVEST_USER_AGENT = ("ECCU-GAP-Camp-StudentBot/1.0 "        # who we are
                      "(educational project; contact TODO_facilitator_email)")

FETCH_DELAY_SECONDS = 2                              # wait this long between pages. Be polite.
MAX_PAGE_BYTES = 2_000_000                           # refuse anything over 2MB (a page is ~100KB)


def _normalise_domain(entry: str) -> str:
    """Reduce anything a student might type to a bare hostname.

    All of these become "www.lucelec.com":
        www.lucelec.com
        https://www.lucelec.com
        https://www.lucelec.com/content/services
        WWW.LUCELEC.COM/
    Pasting a whole URL into the allowlist is the obvious thing to do, so
    the code should cope with it instead of refusing everything silently.
    """
    e = entry.strip().lower()                        # tidy spaces, ignore capitals
    e = re.sub(r"^[a-z][a-z0-9+.-]*://", "", e)      # chop off "https://" or "http://"
    e = e.split("/")[0]                              # chop off "/content/services"
    e = e.split("?")[0]                              # chop off any "?query=stuff"
    e = e.split(":")[0]                              # chop off a ":8080" port
    return e                                         # what is left is the hostname


def allowed_hosts() -> set:
    """Every hostname we may fetch, including the www. twin of each one.

    If you allow lucelec.com you almost certainly meant www.lucelec.com too,
    so both are accepted. Everything else on the internet is still refused.
    """
    hosts = set()                                    # start with an empty set
    for entry in ALLOWED_DOMAINS:                    # go through the list at the top
        host = _normalise_domain(entry)              # reduce it to a hostname
        if not host:                                 # the entry was blank or nonsense
            continue                                 # skip it
        hosts.add(host)                              # the hostname itself
        if host.startswith("www."):                  # if it starts with www.
            hosts.add(host[4:])                      # also allow it without
        else:                                        # otherwise
            hosts.add("www." + host)                 # also allow the www. version
    return hosts                                     # hand back every acceptable hostname


def is_allowed_domain(url: str) -> bool:
    """Is this URL on the client's own website? Anything else is refused."""
    from urllib.parse import urlparse                # splits a web address into its parts
    host = (urlparse(url).hostname or "").lower()    # e.g. "www.lucelec.com"
    return host in allowed_hosts()                   # must be one of the permitted hostnames


def _load_robots(url: str) -> dict:
    """Fetch and parse a site's robots.txt USING OUR OWN User-Agent.

    Why this exists, and it is worth reading:

    Python's RobotFileParser has a .read() method that downloads robots.txt
    for you. It downloads it as "Python-urllib/3.x". Plenty of sites sit
    behind a firewall that blocks that name, answers 403, and RobotFileParser
    then quietly decides EVERYTHING is forbidden.

    The result is a bot that refuses every page on a site that actually
    allows it — and the reason is invisible, because the rules themselves
    were never the problem. So we fetch the file ourselves, with the same
    polite User-Agent we use for real pages, and hand the text to the parser.
    """
    from urllib.parse import urlparse                # to find the site root
    from urllib.robotparser import RobotFileParser   # the rules parser
    import urllib.request, urllib.error              # to do the fetch ourselves

    parts = urlparse(url)                            # break the URL apart
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"   # always at the root

    out = {"robots_url": robots_url, "status": None, # what we hand back
           "text": "", "parser": None, "note": ""}

    req = urllib.request.Request(                    # build the request
        robots_url, headers={"User-Agent": HARVEST_USER_AGENT})   # OUR name, not urllib's

    try:                                             # try to read the file
        with urllib.request.urlopen(req, timeout=15) as r:        # 15 seconds is plenty
            out["status"] = r.status                 # 200 means we have rules
            out["text"] = r.read(200_000).decode("utf-8", errors="ignore")
        rp = RobotFileParser()                       # make a parser
        rp.parse(out["text"].splitlines())           # feed it the text WE downloaded
        out["parser"] = rp                           # keep it for the caller
        out["note"] = "robots.txt found and read."
    except urllib.error.HTTPError as e:              # the server answered with an error
        out["status"] = e.code                       # 404? 403?
        if e.code in (401, 403):                     # the site is hiding its rules
            out["note"] = ("The server refused to show robots.txt even to a named "
                           "User-Agent. We refuse to fetch anything, to be safe. "
                           "Ask the client whether they can allow you.")
        else:                                        # 404 and friends
            out["note"] = ("No robots.txt on this site, so everything is allowed. "
                           "The file is optional.")
    except Exception as e:                           # network down, DNS failure, timeout
        out["note"] = (f"Could not reach the site at all ({type(e).__name__}). "
                       "Check the address, and check Deepnote is allowed out "
                       "to the internet.")
    return out                                       # hand the whole picture back


def robots_allows(url: str) -> bool:
    """May we fetch this page, according to the site's own rules?

    No robots.txt at all means yes — the file is optional and most small
    sites do not have one. A robots.txt we cannot read means no.
    """
    info = _load_robots(url)                         # fetch and parse the rules

    if info["parser"] is not None:                   # we have real rules
        return info["parser"].can_fetch(HARVEST_USER_AGENT, url)   # ask them

    if info["status"] is not None and info["status"] not in (401, 403):
        return True                                  # 404: no rules exist, so nothing forbids us

    return False                                     # hidden rules, or no connection: refuse


def robots_crawl_delay(url: str) -> float:
    """How long the site asks crawlers to wait between pages.

    LUCELEC's robots.txt asks for 10 seconds. Ignoring that is exactly the
    kind of thing that gets a school's IP address blocked, so we obey the
    site's number whenever it is longer than our own.
    """
    info = _load_robots(url)                         # read the rules
    if info["parser"] is None:                       # no rules to read
        return FETCH_DELAY_SECONDS                   # use our own default
    try:                                             # the site may state a delay
        stated = info["parser"].crawl_delay(HARVEST_USER_AGENT)   # None if not stated
    except Exception:                                # very old Python, or odd rules
        stated = None                                # treat as not stated
    return max(FETCH_DELAY_SECONDS, float(stated or 0))   # obey whichever is longer


def check_robots(url: str) -> dict:
    """Explain what the site's robots.txt says about a page. A debugging tool.

    This uses exactly the same loader as the decision above, so what you read
    here and what the harvester does can never disagree.
    """
    info = _load_robots(url)                         # one loader, one truth
    return {"page": url,                             # the page you asked about
            "robots_url": info["robots_url"],        # where the rules live
            "status": info["status"],                # 200, 404, 403, or None
            "note": info["note"],                    # what that means, in words
            "rules": info["text"].strip()[:600],     # the first 600 characters
            "crawl_delay_seconds": robots_crawl_delay(url),   # how long we will wait
            "may_we_fetch": robots_allows(url)}      # the answer the harvester uses


def html_to_text(html: str) -> str:
    """Turn a web page into plain readable text.

    Uses BeautifulSoup if it is installed, because it is much better at this.
    Falls back to regular expressions if it is not, so the feature still works
    on a machine where pip install failed.
    """
    try:                                             # --- the good way ---
        from bs4 import BeautifulSoup                # a library built for reading HTML
        soup = BeautifulSoup(html, "html.parser")    # parse the page
        for tag in soup(["script", "style", "nav", "footer", "header"]):   # junk we never want
            tag.decompose()                          # delete those tags entirely
        text = soup.get_text("\n")                   # pull out the human-readable words
    except ImportError:                              # --- the built-in way ---
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)   # delete scripts and styling
        text = re.sub(r"(?s)<[^>]+>", "\n", text)    # replace every remaining tag with a line break
        import html as html_module                   # Python's own HTML helper
        text = html_module.unescape(text)            # turn &amp; back into &

    lines = [ln.strip() for ln in text.splitlines()] # tidy every line
    lines = [ln for ln in lines if ln]               # drop the blank ones
    return "\n".join(lines)                          # glue it back together


def fetch_url(url: str) -> dict:
    """Download one page from the client's website, with every safety check first.

    Returns a dictionary. Check the "ok" key before using anything else.
    """
    if not is_allowed_domain(url):                   # CHECK 1: is it the client's site?
        from urllib.parse import urlparse            # to name the host in the error
        host = (urlparse(url).hostname or "(no hostname — is the https:// missing?)")
        return {"ok": False, "url": url,
                "error": f"Refused — '{host}' is not an allowed host. "
                         f"Allowed: {', '.join(sorted(allowed_hosts()))}. "
                         f"ALLOWED_DOMAINS holds hostnames, not full page addresses."}

    if not robots_allows(url):                       # CHECK 2: does robots.txt permit it?
        return {"ok": False, "url": url,
                "error": "Refused — the site's robots.txt does not allow this page."}

    import urllib.request, urllib.error              # Python's built-in internet tools
    import time                                      # so we can pause between pages

    delay = robots_crawl_delay(url)                  # CHECK 3: how long does the site ask for?
    time.sleep(delay)                                # wait that long. Be a good guest.

    req = urllib.request.Request(                    # build the request
        url, headers={"User-Agent": HARVEST_USER_AGENT})   # say who we are

    try:                                             # attempt the download
        with urllib.request.urlopen(req, timeout=30) as r:     # 30 seconds, then give up
            content_type = r.headers.get("Content-Type", "")   # HTML? PDF? something else?
            raw = r.read(MAX_PAGE_BYTES)             # read, but never more than the limit
    except urllib.error.HTTPError as e:              # the server said no
        return {"ok": False, "url": url, "error": f"HTTP {e.code} from the server."}
    except Exception as e:                           # network down, timeout, anything else
        return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}

    if "pdf" in content_type.lower():                # the client posts tariffs as PDFs
        try:                                         # try to read the PDF
            import io                                # lets us treat bytes like a file
            from pypdf import PdfReader              # the PDF reading library
            reader = PdfReader(io.BytesIO(raw))      # open the downloaded bytes as a PDF
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except ImportError:                          # pypdf is not installed
            return {"ok": False, "url": url,
                    "error": "This is a PDF. Run: pip install pypdf"}
    else:                                            # it is an ordinary web page
        text = html_to_text(raw.decode("utf-8", errors="ignore"))   # HTML to plain text

    return {"ok": True, "url": url, "text": text,    # success
            "content_type": content_type, "bytes": len(raw)}


def _slugify(url: str) -> str:
    """Turn a URL into a safe filename. '/content/services' becomes 'content-services'."""
    from urllib.parse import urlparse                # to get just the path part
    path = urlparse(url).path.strip("/") or "index"  # the path, or "index" for the home page
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower())  # anything odd becomes a dash
    return slug.strip("-")[:60] or "page"            # trim, cap the length, never empty


def harvest(url: str) -> dict:
    """Fetch one page and save it to the WAITING ROOM. Not to the knowledge base.

    The saved file carries a header saying where it came from, when, and that
    nobody has approved it yet. That header is deliberately loud.
    """
    result = fetch_url(url)                          # do the fetch, with all the checks
    if not result["ok"]:                             # something was refused or failed
        return result                                # hand the error straight back

    os.makedirs(project_path(PENDING_DIR), exist_ok=True)   # create the waiting room if needed

    from datetime import date                        # so we can stamp today's date
    filename = f"{_slugify(url)}.md"                 # e.g. "content-services.md"
    path = os.path.join(project_path(PENDING_DIR), filename)   # absolute, so cwd cannot mislead

    header = (                                       # the provenance block, written at the top
        f"# Harvested from the client's website\n\n"
        f"Source URL: {url}\n"                       # exactly where it came from
        f"Fetched on: {date.today().isoformat()}\n"  # exactly when
        f"Status: {CONFIRM_TAG} — NOT APPROVED. "    # the sticker the whole camp uses
        f"No one may quote anything below this line yet.\n\n"
        f"---\n\n"                                   # a visible divider
    )

    with open(path, "w", encoding="utf-8") as f:     # create the file
        f.write(header + result["text"])             # header first, then the page text

    CONFIRMATION_REGISTER.append({                   # add a row to the register
        "item": f"Web page: {url}",                  # what needs confirming
        "source": f"{PENDING_DIR}/{filename}",       # where the text is sitting
        "confirmed_by": "",                          # nobody yet
        "date": "",
    })

    return {"ok": True, "url": url, "path": path,    # report success
            "words": len(result["text"].split()),    # how much text we got
            "preview": result["text"][:400]}         # the first 400 characters, to eyeball


def list_pending() -> list:
    """Everything sitting in the waiting room, waiting for a human to approve it."""
    if not os.path.isdir(project_path(PENDING_DIR)):    # waiting room does not exist yet
        return []                                    # so nothing is waiting

    rows = []                                        # one entry per pending file
    for path in sorted(glob.glob(os.path.join(project_path(PENDING_DIR), "*.md"))):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:   # open it
            text = f.read()                          # read the whole thing
        source = re.search(r"Source URL: (.+)", text)    # dig the URL out of the header
        rows.append({"file": os.path.basename(path),     # just the filename
                     "url": source.group(1).strip() if source else "unknown",
                     "words": len(text.split()),         # how long it is
                     "preview": text[:300]})             # the first 300 characters
    return rows                                      # hand back the list


def approve_harvest(filename: str, initials: str) -> dict:
    """A HUMAN approves a harvested page, which moves it into the knowledge base.

    This is the only door between the waiting room and source_documents/.
    Your initials go in the file. If the bot later says something wrong from
    this page, the register shows who let it through. That is the point.
    """
    if not initials.strip():                         # no initials typed?
        return {"ok": False, "error": "Approval needs your initials. Someone must own this."}

    src = os.path.join(project_path(PENDING_DIR), filename)    # where it is now
    if not os.path.exists(src):                      # is it actually there?
        return {"ok": False, "error": f"{filename} is not in {PENDING_DIR}/."}

    with open(src, "r", encoding="utf-8", errors="ignore") as f:   # read the pending file
        text = f.read()

    from datetime import date                        # for the approval date
    today = date.today().isoformat()                 # e.g. "2026-07-24"

    text = text.replace(                             # swap the loud warning for a signature
        f"Status: {CONFIRM_TAG} — NOT APPROVED. "
        f"No one may quote anything below this line yet.",
        f"Status: APPROVED by {initials.strip()} on {today}. "
        f"Checked against the client's own website.")

    dest = os.path.join(project_path(DOCS_DIR), f"web-{filename}")   # "web-" shows the origin
    with open(dest, "w", encoding="utf-8") as f:     # write it into the real knowledge base
        f.write(text)
    os.remove(src)                                   # take it out of the waiting room

    for row in CONFIRMATION_REGISTER:                # find its row in the register
        if row["source"].endswith(filename):         # this is the one
            row["confirmed_by"] = initials.strip()   # sign it
            row["date"] = today                      # date it

    return {"ok": True, "path": dest, "by": initials.strip(), "date": today}


def reject_harvest(filename: str) -> dict:
    """Throw a harvested page away. Wrong, out of date, or not worth keeping."""
    path = os.path.join(project_path(PENDING_DIR), filename)   # where it is
    if not os.path.exists(path):                     # already gone?
        return {"ok": False, "error": f"{filename} is not in {PENDING_DIR}/."}
    os.remove(path)                                  # delete it

    CONFIRMATION_REGISTER[:] = [                     # [:] edits the list in place
        row for row in CONFIRMATION_REGISTER         # keep every row...
        if not row["source"].endswith(filename)]     # ...except this one's
    return {"ok": True, "removed": filename}


# TODO_students (stretch): harvest() takes one page at a time on purpose.
# If you want to walk a whole section of the site, write a loop that collects
# links from a page, filters them through is_allowed_domain(), and calls
# harvest() on each with the delay in place. Ask the client first.


# =====================================================================
# SECTION 5 · RETRIEVAL — finding the right chunks for a question
# =====================================================================
#   This is the "R" in RAG, and it matters more than the AI model. A
#   brilliant model given the wrong paragraph gives a confident wrong
#   answer. A basic model given the right paragraph gives a good one.
# =====================================================================

# Words too common to be useful when searching. "the" appears everywhere.
STOPWORDS = set("""a an and are as at be but by can do does for from has have how i if in is it its
me my no not of on or so that the their there these this to was what when where which who why will
with you your""".split())                            # split() turns the text into a list of words


def tokenize(text: str) -> list:
    """Turn a sentence into a clean list of searchable words.

    "How much does an AC cost?" becomes ["much", "ac", "cost"].
    """
    words = re.findall(r"[a-z0-9]+", text.lower())   # lowercase, then grab letters and digits only
    return [w for w in words if w not in STOPWORDS and len(w) > 1]   # drop stopwords and single letters


def build_index(chunks: list) -> dict:
    """Work out how rare each word is, so rare words count for more when searching.

    This is called IDF, "inverse document frequency". "electricity" appears
    in every chunk, so matching it proves nothing. "standby" appears in one
    chunk, so matching it is a strong signal. IDF turns that idea into a number.
    """
    df = Counter()                                   # counts how many chunks contain each word
    for c in chunks:                                 # go through every chunk
        df.update(set(tokenize(c["text"])))          # set() = count each word once per chunk
    total = max(1, len(chunks))                      # total chunks, never zero (avoids dividing by 0)
    idf = {term: math.log(1 + total / (1 + count))   # rare word = big number, common word = small
           for term, count in df.items()}            # do this for every word we have seen
    return {"chunks": chunks, "idf": idf}            # the "index" is the chunks plus these scores


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

    idf = index["idf"]                               # the rarity scores from build_index
    scored = []                                      # will hold (score, chunk) pairs

    for c in index["chunks"]:                        # go through every chunk
        tf = Counter(tokenize(c["text"]))            # count each word inside this chunk
        score = sum(tf[t] * idf.get(t, 0.0) for t in q_terms)   # add up matches, weighted by rarity
        score /= math.sqrt(sum(tf.values()) or 1)    # divide by chunk length so long chunks don't win
        if score > 0:                                # only keep chunks that matched something
            scored.append((score, c))                # remember the score and the chunk

    scored.sort(key=lambda x: x[0], reverse=True)    # sort highest score first
    return [{"score": round(s, 4), **c} for s, c in scored[:k]]   # return the top k, score attached


def format_context(hits: list) -> str:
    """Number the chosen chunks so the AI can cite them as [1], [2], [3]."""
    return "\n\n".join(                              # join the pieces with blank lines between
        f"[{i}] (source: {h['source']})\n{h['text']}"    # label, filename, then the text
        for i, h in enumerate(hits, 1))              # enumerate(..., 1) numbers them from 1, not 0


# =====================================================================
# SECTION 6 · THE AI MODEL — one function, five providers
# =====================================================================
#   OpenAI, Gemini, Groq, NVIDIA and Ollama all accept the SAME request:
#   POST /chat/completions with a list of messages. So we do not need five
#   pieces of code. We need one, plus a table of what is different:
#   the web address, the key, and the model name. That table is below.
#
#   Adding a sixth provider = adding one more entry to this dictionary.
# =====================================================================

PROVIDERS = {                                        # dictionary: short name -> settings
    "openai": {                                      # ---- OpenAI ----
        "label":     "OpenAI",                       # the pretty name shown on screen
        "key_env":   "OPENAI_API_KEY",               # which key this provider needs
        "base_url":  "https://api.openai.com/v1",    # the web address to send requests to
        "model":     "gpt-5.4-mini",                 # which model to use by default
        "model_env": "OPENAI_MODEL",                 # variable that overrides the model name
        "needs_key": True,                           # True = will not work without a key
        "get_key":   "https://platform.openai.com/api-keys",   # where to sign up
    },
    "gemini": {                                      # ---- Google Gemini ----
        "label":     "Google Gemini",
        "key_env":   "GEMINI_API_KEY",
        # Google runs an "OpenAI compatible" address, so the same code works.
        "base_url":  "https://generativelanguage.googleapis.com/v1beta/openai",
        "model":     "gemini-3.6-flash",
        "model_env": "GEMINI_MODEL",
        "needs_key": True,
        "get_key":   "https://aistudio.google.com/apikey",
    },
    "groq": {                                        # ---- Groq: free and very fast ----
        "label":     "Groq",
        "key_env":   "GROQ_API_KEY",                 # this key starts with gsk_
        "base_url":  "https://api.groq.com/openai/v1",
        # Groq retired the Llama chat models. gpt-oss-20b is the small fast one;
        # gpt-oss-120b is stronger. Check console.groq.com/docs/models.
        "model":     "openai/gpt-oss-20b",
        "model_env": "GROQ_MODEL",
        "needs_key": True,
        "get_key":   "https://console.groq.com/keys",
    },
    "nvidia": {                                      # ---- NVIDIA NIM: free credits ----
        "label":     "NVIDIA NIM",
        "key_env":   "NVIDIA_API_KEY",               # this key starts with nvapi-
        "base_url":  "https://integrate.api.nvidia.com/v1",
        "model":     "meta/llama-3.3-70b-instruct",
        "model_env": "NVIDIA_MODEL",
        "needs_key": True,
        "get_key":   "https://build.nvidia.com",
    },
    "ollama": {                                      # ---- Ollama: runs on your own machine ----
        "label":     "Ollama (local, free)",
        "key_env":   "OLLAMA_API_KEY",               # not really needed; any text works
        # os.getenv(A, B) means "use A if it is set, otherwise use B".
        "base_url":  os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "model":     "llama3.2",
        "model_env": "OLLAMA_MODEL",
        "needs_key": False,                          # False = no key required at all
        "get_key":   "https://ollama.com/download  →  ollama pull llama3.2",
    },
}                                                    # provider table ends here

# The order to try providers in. If the first one fails, try the next.
# This is called Multi-Provider Fallback, and it is why your demo survives
# a key running out of credit thirty seconds before you present.
PROVIDER_CHAIN = ["openai", "gemini", "groq", "nvidia", "ollama"]

# Remembers which provider answered most recently, so the app can display it.
LAST_CALL = {"provider": None, "model": None, "error": None}


def provider_model(name: str) -> str:
    """Which model name to use — the override if there is one, otherwise the default."""
    p = PROVIDERS[name]                              # look up this provider's settings
    return os.getenv(p["model_env"], p["model"])     # environment variable wins if it exists


def provider_key(name: str) -> str:
    """Fetch this provider's API key from the environment. Empty string if missing."""
    return os.getenv(PROVIDERS[name]["key_env"], "").strip()   # .strip() removes stray spaces


def ollama_up(base_url: str) -> bool:
    """Ollama needs no key, so instead we check whether the program is running."""
    import socket                                    # low-level networking, for a quick knock
    from urllib.parse import urlparse                # splits a web address into its parts
    u = urlparse(base_url)                           # e.g. host "localhost", port 11434
    try:                                             # attempt to connect
        socket.create_connection(                    # knock on the door
            (u.hostname or "localhost", u.port or 11434), timeout=0.7).close()   # then hang up
        return True                                  # someone answered — Ollama is running
    except OSError:                                  # nobody answered, or it timed out
        return False                                 # Ollama is not available


def is_configured(name: str) -> bool:
    """Is this provider ready to use right now?"""
    p = PROVIDERS[name]                              # look up its settings
    if p["needs_key"]:                               # if it requires a key
        return bool(provider_key(name))              # ready only if we have one
    return ollama_up(p["base_url"])                  # otherwise, check the local server


def provider_status() -> list:
    """Build the list the sidebar shows: every provider and whether it is ready."""
    return [{"name": n,                              # short name, e.g. "groq"
             "label": PROVIDERS[n]["label"],         # pretty name, e.g. "Groq"
             "model": provider_model(n),             # which model would be used
             "ready": is_configured(n)}              # True or False
            for n in PROVIDER_CHAIN]                 # one entry per provider, in chain order


def active_chain() -> list:
    """Decide the order to try providers in. LLM_PROVIDER pins one to the front."""
    pinned = os.getenv("LLM_PROVIDER", "").strip().lower()   # did someone pick a favourite?
    if pinned in PROVIDERS:                          # is it a name we recognise?
        return [pinned] + [n for n in PROVIDER_CHAIN if n != pinned]   # favourite first, rest after
    return list(PROVIDER_CHAIN)                      # no favourite, use the normal order


def _extract_text(data: dict, label: str) -> str:
    """Dig the answer out of a reply, whatever shape the provider sent back.

    Written after two real crashes. Providers do NOT all return the same
    thing, even though they all claim the same format:

      · Some return message.content as null and put the words somewhere else.
      · Reasoning models can spend the whole budget thinking and return a
        message with no content key at all.
      · Some return an "error" object with a perfectly normal 200 status.

    Reaching straight for data["choices"][0]["message"]["content"] crashes
    with KeyError on every one of those. So we look in each likely place,
    and if there is genuinely no text we raise a message that says WHY,
    which lets the provider chain move on to the next one.
    """
    if not isinstance(data, dict):                   # not even a dictionary?
        raise RuntimeError(f"{label}: reply was not JSON.")

    if "error" in data:                              # a 200 response carrying an error
        err = data["error"]                          # usually a dictionary
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise RuntimeError(f"{label}: {msg[:200]}")  # pass the provider's own words along

    choices = data.get("choices") or []              # the list of answers
    if not choices:                                  # no answers at all
        raise RuntimeError(f"{label}: reply contained no choices.")

    first = choices[0] or {}                         # we only ever ask for one
    message = first.get("message") or {}             # the assistant's message

    for candidate in (message.get("content"),        # the normal place
                      message.get("reasoning_content"),   # some reasoning models
                      first.get("text")):            # older completion-style replies
        if isinstance(candidate, str) and candidate.strip():   # found real text
            return candidate.strip()                 # hand it back

    # Some providers return content as a LIST of parts rather than a string.
    content = message.get("content")                 # look again at the normal place
    if isinstance(content, list):                    # a list of pieces
        joined = " ".join(part.get("text", "")       # pull the text out of each piece
                          for part in content if isinstance(part, dict))
        if joined.strip():                           # did that produce anything?
            return joined.strip()                    # hand it back

    reason = first.get("finish_reason") or "unknown" # why did it stop?
    hint = {                                         # what to do about each reason
        "length": "the answer was cut off — raise max_tokens, or the model spent "
                  "its whole budget on reasoning. Try a non-reasoning model.",
        "content_filter": "the provider's safety filter blocked the reply.",
        "stop": "the model returned an empty answer.",
    }.get(reason, "no text was returned.")
    raise RuntimeError(f"{label}: no usable text (finish_reason={reason}) — {hint}")


def _post_chat(name: str, payload: dict) -> str:
    """Actually send the request over the internet and return the AI's text.

    Two ways to do this. The openai library is neater AND more reliable, so we
    try it first. The built-in urllib fallback exists so the template still
    works when pip install fails — but see the note on headers below.
    """
    p     = PROVIDERS[name]                          # this provider's settings
    label = p["label"]                               # the pretty name, for error messages
    key   = provider_key(name) or ("ollama" if not p["needs_key"] else "")   # key, or filler

    try:                                             # --- attempt 1: the openai library ---
        from openai import OpenAI                    # this one library talks to ALL five providers
        client = OpenAI(api_key=key,                 # give it the key
                        base_url=p["base_url"],      # point it at the right provider
                        timeout=60)                  # give up after 60 seconds
        resp = client.chat.completions.create(**payload)   # ** unpacks the dictionary
        # model_dump() turns the library's object back into a plain dictionary,
        # so ONE extractor handles both routes and they can never disagree.
        return _extract_text(resp.model_dump(), label)
    except ImportError:                              # the library is not installed
        pass                                         # no problem — use the built-in way below

    import urllib.request, urllib.error              # Python's built-in internet tools

    # These headers matter more than they look. Several providers sit behind
    # Cloudflare, which blocks clients it does not recognise — Groq answers
    # "403, error code: 1010", which means "banned based on your browser
    # signature". Naming ourselves properly usually gets us through. If it
    # still refuses, install the openai package; that is the real fix.
    headers = {"Content-Type": "application/json",   # we are sending JSON
               "Accept": "application/json",         # we would like JSON back
               "User-Agent": HARVEST_USER_AGENT,     # say who we are, don't be anonymous
               "Authorization": f"Bearer {key}"}     # this is how the key is presented

    req = urllib.request.Request(                    # build the request by hand
        p["base_url"].rstrip("/") + "/chat/completions",   # the full web address
        data=json.dumps(payload).encode(),           # our dictionary, as JSON bytes
        headers=headers)                             # the headers above

    try:                                             # attempt the request
        with urllib.request.urlopen(req, timeout=60) as r:   # send it, wait up to 60 seconds
            data = json.loads(r.read().decode())     # read the reply, JSON to dictionary
    except urllib.error.HTTPError as e:              # the server replied with an error code
        body = e.read().decode(errors="ignore")[:300]    # the first 300 characters of why
        extra = ""                                   # room for a plain-English hint
        if e.code == 403 and "1010" in body:         # Cloudflare's browser-signature ban
            extra = (" — Cloudflare blocked this request because it did not come from "
                     "a recognised client. Fix: pip install openai, which this file "
                     "will then use automatically.")
        elif e.code == 401:                          # the key is wrong
            extra = " — the API key was rejected. Check it with --providers."
        elif e.code == 404:                          # the model name is wrong
            extra = f" — check the model name. Set {p['model_env']} to override it."
        elif e.code == 429:                          # too many requests
            extra = " — rate limited or out of credit. Wait, or use another provider."
        raise RuntimeError(f"{label} HTTP {e.code}: {body}{extra}") from None
    except Exception as e:                           # network down, timeout, DNS failure
        raise RuntimeError(f"{label}: {type(e).__name__}: {e}") from None

    return _extract_text(data, label)                # one extractor, both routes


def chat_completion(name: str, system_prompt: str, user_msg: str,
                    temperature: float = 0.2, max_tokens: int = 900) -> str:
    """Ask one provider a question and get the answer back.

    temperature: 0 = predictable and repetitive, 1 = creative and surprising.
                 0.2 is right for a bot that must stick to documents.
    max_tokens:  roughly the maximum length of the answer. A token is about
                 three-quarters of a word. Reasoning models spend tokens
                 thinking before they write, so this is deliberately generous;
                 600 was too small for Gemini 3.x and it returned nothing.

    Some newer models reject temperature or max_tokens outright. So if the
    full request is refused, we quietly retry with the bare minimum. That
    retry is why this works with providers nobody has tested yet.
    """
    p = PROVIDERS[name]                              # this provider's settings
    if p["needs_key"] and not provider_key(name):    # needs a key but has not got one?
        raise RuntimeError(f"{p['label']}: no key in {p['key_env']}")   # stop with a clear message

    messages = [{"role": "system", "content": system_prompt},   # the rules the AI must follow
                {"role": "user",   "content": user_msg}]        # the actual question

    minimal = {"model": provider_model(name), "messages": messages}   # the bare minimum request
    full    = {**minimal,                            # everything in minimal, plus...
               "temperature": temperature,           # ...how creative to be
               "max_tokens": max_tokens}             # ...how long the answer can be

    try:                                             # try the full request first
        return _post_chat(name, full)                # send it
    except Exception as e:                           # something went wrong
        text = str(e).lower()                        # the error, lowercased for matching

        # Case 1: a reasoning model spent its whole budget thinking and
        # returned nothing. Gemini 3.x does this. Give it three times the
        # room and ask once more before giving up on this provider.
        if "finish_reason=length" in text:           # ran out of room
            roomier = {**full, "max_tokens": max_tokens * 3}   # a much bigger budget
            return _post_chat(name, roomier)         # one more go

        # Case 2: the provider objected to our extra settings. Some newer
        # models reject temperature or max_tokens outright, so retry bare.
        if any(w in text for w in
               ("max_tokens", "temperature", "unsupported", "400", "invalid_request")):
            return _post_chat(name, minimal)         # retry with no extras

        raise                                        # anything else: pass it up the chain


def test_provider(name: str) -> dict:
    """Send a tiny test message to prove a key works. The sidebar's Test button uses this."""
    try:                                             # attempt the smallest possible request
        out = chat_completion(name, "Reply with exactly: OK", "ping", max_tokens=10)
        return {"ok": True, "provider": name,        # it worked
                "model": provider_model(name), "reply": out}
    except Exception as e:                           # it failed
        return {"ok": False, "provider": name,       # report the failure and why
                "model": provider_model(name),
                "reply": f"{type(e).__name__}: {e}"}


# =====================================================================
# SECTION 7 · THE MASTER PROMPT (TCRDEI) — the instructions round every question
# =====================================================================
#   Week 1 taught TCRDEI as the anatomy of a professional prompt. Here it
#   is as actual code. Each letter is a labelled block below, so you can
#   see which part of the prompt you are editing and why.
#
#     T — Task           what the bot must do, in one line
#     C — Context        who it is for, and how they feel right now
#     R — Reference      the retrieved excerpts, and nothing else
#     D — Defined Success what a good answer looks like
#     E — Excellent Check what to do when it cannot answer
#     I — Iterate        the note that this prompt is meant to be rewritten
#
#   NOTE FOR FACILITATORS: the Week 1 pack and the Week 2 pack spell
#   TCRDEI differently. This file follows the Week 1 version. See the
#   README before you teach it.
#
#   Almost every bad answer your bot gives is fixable in this one string.
#   Change it, run the eval, see the number move. That loop is the job.
# =====================================================================

MASTER_PROMPT = """T — TASK
You are {bot_name}, an assistant for {client}. Answer the customer's question
about the cost of running an appliance, using only the excerpts provided.

C — CONTEXT
You are speaking to: {persona}.
Right now they feel: {feeling}.
Their customer category is {segment}, and their local desk is {desk}.
Speak in a {register} register.

R — REFERENCE
Use ONLY the numbered excerpts below. They are the client's own documents.
You have no other knowledge about {client}. If something is not in the
excerpts, you do not know it.

{context}

D — DEFINED SUCCESS
A good answer is: short, plain English, no jargon, in Eastern Caribbean
dollars (EC$), and it cites the excerpt it used like [1] at the end of the
sentence that excerpt supports. Under 90 words.

E — EXCELLENT CHECK
Before answering, check every one of these:
{red_lines}
If the answer is not in the excerpts, reply exactly: "That isn't in my LUCELEC
documents." and point them to {desk}. Never state a rate, tariff or fee that
does not appear above. A tagged value ("{confirm_tag}") is NOT confirmed —
treat it as unknown and say so.

I — ITERATE
This prompt is a draft. When the bot gives a poor answer, fix it here first,
then run the eval set again and compare the score.
"""


def build_prompt(question: str, hits: list, register: str = DEFAULT_REGISTER,
                 territory: Optional[dict] = None) -> str:
    """Fill in every blank in MASTER_PROMPT with this Pod's blueprint and the found chunks."""
    return MASTER_PROMPT.format(                     # .format() replaces each {blank}
        bot_name=BOT_NAME,                           # T — fills {bot_name}
        client=CLIENT,                               # T and R — fills {client}
        persona=PERSONA["who"],                      # C — from the Day 1 persona
        feeling=EMPATHY_MAP["feels"],                # C — from the Day 1 empathy map
        segment=(territory or {}).get("notes", "unknown"),      # C — the segment's description
        desk=(territory or {}).get("desk", ESCALATION_LINE),    # C and E — where to escalate
        register=register,                           # C — which voice to use
        context=format_context(hits) or "(no excerpts retrieved)",   # R — the numbered chunks
        red_lines="\n".join(f"- {r}" for r in MUST_NEVER_DO),  # E — the Red Line, as bullets
        confirm_tag=CONFIRM_TAG,                     # E — the unconfirmed-value sticker
    )


def llm_call(system_prompt: str, user_msg: str) -> str:
    """Try each configured provider in turn. The first one that answers wins."""
    errors = []                                      # collect failure messages as we go
    for name in active_chain():                      # walk the provider list in order
        if not is_configured(name):                  # no key, or server not running?
            continue                                 # skip this one, try the next
        try:                                         # attempt the call
            text = chat_completion(name, system_prompt, user_msg)   # ask this provider
            LAST_CALL.update({"provider": PROVIDERS[name]["label"], # remember who answered
                              "model": provider_model(name),        # and with which model
                              "error": None})                       # no error this time
            return text                              # success — hand the answer back
        except Exception as e:                       # this provider failed
            errors.append(f"{name}: {type(e).__name__} {e}")   # write down why
            continue                                 # try the next provider

    LAST_CALL.update({"provider": None, "model": None,            # nobody answered
                      "error": "; ".join(errors) or "no provider configured"})
    raise RuntimeError(LAST_CALL["error"])           # give up; safe_call catches this


def extractive_answer(question: str, hits: list) -> str:
    """The emergency answer used when NO provider works.

    It just picks the sentences from the found chunks that share the most
    words with the question. It reads clumsily. That is deliberate: it is
    the baseline a real AI model has to beat, and it means a dead API key
    embarrasses you slightly instead of ending your demo.
    """
    if not hits:                                     # nothing was retrieved at all
        return "That isn't in my LUCELEC documents."

    q_terms = set(tokenize(question))                # the question's words, duplicates removed
    scored = []                                      # will hold (overlap, chunk number, sentence)

    for i, h in enumerate(hits, 1):                  # go through each retrieved chunk
        for sent in re.split(r"(?<=[.?!])\s+", h["text"]):   # split the chunk into sentences
            sent = sent.strip()                      # tidy up spaces
            if sent.startswith("#") or sent.endswith("?"):
                continue                             # skip headings and the FAQ's own questions
            if "TODO_" in sent or needs_confirmation(sent):
                continue                             # NEVER speak an unconfirmed value out loud
            overlap = len(q_terms & set(tokenize(sent)))    # "&" = words in BOTH question and sentence
            if overlap and len(sent.split()) > 3:    # some overlap, and not a stub of a sentence
                scored.append((overlap, i, sent))    # keep it as a candidate

    scored.sort(key=lambda x: x[0], reverse=True)    # best overlap first
    if not scored:                                   # nothing matched well enough
        return "That isn't in my LUCELEC documents."

    lines = [f"{s} [{i}]" for _, i, s in scored[:3]] # take the top three, tag each with its chunk
    return "\n\n".join(lines) + "\n\n_(Offline mode — no AI provider configured, so this is the retrieved text as-is.)_"


def safe_call(fn, *args, fallback: str = "") -> str:
    """Run a function, and if it crashes, return the fallback instead of stopping.

    fn is a function passed in as a value. *args is however many arguments
    it needs. This one small function is why the app never shows a red
    error screen in front of the client.
    """
    try:                                             # attempt the risky thing
        return fn(*args)                             # call the function with its arguments
    except Exception as e:                           # it failed, whatever the reason
        print(f"[safe_call] {type(e).__name__}: {e}")   # log it for you, not for the customer
        return fallback                              # hand back the safe alternative



# ---------------------------------------------------------------------
# 7.5 · THE CONVERSATION LANE — being sociable without inventing facts
# ---------------------------------------------------------------------
#   A person who types "hi" has not asked a question about electricity.
#   Answering "That isn't in my LUCELEC documents" is technically correct
#   and completely useless. Worse, it teaches the person that the bot is
#   a search box, so they stop talking to it like a person.
#
#   So the bot has two lanes:
#
#     SOCIAL lane  — greetings, thanks, goodbyes, "what can you do?".
#                    The AI writes these freely, BUT it is forbidden to
#                    state any fact, rate, number or policy. It can be
#                    friendly. It cannot be a source.
#
#     DOMAIN lane  — anything about electricity, bills, appliances.
#                    Full A.R.T., full retrieval, citations, the lot.
#
#   The rule that keeps this honest: warmth is free, facts are not.
#   Nothing in the social lane may ever answer a question about LUCELEC.
# ---------------------------------------------------------------------

# Phrases that mean "this is small talk, not a question about electricity".
#   ORDER MATTERS. The first matching entry wins, so the specific intents
#   ("who are you") are listed before the general one ("hi"), otherwise a
#   message containing both would always be treated as a plain greeting.
SOCIAL_SIGNALS = {                                   # intent name -> the words that suggest it
    "identity":  ["who are you", "what are you", "your name", "are you a robot",
                  "are you human", "are you real", "are you a person"],
    "capability": ["what can you do", "what do you do", "how can you help",
                   "what can you help", "can you help", "what is this"],
    "howareyou": ["how are you", "how you doing", "how's it going", "you good",
                  "how are things"],
    "greeting":  ["hi", "hello", "hey", "good morning", "good afternoon",
                  "good evening", "good day", "greetings", "yow", "hola"],
    "thanks":    ["thank", "thanks", "appreciate it", "much obliged", "bless"],
    "farewell":  ["bye", "goodbye", "see you", "later", "take care", "good night"],
    "chitchat":  ["ok", "okay", "cool", "nice", "great", "alright", "sure",
                  "no problem", "sorry", "oops", "lol", "haha"],
}


def _phrase_in(phrase: str, text: str) -> bool:
    """Does this phrase appear as a WHOLE word (or whole phrase) in the text?

    Written after a real bug: the greeting "yo" was matching inside the word
    "you", so "who are you" got answered with "Hello!". Plain `in` finds
    letters anywhere; this finds words. \b means "edge of a word".
    """
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def classify_intent(message: str) -> str:
    """Decide which lane a message belongs in: "social" or "domain".

    This runs BEFORE the A.R.T. checks, and that is deliberate. You do not
    need to know somebody's customer category before you can say hello back.
    A.R.T. guards ANSWERS about the client's business, not basic manners.
    """
    low = message.lower().strip()                    # tidy it up for matching
    words = low.split()                              # split into words to measure length

    # Any electricity word at all means this is a real question, even if it
    # also says hello. "Hi, how much does an AC cost?" is a domain question.
    domain_words = ["kwh", "bill", "tariff", "rate", "cost", "appliance", "fridge",
                    "electricity", "power", "meter", "watt", "energy", "ac",
                    "air condition", "heater", "solar", "charge", "pay", "unit",
                    "expensive", "cheap", "save", "much"]
    if any(_phrase_in(w, low) for w in domain_words):   # anything domain-ish present?
        return "domain"                              # treat it as a real question

    # Very long messages are almost never small talk.
    if len(words) > 12:                              # more than a dozen words
        return "domain"                              # send it down the serious lane

    for intent, phrases in SOCIAL_SIGNALS.items():   # check each social intent
        if any(_phrase_in(p, low) for p in phrases): # any of its phrases present?
            return "social"                          # this is small talk

    if len(words) <= 2 and "?" not in low:           # a two-word fragment with no question mark
        return "social"                              # e.g. "morning", "ok then"

    return "domain"                                  # when unsure, treat it seriously


# The instructions for the social lane. Notice what is missing: any document.
# The AI is being asked to be a person, not a source.
SOCIAL_PROMPT = """You are {bot_name}, the assistant for {client}.
You are talking to {persona_name}, who {persona_who}.

Right now the person is making small talk — a greeting, a thank you, a goodbye,
or asking what you are. Reply like a friendly human being would.

HARD RULES, no exceptions:
- Do NOT state any rate, tariff, price, number, policy or fact about {client}.
  You have no documents in front of you right now. If they ask for one, say you
  will look it up, and invite them to ask the question properly.
- Do NOT invent a personal history. You are software and you say so if asked.
- Do NOT ask for their account number, meter number, or any personal details.
- Keep it to one or two short sentences. This is a doorway, not a speech.
- Where it fits naturally, mention one thing you CAN do: work out what an
  appliance costs to run, or explain something on their bill in plain words.

Speak in plain Saint Lucian English. Warm, unhurried, never salesy."""


# Used when no AI provider is configured, so the bot is still pleasant offline.
SOCIAL_FALLBACKS = {                                 # intent -> a sensible fixed reply
    "greeting":   "Hello! I can help you work out what an appliance costs to run, "
                  "or explain something on your bill. What would you like to know?",
    "thanks":     "You're very welcome. Anything else you'd like to work out?",
    "farewell":   "Take care. Come back any time you need to check a running cost.",
    "howareyou":  "I'm well, thank you for asking. What can I help you with today?",
    "identity":   "I'm {bot_name}, a computer assistant built for {client} — "
                  "not a person. I can help you compare what appliances cost to run.",
    "capability": "I can work out what an appliance costs to run per month or per "
                  "year, compare two appliances before you buy, and explain the "
                  "words on your bill in plain language.",
    "chitchat":   "Understood. Is there an appliance or a bill question I can help with?",
}


def social_intent_kind(message: str) -> str:
    """Which KIND of small talk is this? Used to pick the offline reply."""
    low = message.lower()                            # lowercase for matching
    for intent, phrases in SOCIAL_SIGNALS.items():   # check each kind in turn
        if any(_phrase_in(p, low) for p in phrases): # found a matching phrase?
            return intent                            # that is the kind
    return "chitchat"                                # a safe general-purpose reply


def social_reply(message: str, register: str) -> dict:
    """Answer small talk. The AI writes it if we have a key; otherwise a fixed line.

    Either way the reply is dressed in the right register, so a worried
    customer gets a gentler hello than a builder in a hurry.
    """
    kind = social_intent_kind(message)               # greeting? thanks? identity?

    system = SOCIAL_PROMPT.format(                   # fill in the blanks
        bot_name=BOT_NAME,                           # who the bot is
        client=CLIENT,                               # who it works for
        persona_name=PERSONA.get("name", "a customer"),          # who it is talking to
        persona_who=PERSONA.get("who", "is a LUCELEC customer"), # their situation
    )

    fallback = SOCIAL_FALLBACKS.get(kind, SOCIAL_FALLBACKS["chitchat"])   # the offline line
    fallback = fallback.format(bot_name=BOT_NAME, client=CLIENT)          # fill its blanks too

    reply = safe_call(llm_call, system, message, fallback=fallback)   # AI if possible, else fixed

    return {"reply": dress(register, reply),         # put the register's outfit on it
            "kind": kind,                            # which sort of small talk it was
            "provider": LAST_CALL["provider"] or "offline (fixed reply)",
            "model": LAST_CALL["model"] or "-"}


# =====================================================================
# SECTION 8 · THE TOOL — the appliance cost calculator
# =====================================================================
#   An AI model is bad at arithmetic and good at words. So we do the maths
#   in Python, where it is always right, and let the AI do the explaining.
#   This split is the single most useful pattern in this whole file.
# =====================================================================

# TODO_students: replace with the rate the client confirms, then log it in
# the Confirmation Register with their initials and the date.
DEFAULT_RATE_PER_KWH = 1.00                          # EC$ per kWh — A PLACEHOLDER, NOT A REAL RATE


def appliance_cost(watts: float, hours_per_day: float,
                   rate_per_kwh: float = DEFAULT_RATE_PER_KWH) -> dict:
    """Work out what one appliance costs to run per day, month and year.

    The whole calculation is one idea: watts / 1000 = kilowatts, kilowatts
    x hours = kilowatt-hours (kWh), kWh x rate = money.
    """
    kwh_day = (watts / 1000.0) * hours_per_day       # convert watts to kW, then multiply by hours
    return {                                         # hand back every number, ready to display
        "watts":         watts,                      # what was put in
        "hours_per_day": hours_per_day,              # what was put in
        "rate_per_kwh":  rate_per_kwh,               # what was put in
        "kwh_day":       round(kwh_day, 3),          # units used per day, 3 decimal places
        "kwh_month":     round(kwh_day * 30, 2),     # per month, treating a month as 30 days
        "kwh_year":      round(kwh_day * 365, 2),    # per year
        "cost_day":      round(kwh_day * rate_per_kwh, 2),          # money per day
        "cost_month":    round(kwh_day * 30 * rate_per_kwh, 2),     # money per month
        "cost_year":     round(kwh_day * 365 * rate_per_kwh, 2),    # money per year
    }


def compare_appliances(a: dict, b: dict, rate: float = DEFAULT_RATE_PER_KWH) -> dict:
    """Compare two appliances and work out how long the pricier one takes to pay for itself.

    a and b each look like:
        {"name": "Old fridge", "watts": 350, "hours_per_day": 8, "price": 1500}
    """
    ca = appliance_cost(a["watts"], a["hours_per_day"], rate)   # running cost of appliance A
    cb = appliance_cost(b["watts"], b["hours_per_day"], rate)   # running cost of appliance B

    yearly_gap = ca["cost_year"] - cb["cost_year"]   # how much more A costs to run each year
    price_gap  = (b.get("price", 0) or 0) - (a.get("price", 0) or 0)   # how much more B costs to buy

    # Payback: extra purchase price divided by yearly saving. Only meaningful
    # if B is actually cheaper to run, so we check before dividing.
    payback_years = (price_gap / yearly_gap) if yearly_gap > 0 else None

    return {                                         # everything the app needs to show a verdict
        a["name"]: ca,                               # full breakdown for A
        b["name"]: cb,                               # full breakdown for B
        "cheaper_to_run": b["name"] if yearly_gap > 0 else a["name"],   # which one wins
        "yearly_saving": round(abs(yearly_gap), 2),  # abs() = ignore the minus sign
        "payback_years": round(payback_years, 1) if payback_years else None,
    }


def decide_action(question: str) -> dict:
    """Guess whether a question needs the calculator or needs the documents.

    TODO_students (Build 2): nothing calls this yet. Wire it into answer()
    so that cost questions run the calculator instead of only retrieving text.
    """
    if re.search(r"\b(how much|cost|per month|monthly|yearly|compare|cheaper)\b", question.lower()):
        return {"action": "CALC", "reason": "question asks for a number"}   # do the maths
    return {"action": "RETRIEVE", "reason": "question asks for an explanation"}   # search the docs


# =====================================================================
# SECTION 9 · THE PIPELINE — A.R.T. first, then the AI
# =====================================================================
#   Everything above is a part. This is the assembly line.
#
#     message
#       -> Red Line check          (Section 3 — refuse outright?)
#       -> A.R.T. three axes       (Section 2 — allowed? mood? rules?)
#           any axis fails -> ESCALATE. Stop. No AI call.
#       -> hide personal info      (Section 3)
#       -> retrieve the best chunks (Section 5)
#       -> build the TCRDEI prompt (Section 7)
#       -> ask the AI              (Section 6)
#       -> translate jargon        (Section 2.4)
#       -> dress in the register   (Section 2.3)
#
#   The AI sits BEHIND the classifier, never in front of it. By the time
#   the model is called, we have already decided we are allowed to answer.
# =====================================================================

def rag_answer(question: str, index: dict, register: str = DEFAULT_REGISTER,
               territory: Optional[dict] = None) -> dict:
    """The retrieval half: find chunks, ground the prompt, get an answer.

    This assumes A.R.T. has already passed. classify_and_route() below is
    what enforces that, and it is the function you should call.
    """
    safe_q = redact(question)                        # strip out personal information first
    hits   = retrieve_chunks(safe_q, index)          # find the best matching chunks

    if not hits:                                     # nothing in the documents matched
        return {"reply": "That isn't in my LUCELEC documents.",   # say so honestly
                "hits": [], "provider": "no-match", "model": "-"}

    system = build_prompt(safe_q, hits, register, territory)   # the TCRDEI master prompt
    reply  = safe_call(llm_call, system, safe_q,     # ask the AI, safely
                       fallback=extractive_answer(safe_q, hits))   # plan B if all providers fail

    return {"reply": reply,                          # the raw answer, before the wardrobe
            "hits": hits,                            # the chunks it was based on
            "provider": LAST_CALL["provider"] or "offline (extractive)",   # who answered
            "model":    LAST_CALL["model"] or "-"}   # and with which model


def classify_and_route(user: dict, message: str, index: dict) -> dict:
    """THE MAIN FUNCTION. The VIP bouncer, now with a library behind it.

    user looks like: {"id_verified": True, "mood": "warm", "segment": "Domestic"}

    Returns a dictionary so the app can show the answer, the sources, and
    which axis stopped it if it was stopped.
    """
    # ---- STEP 1: the Red Line. Some questions we refuse before anything else.
    refusal = check_red_line(message)                # Section 3 — unsafe or account-specific?
    if refusal:                                      # a rule was broken
        return {"reply": refusal, "hits": [], "escalated": True,   # refuse and stop
                "axis": "red-line", "register": DEFAULT_REGISTER,
                "provider": "guardrail", "model": "-"}

    # ---- STEP 2: which lane? Small talk does not need a customer category.
    #      Register is worked out first either way, because even "hello"
    #      should be said in the right voice.
    r = check_register(user, message)                # Axis 2 — how does this person feel?
    intent = classify_intent(message)                # "social" or "domain"

    if intent == "social":                           # a greeting, a thank you, a goodbye
        chat = social_reply(message, r or DEFAULT_REGISTER)   # be a person about it
        return {"reply": chat["reply"], "hits": [],  # no sources, because no facts were stated
                "escalated": False, "axis": "social", "intent": "social",
                "register": r or DEFAULT_REGISTER,
                "provider": chat["provider"], "model": chat["model"]}

    # ---- STEP 2b: a real question about the client's business. Full A.R.T.
    a = check_authority(user, message)               # Axis 1 — am I allowed to answer?
    t = check_territory(user)                        # Axis 3 — which rules apply to them?

    if not a:                                        # authority failed — but WHY?
        # Two different failures deserve two different sentences. Telling an
        # unverified person their question was "about your account" is simply
        # untrue, and a client will notice.
        why = "authority" if user.get("id_verified") else "authority_unverified"
        return {"reply": escalate_message(why, user), "hits": [],
                "escalated": True, "axis": why, "intent": "domain",
                "register": r or DEFAULT_REGISTER,
                "provider": "A.R.T.", "model": "-"}
    if not r:                                        # register failed
        return {"reply": escalate_message("register", user), "hits": [],
                "escalated": True, "axis": "register", "intent": "domain",
                "register": DEFAULT_REGISTER,
                "provider": "A.R.T.", "model": "-"}
    if not t:                                        # territory failed
        return {"reply": escalate_message("territory", user), "hits": [],
                "escalated": True, "axis": "territory", "intent": "domain",
                "register": r,
                "provider": "A.R.T.", "model": "-"}

    # ---- STEP 3: all three axes passed, so now we may use the documents and the AI.
    out = rag_answer(message, index, register=r, territory=t)     # do the RAG work

    # ---- STEP 4: dress the answer. Plain English first, then the right voice.
    plain   = translate(out["reply"])                # swap any jargon the AI used back to plain
    dressed = dress(r, plain)                        # put the right register's outfit on it

    return {"reply": dressed,                        # the finished, dressed answer
            "intent": "domain",                      # which lane produced this
            "hits": out["hits"],                     # the chunks behind it
            "escalated": False,                      # nothing was escalated
            "axis": "passed",                        # all three axes passed
            "register": r,                           # which voice was used
            "territory": t,                          # which rulebook applied
            "provider": out["provider"],             # who answered
            "model": out["model"]}                   # with which model


def answer(question: str, index: dict, user: Optional[dict] = None) -> dict:
    """A shortcut for testing: assumes a verified Domestic customer.

    Real calls should go through classify_and_route() with a real user.
    This exists so the eval set and the CLI stay short and readable.
    """
    user = user or {"id_verified": True,             # pretend they are verified
                    "mood": DEFAULT_REGISTER,        # use the default voice
                    "segment": "Domestic"}           # and the most common segment
    return classify_and_route(user, question, index) # hand off to the real function


# =====================================================================
# SECTION 10 · THE EVAL SET — how you prove the bot is getting better
# =====================================================================
#   "It seems better" is not evidence. A fixed list of questions with
#   expected answers is. Run it before and after every change you make.
# =====================================================================

EVAL_SET = [                                         # each entry is one test
    # --- questions the bot SHOULD answer from the documents ---
    {"q": "What appliance uses the most electricity?", "must_mention": ["water heater", "air condition"]},
    {"q": "How do I read an energy label?",            "must_mention": ["watt", "kilowatt", "units"]},
    {"q": "Does standby power cost me anything?",      "must_mention": ["standby"]},

    # --- questions the bot MUST refuse or escalate (Authority axis) ---
    {"q": "What is my account balance?",               "must_mention": ["can't", "contact", "person"]},
    {"q": "Am I eligible for a payment plan?",          "must_mention": ["person", "contact", "can't"]},

    # --- a question the documents cannot answer honestly ---
    {"q": "What is the exact tariff per unit today?",  "must_mention": ["isn't in my", "contact"]},

    # --- small talk: the bot must be a person here, NOT a search box ---
    #     If either of these starts saying "That isn't in my LUCELEC documents",
    #     somebody has broken the social lane. That is what these two catch.
    {"q": "hi",                                        "must_mention": ["help", "hello", "welcome"]},
    {"q": "who are you",                               "must_mention": ["assistant", "computer", "software", "built for"]},

    # TODO_students: add 4 more, including one for each register in your wardrobe.
]                                                    # eval set ends here


def run_eval(index: dict, user: Optional[dict] = None) -> list:
    """Ask every test question and check whether the required words appear.

    Pass a different user to test the same questions from another segment
    or register — the answer should change voice but never change facts.
    """
    rows = []                                        # one result row per test
    for case in EVAL_SET:                            # go through each test
        out = answer(case["q"], index, user)         # run the real pipeline, no shortcuts
        low = out["reply"].lower()                   # lowercase so matching is not fussy
        hit = any(m.lower() in low for m in case["must_mention"])   # any required word present?
        rows.append({                                # record what happened
            "question":  case["q"],                  # the question asked
            "passed":    hit,                        # True or False
            "axis":      out.get("axis", "-"),       # which A.R.T. axis stopped it, if any
            "escalated": out.get("escalated", False),    # did it hand off to a human?
            "sources":   ", ".join(sorted({h["source"] for h in out["hits"]})) or "-",
            "reply":     out["reply"][:110] + ("…" if len(out["reply"]) > 110 else ""),
        })
    return rows                                      # hand back the whole table


# =====================================================================
# SECTION 11 · THE WEB APP — everything you see in the browser
# =====================================================================
#   Streamlit turns Python into a website. Every st.something() call adds
#   one visible thing to the page. Streamlit re-runs this entire function
#   from the top every time you click anything — that is normal, and it is
#   why anything that must survive a click lives in st.session_state.
# =====================================================================

# =====================================================================
# SECTION 11 · THE WEB APP — everything you see in the browser
# =====================================================================
#   Streamlit turns Python into a website. Every st.something() call adds
#   one visible thing to the page. Streamlit re-runs this entire function
#   from the top every time you click anything — that is normal, and it is
#   why anything that must survive a click lives in st.session_state.
# =====================================================================

def streamlit_app(): # Defines the main function that runs the Streamlit web application
    import streamlit as st # Imports the Streamlit library and aliases it as 'st'
    import base64

    # --- NEW: APPLY CUSTOM BACKGROUND DESIGN ---
    # Cache the function so the image isn't reloaded from the hard drive on every interaction
    @st.cache_data
    def get_base64_of_bin_file(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode() # Encodes the image to base64 format

    # Attempt to load the specific uploaded image
    try:
        img_base64 = get_base64_of_bin_file('files/Lucelec_bot_design.png')
        
        # Inject custom CSS to set the background and adjust padding
        page_bg_img = f'''
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{img_base64}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        
        /* Force the main content block down completely below the custom banner */
        .block-container {{
            padding-top: 15rem !important; 
            padding-bottom: 7rem !important;
        }}
        
        /* Add a subtle semi-transparent background to the tabs so they are readable */
        [data-testid="stTabs"] button {{
            background-color: rgba(255, 255, 255, 0.6);
            border-radius: 5px 5px 0px 0px;
            margin-right: 2px;
        }}
        
        /* Highlight the active tab */
        [data-testid="stTabs"] button[aria-selected="true"] {{
            background-color: rgba(255, 255, 255, 1);
            font-weight: bold;
        }}
        </style>
        '''
        st.markdown(page_bg_img, unsafe_allow_html=True) # Applies the CSS to the app
    except FileNotFoundError:
        st.warning("Design image 'Lucelec_bot_design.png' not found. Please ensure it is saved in the same directory as this script.")
    # -------------------------------------------
    st.set_page_config(page_title=f"{BOT_NAME} · LUCELEC", # Sets the title of the browser tab using the bot's name
                       page_icon="⚡", layout="wide") # Sets the favicon to a lightning bolt and makes the page layout wide
    
    # --- ROUTING STATE INITIALIZATION ---
    if 'page_state' not in st.session_state: # Checks if 'page_state' exists in the current session memory
        st.session_state.page_state = 'homepage' # If not, initializes the starting page state to 'homepage'

    def set_state(new_state): # Defines a helper function to change the current page state
        st.session_state.page_state = new_state # Updates the session state variable to the new specified state

    # --- VIEW: HOMEPAGE ---
    if st.session_state.page_state == 'homepage': # Checks if the user is currently on the homepage view
        st.title(f"⚡ {BOT_NAME} — LUCELEC Assistant") # Displays the main title of the homepage
        st.write("Welcome. Please select your role to continue:") # Displays a welcome message and instructions
        col1, col2 = st.columns(2) # Splits the layout into two equal vertical columns
        with col1: # Opens the context for the first (left) column
            st.button("I am a Customer", on_click=set_state, args=('customer_view',)) # Creates a button that routes to the customer view when clicked
        with col2: # Opens the context for the second (right) column
            st.button("I am an Administrator", on_click=set_state, args=('admin_login',)) # Creates a button that routes to the admin login view when clicked
        return  # Exits the function early so none of the chat/admin code runs while on the homepage

    # --- VIEW: ADMIN LOGIN ---
    if st.session_state.page_state == 'admin_login': # Checks if the user is currently on the admin login view
        st.title("Administrator Login") # Displays the title for the login page
        username = st.text_input("Username") # Creates a text input box for the username
        password = st.text_input("Password", type="password") # Creates a masked text input box for the password
        
        col1, col2 = st.columns([1, 5]) # Splits the layout into two columns with a 1-to-5 width ratio
        with col1:
            if st.button("Login"):
                # Pull credentials from the environment, defaulting to admin/secret if missing
                expected_user = os.getenv("ADMIN_USERNAME", "admin")
                expected_pass = os.getenv("ADMIN_PASSWORD", "secret")
                
                if username == expected_user and password == expected_pass:
                    set_state('admin_view')
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        with col2: # Opens the context for the second (wider) column
            st.button("Back to Home", on_click=set_state, args=('homepage',)) # Creates a back button that routes the user to the homepage
        return  # Exits the function early so the main portal code doesn't run during login

    # --- MAIN APPLICATION PORTAL (Customer & Admin) ---
    is_admin = (st.session_state.page_state == 'admin_view') # Creates a boolean flag that is True if the user is in the admin view, False otherwise

    #st.title(f"⚡ {BOT_NAME} — LUCELEC Appliance Cost Assistant")   # Displays the main application title
    #st.caption(f"Pod: {POD} · Client: {CLIENT} · "             # Displays small grey subtitle text with pod and client info
    #           "Answers come only from source_documents/") # Appends a disclaimer to the caption

    @st.cache_resource                               # Decorator telling Streamlit to cache the result of the following function so it doesn't run on every click
    def get_index():                                 # Defines a function to build the document search index
        return build_index(load_chunks())            # Reads all documents, chunks them, scores word rarities, and returns the finished index

    index = get_index()                              # Calls the function to load the index (it will use the cached version if already built)

    # ---------- SIDEBAR ----------
    with st.sidebar:                                 # Opens the context for the collapsible sidebar menu on the left
        if is_admin: # Checks if the current user has administrator privileges
            # ADMIN ONLY: Settings, keys, documents
            st.subheader("AI model")                     # Displays a sub-heading for AI settings in the sidebar

            names  = [p["name"] for p in provider_status()]   # Builds a list of the short names of all available AI providers
            labels = {p["name"]: f"{p['label']} {'✅' if p['ready'] else '⚪'}"   # Creates a dictionary mapping short names to readable labels with a status icon
                      for p in provider_status()}        # Iterates through the provider status list to build the dictionary

            current = os.getenv("LLM_PROVIDER", "")      # Reads the currently selected provider from the environment variables (empty string if none)
            choice = st.selectbox("Provider", names,     # Creates a dropdown menu for selecting the AI provider
                                  format_func=lambda n: labels[n],   # Tells the dropdown to show the pretty labels instead of the raw short names
                                  index=names.index(current) if current in names else 0) # Sets the default dropdown selection to the currently active provider
            os.environ["LLM_PROVIDER"] = choice          # Saves the user's dropdown choice into the environment variables
            cfg = PROVIDERS[choice]                      # Retrieves the configuration dictionary for the chosen provider

            model_in = st.text_input("Model", value=provider_model(choice),   # Creates a text box to let the admin manually override the AI model name
                                     help="Model IDs change. Check the provider's docs on a 404.") # Adds a tooltip explaining why they might need to change this
            os.environ[cfg["model_env"]] = model_in.strip()   # Saves the entered model name into the specific environment variable for that provider, removing extra spaces

            try:                                         # Starts a block to test if a specific Python package is installed
                import openai                            # Attempts to import the official OpenAI python package
                sdk_ok = True                            # If successful, sets the flag to True
            except ImportError:                          # Catches the error if the package is not installed
                sdk_ok = False                           # Sets the flag to False
            if not sdk_ok:                               # Checks if the OpenAI package is missing
                st.warning("The `openai` package is missing, so requests go out through " # Displays a yellow warning box
                           "Python's built-in fetcher. Some providers sit behind " # Explains the technical fallback
                           "Cloudflare and refuse that. Run `pip install openai`.") # Provides instructions on how to fix it

            if st.button("Test connection"):             # Creates a button to test the AI API connection
                r = test_provider(choice)                # Runs a tiny ping to the chosen provider if clicked
                (st.success if r["ok"] else st.error)(f"{r['model']} → {r['reply']}")   # Displays a green success box if it worked, or a red error box if it failed

            st.caption("Fallback order: " + " → ".join(  # Displays small text showing the sequence providers will be tried in if one fails
                PROVIDERS[n]["label"] for n in active_chain()) + " → offline") # Dynamically builds the chain order text

            with st.expander("🔑 API keys"):             # Creates a collapsible section in the sidebar for managing passwords/keys
                st.caption("Keys are saved to `.streamlit/secrets.toml` on the server. " # Explains where the keys go
                           "They are never shown in full and never go in your code.") # Assures the admin about security

                for row in key_report():                 # Loops through the status report for every known key
                    if row["set"]:                       # Checks if the current key has a value saved
                        st.write(f"✅ `{row['name']}` — {row['masked']} · from {row['source']}") # Prints a green tick, the masked key, and where it loaded from
                    else:                                # If the key is empty
                        st.write(f"⚪ `{row['name']}` — not set") # Prints an empty circle indicating it is missing

                st.divider()                             # Draws a horizontal line to separate sections

                target = st.selectbox("Add or replace a key", KEY_NAMES, # Creates a dropdown to choose which API key to update
                                      index=KEY_NAMES.index(cfg["key_env"])   # Defaults the selection to the key needed by the currently active AI provider
                                      if cfg["key_env"] in KEY_NAMES else 0) # Fallback to the first item if the active provider doesn't use a standard key

                new_key = st.text_input("Paste the key", type="password",     # Creates a text box for pasting the new key, hiding characters with asterisks
                                        help=f"Get one at {cfg['get_key']}") # Adds a tooltip with the URL to get the specific key

                col_save, col_del = st.columns(2)        # Splits this part of the sidebar into two side-by-side columns
                with col_save:                           # Opens context for the left column
                    if st.button("Save to server"):      # Creates a save button and checks if clicked
                        if new_key.strip():              # Checks if the user actually pasted something (not just blank spaces)
                            path = save_key(target, new_key)          # Writes the new key to the server's secrets file
                            st.success(f"Saved to {path}")            # Shows a temporary green success message
                            st.rerun()                                # Instantly reloads the page to apply the new key
                        else:                            # If the input box was empty when save was clicked
                            st.warning("Nothing to save — the box is empty.") # Shows a yellow warning message
                with col_del:                            # Opens context for the right column
                    if st.button("Delete"):              # Creates a delete button and checks if clicked
                        delete_key(target)               # Removes the selected key from the server's file and memory
                        st.info(f"{target} removed.")    # Shows a blue info message confirming deletion
                        st.rerun()                       # Instantly reloads the page to reflect the deleted key

                st.caption("⚠️ Anyone who can open this Deepnote project can read that file. " # Adds a security warning in small text
                           "Use the camp-managed key, never a personal one, and never share " # Best practices instruction
                           "a duplicated project that still has a key inside it.") # Best practices instruction

            st.divider()                                 # Draws a horizontal line
            st.subheader("Knowledge base")               # Adds a sub-heading for document management
            st.metric("Chunks indexed", len(index["chunks"]))   # Displays a large callout metric showing how many document pieces were processed

            st.write("Documents:")                       # Adds a label for the list of files
            for s in sorted({c["source"] for c in index["chunks"]}):   # Extracts a unique list of filenames from the chunks and sorts them alphabetically
                st.write(f"· {s}")                       # Prints each filename as a bullet point

            if st.button("Reload documents"):            # Creates a button to force a refresh of the knowledge base
                st.cache_resource.clear()                # Clears the cached index from memory
                st.rerun()                               # Reloads the script, which will trigger get_index() to run from scratch

            st.divider()                                 # Draws a horizontal line

        # SHARED: A.R.T Settings and Red Line (Visible to both Customer and Admin)
        st.subheader("The user in front of you")     # Adds a sub-heading for user simulation variables
        
        # --- NEW NAME INPUT ---
        # 1. Ask for the user's name
        c_name = st.text_input("Customer Name", placeholder="e.g. Vaughnroy", help="If left blank, it auto-fills to a generic customer.")
        
        # 2. Auto-fill and dynamically update the bot's brain
        if c_name.strip(): # If the user typed a name
            PERSONA["name"] = c_name.strip() # Update the persona name
            PERSONA["who"] = f"a customer named {c_name.strip()}" # Tell the AI exactly who they are
        else: # If they didn't fill it out (auto-fill defaults)
            PERSONA["name"] = "a customer" 
            PERSONA["who"] = "a LUCELEC customer"
        # ----------------------

        st.caption("These three answers ARE the A.R.T. axes. Change them and " # Explains what the dropdowns do
                   "watch the bot's voice and its escalation behaviour change.") # Explains what the dropdowns do

        sim_verified = st.checkbox("Authority — identity verified", value=True, # Creates a checkbox to toggle user verification status, defaulted to True
                                   help="Untick this and every question escalates. That is correct.") # Tooltip explaining the behavior of Axis 1

        sim_mood = st.selectbox("Register — how do they feel?",            # Creates a dropdown to force the bot's tone (Axis 2)
                                ["(read it from the message)"] + list(TONES.keys()), # Provides automatic inference plus all hardcoded tones from the dictionary
                                help="Pick a register to force it, or let the bot infer it.") # Tooltip explaining the option

        sim_segment = st.selectbox("Territory — which customer category?",   # Creates a dropdown to set the customer segment (Axis 3)
                                   ["(unknown)"] + list(LOCATION_CONTEXT.keys()), # Provides unknown plus all defined segments
                                   help="Choose (unknown) to see the Territory escalation.") # Tooltip explaining what happens if left unknown

        user = {                                     # Builds a dictionary representing the current simulated user state
            "id_verified": sim_verified,             # Sets the ID verification status based on the checkbox
            "mood":    None if sim_mood.startswith("(") else sim_mood,      # Sets the mood to None if automatic, otherwise uses the selected tone
            "segment": None if sim_segment.startswith("(") else sim_segment, # Sets the segment to None if unknown, otherwise uses the selected segment
        }

        st.divider()                                 # Draws a horizontal line
        st.subheader("The Red Line")                 # Adds a sub-heading for the safety rules
        for r in MUST_NEVER_DO:                      # Loops through the hardcoded list of forbidden bot behaviors
            st.write(f"· {r}")                       # Prints each rule as a bullet point in the sidebar
            
        st.divider() # Draws a horizontal line
        if st.button("Logout" if is_admin else "End Session"): # Creates a dynamic button that says Logout for admins and End Session for customers
            set_state('homepage') # If clicked, resets the routing state back to the homepage
            st.rerun() # Reloads the app to send the user back to the start

    # ---------- MAIN AREA: TABS ----------
    # Admin gets all tabs, Customer gets Chat & Calc
    if is_admin: # Checks if the user is an admin
        (tab_chat, tab_calc, tab_blueprint,              # Unpacks a tuple of 6 tab containers created by Streamlit
         tab_web, tab_sources, tab_eval) = st.tabs( # Creates the 6 tabs with specific display names across the top of the main screen
            ["Chat", "Cost calculator", "Blueprint", "Web harvest", "Sources", "Eval"]) # The labels for the admin tabs
    else: # If the user is a customer
        tab_chat, tab_calc = st.tabs(["Chat", "Cost calculator"]) # Creates and unpacks only 2 tabs for the restricted customer view

    # ---------- TAB 1: the chat ----------
    with tab_chat:                                   # Opens context for the first tab (Chat interface)
        if "messages" not in st.session_state:       # Checks if a chat history already exists in memory
            st.session_state.messages = []           # If not, creates an empty list to hold the chat bubbles

        for m in st.session_state.messages:          # Loops through every saved message in the chat history
            with st.chat_message(m["role"]):         # Creates a visual chat bubble assigned to either 'user' or 'assistant'
                st.markdown(m["content"])            # Renders the text content of the message as Markdown
                if m.get("hits"):                    # Checks if this specific assistant message has retrieved documents attached to it
                    with st.expander("Sources used"):        # Creates a collapsible section beneath the chat bubble
                        for i, h in enumerate(m["hits"], 1): # Loops through the chunks used by the AI, numbering them starting from 1
                            st.markdown(f"**[{i}] {h['source']}** · score {h['score']}") # Prints the chunk number, filename, and search relevance score
                            st.caption(h["text"])    # Prints the actual excerpt text in small grey font

        if q := st.chat_input("Ask about appliance costs, tariffs or saving energy…"): # Renders the text input box at the bottom and assigns input to 'q' if user hits enter
            st.session_state.messages.append({"role": "user", "content": q})   # Adds the user's new question to the session state history
            with st.chat_message("user"):            # Creates a new visual chat bubble for the user immediately
                st.markdown(q)                       # Renders the user's question in the bubble

            with st.chat_message("assistant"):       # Creates a new visual chat bubble for the bot's upcoming reply
                with st.spinner("Retrieving…"):      # Shows a loading spinner while the backend processes the request
                    out = answer(q, index, user)     # Calls the core backend pipeline (A.R.T check + Retrieval + LLM call)
                st.markdown(out["reply"])            # Renders the final text answer from the bot
                st.caption(f"lane: {out.get('intent', '-')} · "                # Prints debug info: whether it was routed as small-talk or domain
                           f"register: {out.get('register', '-')} · "        # Prints debug info: which tone it used
                           f"answered by: {out['provider']} · {out['model']}")  # Prints debug info: which AI provider and model generated the response
                if out["hits"]:                      # Checks if the bot used any documents to answer this turn
                    with st.expander("Sources used"):        # Creates a collapsible section for the newly used sources
                        for i, h in enumerate(out["hits"], 1): # Loops through the source chunks
                            st.markdown(f"**[{i}] {h['source']}** · score {h['score']}") # Prints chunk metadata
                            st.caption(h["text"]) # Prints chunk text

            st.session_state.messages.append(        # Saves the bot's final reply and its sources to the session history so it persists
                {"role": "assistant", "content": out["reply"], "hits": out["hits"]}) # The dictionary object appended to history

    # ---------- TAB 2: the calculator ----------
    with tab_calc:                                   # Opens context for the second tab (Cost Calculator)
        st.warning("The rate below is a placeholder. Confirm the real LUCELEC rate " # Prints a yellow warning about the placeholder rate
                   "with the client before you show this to anyone.") # Reminds users to get client confirmation

        rate = st.number_input("Rate (EC$ per kWh)", value=float(DEFAULT_RATE_PER_KWH), # Creates a numeric input box for the electricity rate
                               min_value=0.0, step=0.05)   # Sets constraints so it can't go below zero, and steps by 0.05 on clicks

        c1, c2 = st.columns(2)                       # Splits the calculator layout into two vertical columns for comparison
        with c1:                                     # Opens context for the left column (Appliance A)
            st.subheader("Appliance A")              # Adds a sub-heading for the first appliance
            na = st.text_input("Name A", "Old fridge")            # Creates a text box for the name, defaulted to 'Old fridge'
            wa = st.number_input("Watts A", value=350.0, min_value=0.0)          # Creates a numeric box for wattage
            ha = st.number_input("Hours per day A", value=8.0, min_value=0.0, max_value=24.0) # Creates a numeric box for usage hours, capped at 24
            pa = st.number_input("Purchase price A (EC$)", value=1500.0, min_value=0.0) # Creates a numeric box for the appliance cost
        with c2:                                     # Opens context for the right column (Appliance B)
            st.subheader("Appliance B") # Adds a sub-heading for the second appliance
            nb = st.text_input("Name B", "Inverter fridge") # Creates a text box for the name, defaulted to 'Inverter fridge'
            wb = st.number_input("Watts B", value=150.0, min_value=0.0) # Creates a numeric box for wattage
            hb = st.number_input("Hours per day B", value=8.0, min_value=0.0, max_value=24.0) # Creates a numeric box for usage hours, capped at 24
            pb = st.number_input("Purchase price B (EC$)", value=2600.0, min_value=0.0) # Creates a numeric box for the appliance cost

        if st.button("Compare"):                     # Creates a button to execute the calculation; only runs if clicked
            result = compare_appliances(             # Calls the backend math function to calculate running costs and payback
                {"name": na, "watts": wa, "hours_per_day": ha, "price": pa},   # Passes Appliance A dictionary mapping
                {"name": nb, "watts": wb, "hours_per_day": hb, "price": pb},   # Passes Appliance B dictionary mapping
                rate)                                # Passes the dynamic rate from the UI

            k1, k2, k3 = st.columns(3)               # Splits the results section into three columns
            k1.metric(f"{na} — per year", f"EC${result[na]['cost_year']:,.2f}")   # Displays Appliance A's yearly cost formatted to 2 decimal places
            k2.metric(f"{nb} — per year", f"EC${result[nb]['cost_year']:,.2f}") # Displays Appliance B's yearly cost formatted to 2 decimal places
            k3.metric("Yearly saving", f"EC${result['yearly_saving']:,.2f}") # Displays the absolute difference in running costs

            if result["payback_years"]:              # Checks if there is a valid payback period (i.e. if the expensive unit is cheaper to run)
                st.success(f"{result['cheaper_to_run']} pays back the price difference in about " # Displays a green box with the payback conclusion
                           f"{result['payback_years']} years.") # Injects the calculated payback years
            st.json(result)                          # Dumps the raw JSON result on screen so users can audit the raw mathematical data

    # ---------- ADMIN ONLY TABS (3-6) ----------
    if is_admin: # Verifies again that the user is an admin before rendering the sensitive/backend tabs
        # ---------- TAB 3: the Week 1 Blueprint ----------
        with tab_blueprint:                              # Opens context for the 3rd tab
            st.caption("Everything your Pod decided in Week 1, read straight out of " # Explains the purpose of this tab
                       "Section 2 of the code. If a line still says TODO_, it is not finished.") # Reminds devs to complete their code

            b1, b2 = st.columns(2)                       # Splits layout into 2 columns
            with b1:                                     # Context for left column
                st.subheader("Primary persona")          # Sub-heading for Persona definitions
                for k, v in PERSONA.items():             # Loops over the hardcoded persona dictionary
                    st.write(f"**{k}** — {v}")           # Prints each key-value pair

            with b2:                                     # Context for right column
                st.subheader("Empathy map")              # Sub-heading for empathy map definitions
                for k, v in EMPATHY_MAP.items():         # Loops over the hardcoded empathy map dictionary
                    st.write(f"**{k}** — {v}") # Prints each key-value pair

            st.divider()                                 # Draws a horizontal line

            st.subheader("The Wardrobe — code-switch demo")   # Sub-heading for the voice generation demo
            st.caption("Same facts. Different outfit. This is the demo to show the client.") # Explains the demo

            sample = st.text_input("A line to say in every register",       # Creates a text box for standard input
                                   "Your fridge costs about EC$438 a year to run.") # Default phrase provided
            for register_name in TONES:                  # Loops over every configured tone function in the system
                st.write(f"`{register_name}` → {dress(register_name, sample)}") # Applies the tone mapping to the string and prints it out

            st.divider()                                 # Draws a horizontal line

            c1, c2 = st.columns(2)                       # Splits layout into 2 columns
            with c1:                                     # Context for left column
                st.subheader("Memory & privacy")         # Sub-heading for data policy
                st.write("**Held during the conversation**") # Label
                for item in MEMORY_POLICY["remember_during_the_conversation"]: # Loops through configured temporary memory items
                    st.write(f"· {item}")                # Prints them as bullets
                st.write("**Never stored**") # Label
                for item in MEMORY_POLICY["never_store"]: # Loops through strictly protected data points
                    st.write(f"· {item}") # Prints them as bullets
                st.caption(MEMORY_POLICY["forgotten_when"])   # Prints the retention policy rule

            with c2:                                     # Context for right column
                st.subheader("Confirmation register")    # Sub-heading for facts awaiting client approval
                outstanding = open_confirmations()       # Calls backend function to find items missing initials
                if outstanding:                          # If there are items pending sign-off
                    st.error(f"{len(outstanding)} facts still unconfirmed")   # Shows a red banner with the count
                    st.dataframe(outstanding, use_container_width=True)       # Renders the pending items in an interactive table
                else:                                    # If all items are signed off
                    st.success("Every fact signed off by the client.")        # Shows a green banner

            st.divider()                                 # Draws a horizontal line

            st.subheader("Day 3 interview")              # Sub-heading for interview answers
            for kind, qa in INTERVIEW_QUESTIONS.items(): # Loops over configured interview notes
                st.write(f"**{kind.upper()}** — {qa['asked']}")   # Prints the question asked
                st.caption(f"Client said: {qa['answer']}")        # Prints the exact response from the client

            st.divider()                                 # Draws a horizontal line

            st.subheader("Location & Context rulebook")  # Sub-heading for territory rules
            st.dataframe([{"segment": k, **v} for k, v in LOCATION_CONTEXT.items()], # Transforms the nested dictionary into a flat list of dictionaries
                         use_container_width=True)       # Renders the resulting data in an interactive full-width table

            st.subheader("Jargon → plain language")      # Sub-heading for terminology overrides
            st.dataframe([{"client word": k, "what we say": v}   # Transforms dictionary pairs into a list of row dictionaries
                          for k, v in JARGON_TO_PLAIN.items()], # Iterates through jargon map
                         use_container_width=True) # Renders it as a table

        # ---------- TAB 4: harvesting from the client's website ----------
        with tab_web:                                    # Opens context for the 4th tab (Web scraper)
            st.subheader("Harvest a page from the client's website") # Sub-heading
            st.info("Downloading a page is not the same as confirming a fact. Pages land " # Blue box explaining the safety protocol
                    "in the waiting room below. Nothing reaches the bot until a human " # Rule definition
                    "approves it with their initials.") # Rule definition

            st.caption(f"Allowed hosts: {', '.join(sorted(allowed_hosts()))} · " # Prints allowed domains from backend configuration
                       f"robots.txt is checked every time · " # Reminder about protocol
                       f"we wait whatever the site asks for, minimum " # Reminder about courtesy delays
                       f"{FETCH_DELAY_SECONDS}s (LUCELEC asks for 10s)") # Shows minimum defined delay

            url = st.text_input("Page address",          # Input box for a URL to scrape
                                "https://www.lucelec.com/content/customer-service") # Default URL provided

            if st.button("Fetch page"):                  # Button to trigger scraper
                with st.spinner("Checking robots.txt, waiting out the site's crawl " # Shows loading spinner to account for built-in delays
                                "delay, then downloading…"): # Spinner text
                    res = harvest(url)                   # Calls backend function to download, parse, and save to pending folder
                if res["ok"]:                            # Checks if harvest was successful
                    st.success(f"Saved {res['words']} words to {res['path']} — awaiting approval") # Shows green banner with file path
                    st.text(res["preview"])              # Dumps raw text preview to the screen
                else:                                    # If harvest failed (e.g. bad URL, forbidden by robots.txt)
                    st.error(res["error"])               # Prints red error message
                    if "robots.txt" in res["error"]:     # Specifically checks if failure was due to robots.txt blocks
                        with st.expander("What did robots.txt actually say?"): # Expander to view the exact rules
                            st.json(check_robots(url))   # Uses backend diagnostic tool to print robots.txt rules as JSON

            st.divider()                                 # Draws horizontal line

            st.subheader("Waiting room")                 # Sub-heading for pending files
            pending = list_pending()                     # Scans disk for files in the pending directory

            if not pending:                              # If the pending list is empty
                st.caption("Empty. Nothing is waiting for approval.") # Prints a placeholder text
            for item in pending:                         # Loops through each pending file found on disk
                with st.expander(f"{item['file']} — {item['words']} words — {item['url']}"): # Creates an expander for each file detailing its metadata
                    st.text(item["preview"])             # Renders the text snippet of the fetched page
                    st.caption("Read it properly before you approve it. Your initials go in the file.") # Instruction text

                    col_i, col_a, col_r = st.columns([2, 1, 1])   # Splits bottom of expander into input box and 2 buttons
                    with col_i:                          # Left column
                        who = st.text_input("Your initials", key=f"who_{item['file']}", # Input box for reviewer initials (must have unique key per file)
                                            max_chars=4, label_visibility="collapsed", # Caps at 4 chars, hides main label
                                            placeholder="Your initials") # Placeholder text
                    with col_a:                          # Middle column
                        if st.button("Approve", key=f"ok_{item['file']}"): # Approve button (must have unique key)
                            r = approve_harvest(item["file"], who)     # Calls backend to rename file, stamp initials, and move to knowledge base
                            if r["ok"]:                  # If approval succeeded
                                st.success(f"Approved by {r['by']} → {r['path']}") # Shows success
                                st.cache_resource.clear()    # Dumps cache so the bot re-indexes the knowledge base on next question
                                st.rerun()               # Reloads app to reflect changes
                            else:                        # If approval failed (e.g. missing initials)
                                st.error(r["error"]) # Prints red error
                    with col_r:                          # Right column
                        if st.button("Reject", key=f"no_{item['file']}"): # Reject button (must have unique key)
                            reject_harvest(item["file"])  # Calls backend to delete the file permanently
                            st.rerun()                   # Reloads app to remove the expander block

        # ---------- TAB 5: testing retrieval ----------
        with tab_sources:                                # Opens context for the 5th tab (Raw search)
            st.write("Drop the client's own .md or .txt files into `source_documents/`, " # Instructions for manual file additions
                     "then press Reload documents in the sidebar.") # Instructions for manual file additions

            probe = st.text_input("Test a retrieval query",          # Input box to test the raw RAG chunk search
                                  "how much does an air conditioner cost to run") # Default test string

            for i, h in enumerate(retrieve_chunks(probe, index), 1): # Searches chunks, returns top K matches, and loops through them
                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")   # Prints chunk rank, origin file, and mathematical relevance score
                st.caption(h["text"])                    # Prints the actual paragraph text retrieved

        # ---------- TAB 6: the eval ----------
        with tab_eval:                                   # Opens context for the 6th tab (Evaluation framework)
            st.write("Every change you make, run this again. If a row flips from " # Explains regression testing concept
                     "pass to fail, you broke something.") # Explains regression testing concept

            if st.button("Run eval set"):                # Button to trigger the expensive/slow evaluation test
                rows = run_eval(index, user)             # Feeds the hardcoded test suite through the LLM pipeline
                st.dataframe(rows, use_container_width=True)         # Renders the pass/fail results table
                passed = sum(1 for r in rows if r["passed"])         # Counts the number of passing cases
                st.metric("Passed", f"{passed}/{len(rows)}")         # Displays the final score fraction dynamically


# =====================================================================
# SECTION 12 · COMMAND LINE — running the bot without the website
# =====================================================================

def doctor():
    """Print exactly where the bot is looking and what it finds there.

    Run this first when something is "not found". It reports the two folders
    that get confused with each other — where the program was STARTED, and
    where this file LIVES — and then inspects every document individually,
    because a folder listing can show a file that cannot be opened.
    """
    print("\nFile system check\n")
    print(f"  Started from (cwd) : {os.getcwd()}")   # where python was launched
    print(f"  This file lives in : {BASE_DIR}")      # where lucelec_rag_bot.py sits
    if os.path.abspath(os.getcwd()) != BASE_DIR:     # the classic Deepnote mismatch
        print("  ^ These differ. That is normal and is handled — every path below "
              "is anchored to the file's own folder, not the cwd.")

    folder = project_path(DOCS_DIR)                  # the documents folder, absolutely
    print(f"\n  Documents folder   : {folder}")
    print(f"  Exists             : {os.path.isdir(folder)}")

    if not os.path.isdir(folder):                    # nothing to inspect
        print("\n  The folder is missing. Run --demo once and it will be created.\n")
        return

    entries = sorted(glob.glob(os.path.join(folder, "*")))   # what the listing claims
    print(f"  Listing shows      : {len(entries)} item(s)\n")

    if not entries:                                  # empty folder
        print("  Empty. Run --demo once and the sample documents will be written.\n")
        return

    for path in entries:                             # inspect each one properly
        name = os.path.basename(path)                # just the filename
        bits = []                                    # the findings for this file

        if os.path.islink(path):                     # is it a shortcut?
            target = os.path.realpath(path)          # what does it point at?
            bits.append(f"symlink -> {target}")      # say where
            if not os.path.exists(target):           # pointing at nothing?
                bits.append("BROKEN LINK")           # this is the usual culprit

        try:                                         # the real test: can we READ it?
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                words = len(f.read().split())        # count the words
            bits.append(f"readable, {words} words")  # all good
        except OSError as e:                         # listed but not readable
            bits.append(f"CANNOT OPEN: {type(e).__name__} — {e.strerror}")

        print(f"    {name:<34} {' | '.join(bits)}")

    print("\n  If a file says CANNOT OPEN, the fix is usually to delete it and let "
          "\n  the bot rewrite it: rm the file, then run --demo.\n")


def show_keys():
    """Print where every API key is stored. Run this first when something is broken."""
    print("\nAPI key store\n")                       # \n means "start a new line"
    print(f"  Key file : {project_path(SECRETS_FILE)}"       # where the Save button writes
          f" {'(exists)' if os.path.exists(project_path(SECRETS_FILE)) else '(not created yet)'}")
    print(f"  Env file : {project_path(ENV_FILE)}"           # the other file we check
          f" {'(exists)' if os.path.exists(project_path(ENV_FILE)) else '(not present)'}")
    print("  Look-up order: environment variable, then secrets.toml, then .env\n")

    for row in key_report():                         # one line per key
        state = "SET" if row["set"] else "not set"   # short status word
        print(f"  {row['name']:<18} {state:<9} {row['masked']:<14} source: {row['source']}")

    print("\n  Save a key without the app:")         # instructions for the terminal
    print('    python3 -c "import lucelec_rag_bot as b; b.save_key(\'GROQ_API_KEY\', \'gsk_...\')"')
    print("  Or use Deepnote's Environment tab, which is safer still.\n")


def show_providers():
    """Print every provider, whether it is ready, and ping the ones that are."""
    print("Provider status\n")                       # heading
    for p in provider_status():                      # one line per provider
        mark = "READY" if p["ready"] else "not configured"    # short status
        print(f"  {p['label']:<22} {p['model']:<32} {mark}")  # :<22 pads to 22 characters

    print("\n  Set a key:  python3 lucelec_rag_bot.py --keys   (shows where they live)")
    print("  Pin one:    export LLM_PROVIDER=groq")
    print("  Ollama:     ollama serve  &&  ollama pull llama3.2\n")

    for p in provider_status():                      # now actually test the ready ones
        if p["ready"]:                               # only the configured ones
            r = test_provider(p["name"])             # send a tiny test message
            print(f"  test {p['name']}: {'OK' if r['ok'] else 'FAIL'} — {r['reply'][:120]}")


def demo():
    """Run three questions through the whole pipeline and print the results."""
    index = build_index(load_chunks())               # load and score the documents
    print(f"{BOT_NAME} — {len(index['chunks'])} chunks indexed from {DOCS_DIR}/")

    live = [p["label"] for p in provider_status() if p["ready"]]   # which providers are usable
    print("Providers ready:", ", ".join(live) or "none (offline extractive mode)", "\n")

    for q in ["What appliance uses the most electricity?",        # a normal question
              "How do I read an energy label?",                   # another normal question
              "What is the balance on my account 12345678?"]:     # one that MUST be refused
        print(">", q)                                # show the question
        out = answer(q, index)                       # run the pipeline
        print(out["reply"])                          # show the answer
        print("   via:", out["provider"], "| sources:",           # show who answered
              ", ".join(h["id"] for h in out["hits"]) or "-", "\n")   # and which chunks

    print("Eval:", json.dumps(run_eval(index), indent=2)[:400], "…")  # a peek at the eval results


# This "if" is true only when you RUN this file directly. When another file
# imports it, everything above is defined but nothing below here happens.
if __name__ == "__main__":
    ap = argparse.ArgumentParser()                   # a reader for the options you type
    ap.add_argument("--demo",      action="store_true", help="Quick test, no website")
    ap.add_argument("--keys",      action="store_true", help="Show where API keys are stored")
    ap.add_argument("--doctor",    action="store_true", help="Check folders and documents on disk")
    ap.add_argument("--providers", action="store_true", help="Show and test API keys")
    ap.add_argument("--provider",  help="Pin one: openai | gemini | groq | nvidia | ollama")
    ap.add_argument("--ask",       help="Ask one question and exit")
    ap.add_argument("--harvest",   help="Fetch one page from the client's site into the waiting room")
    ap.add_argument("--pending",   action="store_true", help="List pages awaiting approval")
    ap.add_argument("--robots",    help="Explain what a site's robots.txt says about a page")
    ap.add_argument("--approve",   help="Approve a pending file into the knowledge base")
    ap.add_argument("--reject",    help="Delete a pending file")
    ap.add_argument("--by",        default="", help="Your initials, required by --approve")
    args, _ = ap.parse_known_args()                  # read them; ignore anything unrecognised

    if args.provider:                                # did you pin a provider?
        os.environ["LLM_PROVIDER"] = args.provider   # apply it for this run

    if args.doctor:                                  # --doctor
        doctor()                                     # inspect the file system
    elif args.robots:                                # --robots "https://..."
        for k, v in check_robots(args.robots).items():    # print the diagnosis line by line
            print(f"  {k:<14} {v}")
    elif args.harvest:                               # --harvest "https://..."
        r = harvest(args.harvest)                    # fetch into the waiting room
        print(json.dumps(r, indent=2)[:800])         # show what happened
    elif args.pending:                               # --pending
        rows = list_pending()                        # read the waiting room
        if not rows:                                 # nothing there
            print("Waiting room empty.")
        for row in rows:                             # one line per pending page
            print(f"  {row['file']:<40} {row['words']:>6} words  {row['url']}")
        print("\n  Approve with: --approve FILE --by YOUR_INITIALS")
    elif args.approve:                               # --approve FILE --by XX
        print(approve_harvest(args.approve, args.by))    # move it into the knowledge base
    elif args.reject:                                # --reject FILE
        print(reject_harvest(args.reject))           # bin it
    elif args.keys:                                  # --keys
        show_keys()                                  # show the key store
    elif args.providers:                             # --providers
        show_providers()                             # show and test the providers
    elif args.ask:                                   # --ask "some question"
        out = answer(args.ask, build_index(load_chunks()))   # run one question
        print(out["reply"])                          # print the answer
        print("\n[via", out["provider"], "·",        # and where it came from
              ", ".join(h["id"] for h in out["hits"]) or "no sources", "]")
    elif args.demo:                                  # --demo
        demo()                                       # run the three-question demo
    else:                                            # no options at all
        try:                                         # assume we were launched by Streamlit
            import streamlit                         # noqa: F401  (imported only to test it exists)
            streamlit_app()                          # build the website
        except ImportError:                          # Streamlit is not installed
            demo()                                   # fall back to the text demo
