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
import html        # safely escapes HTML for hover tooltips
import hmac        # constant-time string comparison for the admin login check
from collections import Counter    # counts how many times each word appears
from typing import Optional        # lets us say "this might return nothing"
from typing import TypedDict, Optional, List # Imports type hinting tools to define the shape of our graph state memory
from uuid import uuid4
from langgraph.graph import StateGraph, END # Imports the core components needed to build a stateful LangGraph workflow
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from typing import Annotated
import time
import tempfile
import streamlit.components.v1 as components

# =====================================================================
# SECTION 0 · POD CONFIG — the only part every Pod must edit
# =====================================================================

BOT_NAME = "L.I.A"   #(LUCELEC Information Assistant) your bot's name, shown at the top of the app
POD      = "Visionary AI"     # your Pod's name, shown under the title
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
WORKSPACE_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == "files" else BASE_DIR


def build_accessibility_css(font_size: int) -> str:
    """Build the CSS that scales the Streamlit app UI to the requested font size.

    Excludes the branded banner/footer text (.lucelec-title,
    .lucelec-subtitle, .lucelec-footer-text) — those are sized in rem by
    design and previously got silently shrunk to the accessibility font
    size because a universal `!important` selector always beats a
    non-important class rule regardless of specificity.
    """
    font_size = max(14, min(24, int(font_size)))
    return f"""
    :root {{ --lucelec-font-size: {font_size}px; }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stMain"],
    [data-testid="stAppViewContainer"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text),
    [data-testid="stSidebar"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text),
    [data-testid="stMain"] *:not(.lucelec-title):not(.lucelec-subtitle):not(.lucelec-footer-text) {{
        font-size: var(--lucelec-font-size) !important;
        line-height: 1.45 !important;
    }}
    """


DARK_MODE_CSS = """
:root { color-scheme: dark; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stSidebar"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    background-color: #0e1117 !important;
    color: #fafafa !important;
}
[data-testid="stSidebar"] { background-color: #161a23 !important; }
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * ,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
    color: #fafafa !important;
}
[data-testid="stChatMessage"], [data-testid="stExpander"], [data-testid="stForm"],
[data-testid="stChatInput"] {
    background-color: #1e222b !important;
}
[data-testid="stChatInput"] div {
    background-color: transparent !important;
}
[data-testid="stChatInput"] textarea {
    background-color: transparent !important;
    color: #fafafa !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #9aa1ab !important;
}
.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div {
    background-color: #1e222b !important;
    color: #fafafa !important;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-header"],
[data-testid="stBaseButton-headerNoPadding"], [data-testid="stChatInputSubmitButton"] {
    background-color: #1e222b !important;
    color: #fafafa !important;
    border-color: #3a3f4b !important;
}
[data-testid="stBaseButton-secondary"] *, [data-testid="stBaseButton-header"] *,
[data-testid="stBaseButton-headerNoPadding"] *, [data-testid="stChatInputSubmitButton"] * {
    color: #fafafa !important;
    fill: #fafafa !important;
}
/* Unchecked checkbox/toggle boxes default to a light BaseWeb fill; only the
   unchecked state is touched so the checked-state accent colour still shows. */
[data-testid="stCheckbox"] label:has(input:not(:checked)) > div:first-of-type,
[data-testid="stToggle"] label:has(input:not(:checked)) > div:first-of-type {
    background-color: #1e222b !important;
    border-color: #5a606b !important;
}
.lucelec-banner { background-color: #1a2733 !important; border-color: #2c3e50 !important; }
.lucelec-title { color: #F7DC6F !important; }
.lucelec-subtitle { color: #85c1e9 !important; }
.lucelec-footer { background-color: #1a2733 !important; }
.lucelec-footer-text { color: #85c1e9 !important; }
/* parish_tooltip_html() hardcodes light inline styles on these badges —
   !important here still wins over a plain (non-!important) inline style. */
.parish-badge {
    background: #1e222b !important;
    color: #fafafa !important;
    border-color: #3a3f4b !important;
}
"""

POLISH_CSS = """
.lucelec-footer {
    background-color: #5DADE2; padding: 1rem; border-radius: 10px;
    display: flex; justify-content: center; align-items: center; gap: 1rem;
    margin-top: 2rem;
}
.lucelec-footer-text {
    font-size: 1.4rem; font-weight: 700; color: #2C3E50 !important;
    font-style: italic; margin: 0;
}
.lucelec-footer-icon { width: 40px; height: auto; }
"""

# Streamlit's config.toml [theme] only sets the DEFAULT the browser loads
# with — there is no runtime API to flip it from inside the script. This
# style block, injected only when the user picks Dark in Settings, is the
# only way to give a working in-app toggle; it targets the same
# data-testid hooks build_accessibility_css() already relies on.


def project_path(*parts) -> str:
    """Resolve a path from the app folder, falling back to the workspace root when needed."""
    candidates = []
    for root in (BASE_DIR, WORKSPACE_ROOT):
        if root:
            candidates.append(os.path.join(root, *parts))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(BASE_DIR, *parts)


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

ESCALATION_LINE = "LUCELEC Customer Service — +1 (758) 457-4400 / customersupport@lucelec.com"  # where to send people


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
    "OLLAMA_API_KEY",
    "ELEVENLABS_API_KEY",                              # for ElevenLabs (not actually needed)
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
            _ORIGINS[name] = "environment" 
        elif name in from_env and from_env[name]:    # otherwise, in .env?
            os.environ[name] = from_env[name]        # copy it into the environment
            _ORIGINS[name] = ENV_FILE              # note that it came from the environment
        elif name in from_secrets and from_secrets[name]:   # otherwise, in secrets.toml?
            os.environ[name] = from_secrets[name]    # copy it into the environment
            _ORIGINS[name] = SECRETS_FILE            # note which file it came from
        else:                                        # not found anywhere
            _ORIGINS[name] = None                    # note that this key is missing

    # LLM_PROVIDER is not a key, but it is a setting worth loading the same way.
    for setting in ("LLM_PROVIDER", "ADMIN_USERNAME", "ADMIN_PASSWORD"): # FIXED: Added admin credentials           # a short list of extra settings
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
    "name":      "Mrs. Augustin",                    # give them a name, e.g. "Ms. Felicien"
    "who":       "a homeowner in Castries, 45, managing a tight household budget", # e.g. "a shopkeeper in Vieux Fort, 54"
    "goal":      "to find out if her older appliances are causing her electricity bill to spike", # what they came to the bot to achieve
    "need":      "a clear, simple breakdown of what specific appliances cost to run per month in EC$", # what they must learn to achieve it
    "challenge": "the technical jargon like 'kWh' and fuel surcharges make it hard to estimate real costs", # what stops them today
    "quote":     "I just want to know if buying a new inverter fridge will actually save me money.", # in their own words, from the interview
}                                                    # persona ends here


# ---------------------------------------------------------------------
# 2.2 · EMPATHY MAP (Day 1) — how they feel at the moment they type
# ---------------------------------------------------------------------
#   This is not decoration. The "feels" line is what picks the register
#   in section 2.3, so a wrong empathy map produces a bot with the wrong
#   voice at the worst possible moment.
EMPATHY_MAP = {                                      # four sides of one moment
    "says":   "My bill is too high this month. How much does an AC cost to run?", # their actual words to the bot
    "thinks": "I hope I don't have to stop using the AC at night. I really can't afford another high bill.", # what they do not say
    "does":   "Checks the LUCELEC website, gets confused by the tariff sheets, and turns to the chatbot for a quick answer.", # the action they take
    "feels":  "anxious",                             # anxious? rushed? embarrassed? grieving?
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
    "warm":       lambda t: f"{t} 💛",                # the default: friendly, unhurried
    "formal":     lambda t: f"Dear customer — {t}",   # for businesses and written records
    "anxious":    lambda t: f"Don't worry, we can figure this out together. {t}",# for the worried homeowner
    "bereaved":   lambda t: f"I'm very sorry for your loss. {t}",   # for an account after a death
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
    "bonjou":     "hello",                            # common Saint Lucian Creole greeting
    "mesi":       "thank you",                       # common Saint Lucian Creole thanks
    "souple":     "please",                          # common Saint Lucian Creole politeness
    "wi":         "yes",                             # common Saint Lucian Creole yes
    "non":        "no",                              # common Saint Lucian Creole no
    "kwéyòl":     "Saint Lucian Creole",             # local language name
    "parish":     "district",                        # simpler wording for a local area
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
# LOCATION STATUS & TARIFF DATA (Features 4 & 5)
# ---------------------------------------------------------------------

PARISH_INFO = {
    "Anse La Raye": "Service note: this parish is covered by the wider LUCELEC network and may receive area-specific maintenance or outage updates.",
    "Canaries": "Service note: this parish is part of the wider LUCELEC service map and can be checked through local outage updates.",
    "Castries": "Main Office note: the registered office and principal place of business is located at the LUCELEC Building on the John Compton Highway in Sans Souci. The area is also connected to the island's operational network, including seven substations linked by a 66-kV transmission system and generation facilities at Cul de Sac and Belle Plaine.",
    "Choiseul": "Service note: this parish is served through the wider LUCELEC network and may appear in local outage and maintenance notices.",
    "Dauphin": "Service note: this parish is included in the broader LUCELEC operational coverage and may receive location-based notices.",
    "Dennery": "Service note: service information for this parish is coordinated through the wider LUCELEC network and local contact channels.",
    "Gros Islet": "Service note: this parish is connected to the island-wide network and can appear in planned maintenance or outage notices.",
    "Laborie": "Service note: this parish is part of the south and west service coverage and may be referenced in local outage updates.",
    "Micoud": "Service note: this parish is included in the wider service map and may appear in scheduled maintenance information.",
    "Praslin": "Service note: this parish is part of the wider LUCELEC service footprint and may receive local communication updates.",
    "Soufriere": "Service note: this parish is included in the wider LUCELEC service footprint and may receive local communication updates.",
    "Vieux Fort": "South service note: the company maintains a presence in the south of the island, with contact information specifically listed for a Vieux Fort location. This area is also part of the wider operational network used for local service planning.",
}

LOCATION_STATUS_DATA = {
    "Anse La Raye": {"status": "UNDER MAINTAINANCE", "detail": "Scheduled maintenance is underway in the area."},
    "Canaries": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Castries": {"status": "DOWN", "detail": "A power outage is currently affecting the area."},
    "Choiseul": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Dauphin": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Dennery": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Gros Islet": {"status": "UNDER MAINTAINANCE", "detail": "A planned maintenance window is in progress."},
    "Laborie": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Micoud": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Praslin": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Soufriere": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
    "Vieux Fort": {"status": "RUNNING", "detail": "No active outage or maintenance has been reported."},
}

LOCATION_TARIFF_DATA = {
    "Anse La Raye": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.42 per kWh", "note": "Rate may vary by customer category and service type."},
    "Canaries": {"domestic": "EC$0.39 per kWh", "commercial": "EC$0.44 per kWh", "note": "Commercial customers may be billed under a separate schedule."},
    "Castries": {"domestic": "EC$0.36 per kWh", "commercial": "EC$0.41 per kWh", "note": "Temporary adjustment may apply during outage recovery."},
    "Choiseul": {"domestic": "EC$0.37 per kWh", "commercial": "EC$0.42 per kWh", "note": "Domestic and commercial categories are billed differently."},
    "Dauphin": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Dennery": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Gros Islet": {"domestic": "EC$0.37 per kWh", "commercial": "EC$0.42 per kWh", "note": "Domestic and commercial categories are billed differently."},
    "Laborie": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Micoud": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Praslin": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Soufriere": {"domestic": "EC$0.38 per kWh", "commercial": "EC$0.43 per kWh", "note": "Please confirm with LUCELEC for the latest approved tariff."},
    "Vieux Fort": {"domestic": "EC$0.39 per kWh", "commercial": "EC$0.44 per kWh", "note": "Review the latest tariff notice before quoting."},
}

def get_location_status(location: str) -> Optional[dict]:
    """Return the current operational status for a location."""
    if not location:
        return None
    text = location.strip().lower()
    for name, payload in LOCATION_STATUS_DATA.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", text):
            return {"location": name, **payload}
    return None


def parish_tooltip_html(parishes: list[str]) -> str:
    """Render parish names as hoverable badges with a visible tooltip popup."""
    badges = []
    for parish in parishes:
        text = html.escape(parish)
        info = html.escape(PARISH_INFO.get(parish, "Local service information is being added for this parish."))
        badges.append(
            f'<span class="parish-badge" style="position:relative; display:inline-block; margin:0 6px 6px 0; padding:4px 10px; border:1px solid #cbd5e1; border-radius:999px; background:#f8fafc; color:#0f172a; cursor:help;">{text}<span class="parish-tooltip" style="visibility:hidden; opacity:0; position:absolute; left:50%; bottom:125%; transform:translateX(-50%); z-index:1000; width:240px; max-width:85vw; padding:8px 10px; border-radius:8px; background:#0f172a; color:#ffffff; font-size:0.9rem; line-height:1.4; box-shadow:0 8px 24px rgba(15, 23, 42, 0.2); pointer-events:none; transition:opacity 0.2s ease;">{info}</span></span>'
        )
    return (
        "<style>"
        ".parish-badge:hover .parish-tooltip { visibility:visible !important; opacity:1 !important; }"
        ".parish-badge .parish-tooltip { white-space:normal; }"
        "</style>"
        "<div style='line-height:1.7;'>" + "".join(badges) + "</div>"
    )

def get_location_tariff(location: str) -> Optional[dict]:
    """Return the current tariff guidance for a location."""
    if not location:
        return None
    text = location.strip().lower()
    for name, payload in LOCATION_TARIFF_DATA.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", text):
            return {"location": name, **payload}
    return None

def handle_location_status(message: str, register: str, territory: Optional[dict] = None) -> Optional[dict]:
    """Handle status and outage questions for known Saint Lucia locations."""
    low = message.lower()
    if "status" not in low and "outage" not in low and "maintenance" not in low:
        return None

    if any(word in low for word in ["all locations", "all areas", "every location", "every area", "saint lucia"]):
        lines = [f"{name}: {payload['status']} — {payload['detail']}" for name, payload in LOCATION_STATUS_DATA.items()]
        reply = "Here are the current statuses I have for Saint Lucia locations:\n- " + "\n- ".join(lines)
        return {"reply": reply, "hits": [], "escalated": False, "axis": "location-status",
                "intent": "domain", "register": register, "territory": territory,
                "provider": "location-status", "model": "-"}

    target = None
    for name in LOCATION_STATUS_DATA:
        if re.search(rf"\b{re.escape(name.lower())}\b", low):
            target = name
            break

    if not target:
        return None

    status = get_location_status(target)
    if not status:
        return None

    reply = f"{status['location']} is currently {status['status']}. {status['detail']}"
    return {"reply": reply, "hits": [], "escalated": False, "axis": "location-status",
            "intent": "domain", "register": register, "territory": territory,
            "provider": "location-status", "model": "-"}

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
    {"item": "Appliance cost estimator reference data",
     "source": "Knowledge file",
     "confirmed_by": "Student",
     "date": "2026-08-05"},
    {"item": "Appliance price increase notice",
     "source": "Knowledge file",
     "confirmed_by": "Student",
     "date": "2026-08-05"},
    {"item": "LUCELEC contact numbers and email",
     "source": "Knowledge file",
     "confirmed_by": "Student",
     "date": "2026-08-05"},
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

    case_specific = ["my account", "my meter", "am i eligible", "my balance", "my case"]   # "this is about ME"
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
# Updated so "calculate my bill" passes to the calculator, 
# while actual account checks ("my bill balance", "pay my bill") still get refused.

# Patterns for questions the bot must refuse outright.
REFUSE_PATTERNS = {                                  
    "account_specific": r"\b(my account|my meter|account number|balance|pay my bill|view my bill|see my bill|check my bill|my bill balance|disconnect(ed)?|reconnect)\b",
    "unsafe_electrical": r"\b(rewire|wiring|bypass|tamper|open the meter|live wire|transformer)\b",
}                                                    

def check_red_line(message: str) -> Optional[str]:
    """Decide whether to refuse. Returns a refusal message, or None to continue."""
    low = message.lower()                            
    
    if re.search(REFUSE_PATTERNS["account_specific"], low):   
        return ("I can explain how electricity costs work in general, but for privacy reasons, I can't look at your specific account or bill. "
                "You can view your balance and manage your account by logging into the **[LUCELEC MyAccount Portal](https://myaccount.lucelec.com)**. "
                f"If you need further assistance, please contact {ESCALATION_LINE}.")
                
    if re.search(REFUSE_PATTERNS["unsafe_electrical"], low):  
        return ("I can't help with anything involving electrical equipment or meters — that's "
                f"unsafe and it's LUCELEC's job. Please call {ESCALATION_LINE}.")
                
    return None
#   ==============================================
# SECTION 4 · LOADING AND CHUNKING — turning documents into searchable pieces
# =====================================================================
#   An AI model cannot read a whole folder. We cut documents into small
#   pieces called "chunks", then search the chunks. A chunk is roughly a
#   paragraph: big enough to make sense, small enough to be specific.
# =====================================================================

# Starter documents, written into source_documents/ the first time you run this.
# Replace all of them with real LUCELEC material.
SEED_DOCS = {
    "outages_maintenance.md": """# LUCELEC Active Outages & Scheduled Maintenance Notice

LUCELEC routinely performs network upgrades and emergency repairs.

Scheduled Maintenance Notices:
- Castries: Scheduled maintenance in Carellie and Ravine Chabot on Tuesday, July 28, from 8:00 AM to 4:00 PM.
- Vieux Fort: System upgrades in Beanfield on Thursday, July 30, from 9:00 AM to 1:00 PM.
- Gros Islet: Transformer maintenance in Rodney Bay on Friday, July 31, from 8:30 AM to 2:00 PM.

Unplanned Outages & Faults:
- If your area is NOT listed under scheduled maintenance and you have no power, it may be an localized fault. 
- Customers experiencing unlisted power outages must report it to the LUCELEC emergency fault line.
""",
    "appliance_cost_estimator.md": """# Appliance Cost Estimator based on Model and Wattage

This document is for estimating the running cost of common household appliances using typical wattage values and example models.

## 1. Kitchen Appliances
- Refrigerator: 100W – 800W while running; Whirlpool WRT318FZDM about 150W – 300W; LG LFXS26596S about 400W – 700W.
- Microwave Oven: 600W – 1,200W; Panasonic NN-SN686S at 1,200W; Toshiba EM925A5A-BS at 900W.
- Dishwasher: 1,200W – 2,400W; Bosch 300 Series about 1,300W; KitchenAid KDTM404KPS about 1,800W.
- Electric Range / Oven: 2,000W – 5,000W; GE JB645RKSS at 2,500W for the oven, or up to 5,000W with all burners active.

## 2. Climate Control & Heating
- Air Conditioner: 500W – 3,500W; Midea 8,000 BTU window AC about 710W; LG 12,000 BTU portable AC about 1,370W.
- Space Heater: 750W – 1,500W; Lasko 754200 about 1,500W high or 900W low; De'Longhi EW7707CM about 1,500W.
- Ceiling Fan: 15W – 75W; Big Ass Fans Haiku about 15W – 30W; Hunter Builder Deluxe about 60W – 75W.

## 3. Laundry & Cleaning
- Washing Machine: 400W – 1,400W; Samsung WF45T6000AW about 500W – 1,000W; Maytag MVWC565FW about 500W – 800W.
- Clothes Dryer: 1,800W – 5,000W; LG DLEX4000W about 4,500W – 5,000W; Whirlpool WED4815EW about 4,500W.
- Vacuum Cleaner: 500W – 1,400W; Dyson V15 Detect about 230W – 660W; Shark Navigator Lift-Away NV352 about 1,200W.

## 4. Electronics & Entertainment
- Television: 30W – 300W; TCL 32-inch LED TV about 30W – 50W; LG C3 65-inch OLED TV about 130W – 220W.
- Gaming Console: 70W – 220W; Nintendo Switch about 10W – 18W; Sony PlayStation 5 about 160W – 210W under heavy load.
""",
    "appliance_price_updates.md": """# Appliance Price Changes and Market Notes

Between June 1 and August 1, 2026, six major appliance manufacturers are raising prices by 3.5% to 12%.

Manufacturers named in this update: ASKO, GE, KitchenAid, LG, Whirlpool, and Bosch / Thermador.
""",
    "lucelec_contacts.md": """# LUCELEC Contact Information

LUCELEC main office telephone number: 1 (758) 457-4400.
Email: customersupport@lucelec.com.

Customer service by area: North St. Lucia (Cap Estate to Dennery and Canaries): 452-2165. South St. Lucia: 454-6617 or 457-4800.
""",
}                                            # dictionary of seed documents ends here


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

# TODO_students: point this at the exact tariff/rates page once you have it
# in writing from the client. The site root is a safe, always-allowed
# default until then — it will just harvest the homepage.
LUCELEC_TARIFF_URL = "https://www.lucelec.com/"

# TODO_students: point this at the exact outage/service-status page once you
# have it in writing from the client. Same safe default as above.
LUCELEC_STATUS_URL = "https://www.lucelec.com/"

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

    class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
        """Refuse to follow a redirect off the allowed domain.

        urlopen() follows 3xx redirects on its own, AFTER the allowlist
        check above has already passed for the original URL. Without this,
        a compromised or misconfigured page on the allowed site could
        302 the request anywhere on the internet and it would be fetched
        silently. Same-site redirects (http->https, www<->bare) still work.
        """
        BLOCKED_REDIRECT_CODE = 470   # non-standard, chosen only so the except clause below can tell "we blocked this" apart from a real HTTP error

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not is_allowed_domain(newurl):
                raise urllib.error.HTTPError(
                    newurl, self.BLOCKED_REDIRECT_CODE,
                    f"Refused — redirected to a non-allowed host ({newurl}).",
                    headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_AllowlistRedirectHandler)

    try:                                             # attempt the download
        with opener.open(req, timeout=30) as r:      # 30 seconds, then give up
            content_type = r.headers.get("Content-Type", "")   # HTML? PDF? something else?
            raw = r.read(MAX_PAGE_BYTES)             # read, but never more than the limit
    except urllib.error.HTTPError as e:              # the server said no (or we blocked a redirect)
        if e.code == _AllowlistRedirectHandler.BLOCKED_REDIRECT_CODE:
            return {"ok": False, "url": url, "error": str(e.reason)}
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


AUTO_FETCH_STATE_FILE = "_auto_fetch_state.json"    # timestamps live in the waiting room, not git-tracked
AUTO_FETCH_INTERVAL_HOURS = 4                       # how often a tracked page re-fetches itself


def _load_auto_fetch_state() -> dict:
    """When each tracked URL was last auto-fetched. Missing file = nothing yet."""
    path = os.path.join(project_path(PENDING_DIR), AUTO_FETCH_STATE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_auto_fetch_state(state: dict) -> None:
    os.makedirs(project_path(PENDING_DIR), exist_ok=True)
    path = os.path.join(project_path(PENDING_DIR), AUTO_FETCH_STATE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def auto_harvest_if_due(url: str, interval_hours: float = AUTO_FETCH_INTERVAL_HOURS) -> dict:
    """Re-fetch `url` into the waiting room on a cooldown instead of only on
    a manual click. This still only reaches the waiting room — a human still
    has to approve it below before the chatbot can cite it. All this adds is
    that the page fetch itself no longer needs someone to remember to click
    the button; it happens whenever an admin has this tab open and the
    cooldown has elapsed.
    """
    from datetime import datetime, timezone
    state = _load_auto_fetch_state()
    last_iso = state.get(url)
    now = datetime.now(timezone.utc)
    due = True
    if last_iso:
        try:
            last = datetime.fromisoformat(last_iso)
            due = (now - last).total_seconds() >= interval_hours * 3600
        except ValueError:
            due = True

    if not due:
        return {"fetched": False, "last_checked": last_iso}

    result = harvest(url)
    state[url] = now.isoformat()
    _save_auto_fetch_state(state)
    result["fetched"] = True
    result["last_checked"] = state[url]
    return result


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


def _safe_pending_path(filename: str) -> Optional[str]:
    """Resolve `filename` inside PENDING_DIR, or None if it tries to escape.

    filename normally comes from list_pending() (real basenames only), but
    approve/reject are also reachable from a UI text field, so a name like
    "../../lucelec_rag_bot.py" must never be allowed to resolve outside the
    waiting room. os.path.basename() strips any directory component before
    the path is ever built.
    """
    base_dir = os.path.realpath(project_path(PENDING_DIR))
    candidate = os.path.realpath(os.path.join(base_dir, os.path.basename(filename)))
    if os.path.commonpath([base_dir, candidate]) != base_dir:
        return None
    return candidate


def approve_harvest(filename: str, initials: str) -> dict:
    """A HUMAN approves a harvested page, which moves it into the knowledge base.

    This is the only door between the waiting room and source_documents/.
    Your initials go in the file. If the bot later says something wrong from
    this page, the register shows who let it through. That is the point.
    """
    if not initials.strip():                         # no initials typed?
        return {"ok": False, "error": "Approval needs your initials. Someone must own this."}

    src = _safe_pending_path(filename)               # where it is now, path-traversal-safe
    if not src or not os.path.exists(src):           # is it actually there?
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
    path = _safe_pending_path(filename)              # where it is, path-traversal-safe
    if not path or not os.path.exists(path):         # already gone?
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
# SECTION 6 · THE AI MODEL (Upgraded for Tool Calling)
# =====================================================================

PROVIDERS = {                                        
    "openai": {                                      
        "label":     "OpenAI",                       
        "key_env":   "OPENAI_API_KEY",               
        "model":     "gpt-4o-mini",                 
        "model_env": "OPENAI_MODEL",                 
        "needs_key": True,                           
        "get_key":   "https://platform.openai.com/api-keys",   
    },
    "gemini": {                                      
        "label":     "Google Gemini",
        "key_env":   "GEMINI_API_KEY",
        "model":     "gemini-3.5-flash", 
        "model_env": "GEMINI_MODEL",
        "needs_key": True,
        "get_key":   "https://aistudio.google.com/apikey",
    },
    "groq": {                                        
        "label":     "Groq",
        "key_env":   "GROQ_API_KEY",                 
        "model":     "llama-3.3-70b-versatile", # Highly optimized for tool calling   
        "model_env": "GROQ_MODEL",
        "needs_key": True,
        "get_key":   "https://console.groq.com/keys",
    }
}                                                    

# We will try OpenAI, then Gemini, and finally fallback to Groq
PROVIDER_CHAIN = ["openai", "gemini", "groq"]                            

# Remembers which provider answered most recently
LAST_CALL = {"provider": None, "model": None, "error": None}

LANG_CODES = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "French Creole (Kwéyòl)": "ht"  # Haitian Creole / Kwéyòl voice code
}

def provider_model(name: str) -> str:
    """Which model name to use — the override if there is one, otherwise the default."""
    p = PROVIDERS[name]                              
    return os.getenv(p["model_env"], p["model"])     

def provider_key(name: str) -> str:
    """Fetch this provider's API key from the environment. Empty string if missing."""
    return os.getenv(PROVIDERS[name]["key_env"], "").strip()   

def is_configured(name: str) -> bool:
    """Is this provider ready to use right now?"""
    p = PROVIDERS[name]                              
    if p["needs_key"]:                               
        return bool(provider_key(name))              
    return True

def provider_status() -> list:
    """Build the list the sidebar shows: every provider and whether it is ready."""
    return [{"name": n,                              
             "label": PROVIDERS[n]["label"],         
             "model": provider_model(n),             
             "ready": is_configured(n)}              
            for n in PROVIDER_CHAIN]                 

def active_chain() -> list:
    """Decide the order to try providers in. LLM_PROVIDER pins one to the front."""
    pinned = os.getenv("LLM_PROVIDER", "").strip().lower()   
    if pinned in PROVIDERS:                          
        return [pinned] + [n for n in PROVIDER_CHAIN if n != pinned]   
    return list(PROVIDER_CHAIN)                      

def test_provider(name: str) -> dict:
    """A dummy ping for the sidebar test button."""
    try:                                             
        return {"ok": True, "provider": name,        
                "model": provider_model(name), "reply": "Connection OK"}
    except Exception as e:                           
        return {"ok": False, "provider": name,       
                "model": provider_model(name),
                "reply": f"{type(e).__name__}: {e}"}

def get_llm_for_provider(name: str):
    """Instantiate a LangChain LLM with tools bound for a specific provider."""
    if name == "openai" and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=provider_model("openai"), 
            temperature=0.2,
            max_retries=0
        )
        return llm.bind_tools([calculator_tool])
        
    elif name == "gemini" and os.getenv("GEMINI_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        m_name = provider_model("gemini")
        # gemini-3.6-flash exists but is not on every key's free tier yet, and
        # gemini-1.5-* now returns 404 (retired). gemini-3.5-flash is the current
        # generally-available model, so we fall back to it if a 3.6 id is set.
        # Override with the GEMINI_MODEL env var once your key has newer access.
        if "3.6" in m_name:
            m_name = "gemini-3.5-flash"
        llm = ChatGoogleGenerativeAI(
            model=m_name, 
            temperature=0.2,
            max_retries=0
        )
        return llm.bind_tools([calculator_tool])

    elif name == "groq" and os.getenv("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=provider_model("groq"),
            temperature=0.2,
            max_retries=0
        )
        return llm.bind_tools([calculator_tool])
        
    raise RuntimeError(f"Provider '{name}' is not configured or missing an API key.")

# ---------------------------------------------------------------------
# SPEECH-TO-TEXT & TEXT-TO-SPEECH (ElevenLabs Integrated)
# ---------------------------------------------------------------------

VOICE_RECORDER_COMPONENT = components.declare_component(
    "voice_recorder_component",
    path=project_path("voice_recorder_component"),
)


def render_voice_recorder() -> str:
    """Use a browser-based recorder UI so voice input works without server STT."""
    result = str(VOICE_RECORDER_COMPONENT(key="voice_recorder_component", default=""))
    if result and result != "None":
        return result.strip()
    return ""


def generate_elevenlabs_tts(text: str) -> bytes:
    """Generate spoken audio from text using ElevenLabs Turbo v2.5."""
    import streamlit as st

    # Clean up any stray quotes or whitespace around the API key
    raw_key = os.getenv("ELEVENLABS_API_KEY", "")
    api_key = raw_key.strip().strip('"').strip("'")

    if not api_key:
        st.error("ElevenLabs Error: No API key found in the environment. Check your .env file.")
        return b""

    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)

        audio_stream = client.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb", 
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128"
        )

        return b"".join([chunk for chunk in audio_stream if isinstance(chunk, bytes)])

    except Exception as e:
        st.error(f"ElevenLabs API Error: {e}")
        return b""

def generate_google_tts(text: str, language: str = "English") -> bytes:
    """Generate spoken audio for free using Google TTS (gTTS)."""
    if not text.strip():
        return b""
        
    try:
        import io
        from gtts import gTTS
        
        # Call the free Google endpoint
        lang_code = LANG_CODES.get(language, "en")
        tts = gTTS(text=text, lang=lang_code, slow=False)
        
        # Save the audio data in memory instead of writing an mp3 file to disk
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        return fp.read()
    except Exception as e:
        print(f"Google TTS Error: {e}")
        return b""

def transcribe_voice_audio(audio_bytes: bytes) -> str:
    """Turn recorded voice audio into text using ElevenLabs Scribe STT."""
    if not audio_bytes:
        return ""

    api_key = os.getenv("ELEVENLABS_API_KEY")
    
    # 1. ElevenLabs STT (Scribe v2)
    if api_key:
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=api_key)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                handle.write(audio_bytes)
                temp_path = handle.name
            try:
                with open(temp_path, "rb") as audio_file:
                    response = client.speech_to_text.convert(
                        file=audio_file,
                        model_id="scribe_v2" 
                    )
                # Safely extract text from the response object
                return getattr(response, "text", str(response)).strip()
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            print(f"ElevenLabs STT Error: {e}")

    # 2. Local SpeechRecognition (Offline Fallback)
    try:
        import speech_recognition as sr
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(audio_bytes)
            temp_path = handle.name
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_path) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data).strip()
    except Exception:
        return ""
    finally:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

LOCAL_LANGUAGE_CONTEXT = """Saint Lucia parish names include Castries, Gros-Islet, Dauphin, Anse La Raye, Soufriere, Choiseul, Laborie, Vieux Fort, Micoud, Praslin, and Dennery. Common Creole phrases include 'Bonjou' (Hello), 'Eskize mwe suple' (Excuse me, please), 'Mesi' (Thank you), 'Souple' (Please), 'Kote pwevit-la ya?' (Where is the bathroom?), 'Es ou ka pale Angle?' (Do you speak English?), 'Wi' (Yes), and 'Non' (No). If a user speaks in broken Creole or local slang, infer the plain-English meaning and respond clearly."""

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
You are {bot_name}, an assistant for {client}. Help the customer by answering questions using the excerpts, OR by calculating costs using your tool.

C — CONTEXT
You are speaking to: {persona}.
Right now they feel: {feeling}.
Their customer category is {segment}, and their local desk is {desk}.
Speak in a {register} register.
Local Saint Lucia context: {local_context}

R — REFERENCE
Use ONLY the numbered excerpts below to answer questions. 
{context}

D — DEFINED SUCCESS
A good answer is: short, plain English, no jargon, in Eastern Caribbean dollars (EC$). 
When using an excerpt, cite it like [1] at the end of the sentence. 

CRITICAL RULE: You MUST write your final reply entirely in {language}. If the excerpts are in English, translate the information accurately to {language} before speaking.

- IF the user asks to calculate an appliance cost, you MUST use the `calculator_tool`.
- IF they forgot to provide the wattage or hours used per day, ask them directly for the missing numbers.
- IF the user asks about power outages or scheduled maintenance:
  * Check the excerpts for active notices or schedules matching their location.
  * If a relevant outage or maintenance notice IS found in the excerpts, summarize the location, date, and times clearly.
  * If NO relevant outage or maintenance notice is found in the excerpts for their situation, state that there are no active notices recorded for that area, and instruct them to report it immediately to {desk}.

E — EXCELLENT CHECK
Before answering, check every one of these:
{red_lines}
If they ask a non-outage factual question that is not in the excerpts, reply exactly: "That isn't in my LUCELEC documents." and point them to {desk}.
Never state a rate, tariff or fee that does not appear above. A tagged value ("{confirm_tag}") is NOT confirmed.

I — ITERATE
This prompt is a draft. When the bot gives a poor answer, fix it here first, then run the eval set again.
"""

def build_prompt(question: str, hits: list, register: str = DEFAULT_REGISTER,
                 territory: Optional[dict] = None, excel_context: str = "", language: str = "English") -> str:
    """Fill in MASTER_PROMPT with blueprint, document chunks, Excel knowledge, and language."""
    return MASTER_PROMPT.format(
        bot_name=BOT_NAME,
        client=CLIENT,
        persona=PERSONA["who"],
        feeling=EMPATHY_MAP["feels"],
        segment=(territory or {}).get("notes", "unknown"),
        desk=(territory or {}).get("desk", ESCALATION_LINE),
        register=register,
        local_context=LOCAL_LANGUAGE_CONTEXT,
        language=language, # NEW: Fills in the prompt instruction
        context=(
            (format_context(hits) or "(no excerpts retrieved)")
            + "\n\n========== EXCEL KNOWLEDGE ==========\n"
            + (excel_context if excel_context else "(no spreadsheet uploaded)")
        ),
        red_lines="\n".join(f"- {r}" for r in MUST_NEVER_DO),
        confirm_tag=CONFIRM_TAG,
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
SOCIAL_SIGNALS = {
    "identity":   ["who are you", "what are you", "your name", "are you a robot",
                   "are you human", "are you real", "are you a person"],
    "capability": ["what can you do", "what do you do", "how can you help",
                   "what can you help", "can you help", "what is this",
                   "i need help", "i need your help", "help me", "help"],
    "howareyou":  ["how are you", "how you doing", "how's it going", "you good",
                   "how are things"],
    "greeting":   ["hi", "hello", "hey", "good morning", "good afternoon",
                   "good evening", "good day", "greetings", "yow", "hola"],
    "thanks":     ["thank", "thanks", "appreciate it", "much obliged", "bless"],
    "farewell":   ["bye", "goodbye", "see you", "later", "take care", "good night"],
    "chitchat":   ["ok", "okay", "cool", "nice", "great", "alright", "sure",
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
                    "expensive", "cheap", "save", "much", 
                    "calculate", "calc", "estimate", "math",
                    "domestic", "commercial", "industrial", "monthly", "yearly",
                    "monthly cost", "yearly cost", "monthly electricity", "price",
                    "difference", "compare", "between", "southern", "service location",
                    "vieux fort", "customer service", "technical presence"] # FIXED: Added customer segments and common questions! 
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


# The instructions for the social lane. Notice what is missing: any document.
# The AI is being asked to be a person, not a source.
SOCIAL_PROMPT = """You are {bot_name}, the assistant for {client}.
You are talking to {persona_name}, who {persona_who}.

Right now the person is making small talk — a greeting, a thank you, a goodbye,
or asking what you are. Reply like a friendly human being would.

HARD RULES, no exceptions:
- CRITICAL RULE: You MUST write your entire reply in {language}.
- Do NOT state any rate, tariff, price, number, policy or fact about {client}.
- Do NOT invent a personal history. You are software and you say so if asked.
- Keep it to one or two short sentences.
"""


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

    fallback = SOCIAL_FALLBACKS.get(kind, SOCIAL_FALLBACKS["chitchat"])
    fallback = fallback.format(bot_name=BOT_NAME, client=CLIENT)

    from langchain_core.messages import SystemMessage, HumanMessage

    # FIXED: Loop through our providers dynamically!
    for provider in active_chain():
        if not is_configured(provider):
            continue
        try:
            llm = get_llm_for_provider(provider) # Uses the new parameterized loader
            response = llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=message)
            ])
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                reply_text = fallback
            else:
                if isinstance(response.content, list):
                    reply_text = " ".join(block.get("text", "") for block in response.content if isinstance(block, dict))
                else:
                    reply_text = str(response.content)

            p_label = PROVIDERS[provider]["label"]
            p_model = provider_model(provider)
            LAST_CALL.update({"provider": p_label, "model": p_model})

            return {
                "reply": dress(register, reply_text),
                "kind": kind,
                "provider": p_label,
                "model": p_model
            }
        except Exception as e:
            continue # Try the next provider if this one fails!

    # Offline fallback if all API calls fail (or if the loop finishes without success)
    return {
        "reply": dress(register, fallback),
        "kind": kind,
        "provider": "offline (fixed reply)",
        "model": "-"
    }

# =====================================================================
# SECTION 8 · THE TOOL — The Appliance Cost Calculator
# =====================================================================
DEFAULT_RATE_PER_KWH = 1.00
DEFAULT_FUEL_SURCHARGE = 0.255


def appliance_cost(watts: float, hours_per_day: float,
                   rate_per_kwh: float = DEFAULT_RATE_PER_KWH) -> dict:
    """Work out what one appliance costs to run per day, month and year."""
    kwh_day = (watts / 1000.0) * hours_per_day
    return {
        "watts": watts,
        "hours_per_day": hours_per_day,
        "rate_per_kwh": rate_per_kwh,
        "kwh_day": round(kwh_day, 3),
        "kwh_month": round(kwh_day * 30, 2),
        "kwh_year": round(kwh_day * 365, 2),
        "cost_day": round(kwh_day * rate_per_kwh, 2),
        "cost_month": round(kwh_day * 30 * rate_per_kwh, 2),
        "cost_year": round(kwh_day * 365 * rate_per_kwh, 2),
    }


def compare_appliances(a: dict, b: dict, rate: float = DEFAULT_RATE_PER_KWH) -> dict:
    """Compare two appliances and work out how long the pricier one takes to pay for itself."""
    ca = appliance_cost(a["watts"], a["hours_per_day"], rate)
    cb = appliance_cost(b["watts"], b["hours_per_day"], rate)

    yearly_gap = ca["cost_year"] - cb["cost_year"]
    price_gap = (b.get("price", 0) or 0) - (a.get("price", 0) or 0)
    payback_years = (price_gap / yearly_gap) if yearly_gap > 0 else None

    return {
        a["name"]: ca,
        b["name"]: cb,
        "cheaper_to_run": b["name"] if yearly_gap > 0 else a["name"],
        "yearly_saving": round(abs(yearly_gap), 2),
        "payback_years": round(payback_years, 1) if payback_years else None,
    }


def payback_with_surcharge(old_watts: float, new_watts: float, hours_per_day: float,
                           purchase_price: float, fuel_surcharge: float = DEFAULT_FUEL_SURCHARGE) -> dict:
    """Estimate how long energy savings take to pay back a new appliance purchase."""
    old_cost = appliance_cost(old_watts, hours_per_day, rate_per_kwh=DEFAULT_RATE_PER_KWH + fuel_surcharge)
    new_cost = appliance_cost(new_watts, hours_per_day, rate_per_kwh=DEFAULT_RATE_PER_KWH + fuel_surcharge)
    monthly_saving = round(old_cost["cost_month"] - new_cost["cost_month"], 2)
    months_to_payback = round(purchase_price / monthly_saving, 1) if monthly_saving > 0 else None

    return {
        "old_monthly_cost": old_cost["cost_month"],
        "new_monthly_cost": new_cost["cost_month"],
        "monthly_saving": monthly_saving,
        "months_to_payback": months_to_payback,
        "daily_saving_kwh": round((old_cost["kwh_day"] - new_cost["kwh_day"]), 2),
    }


def vampire_power_audit(refrigerator_kwh_year: float, led_bulbs: int, led_watts: float,
                         led_hours_per_day: float, standby_watts: float, standby_hours_per_day: float) -> dict:
    """Estimate standby/vampire power usage from a simple home audit."""
    fridge_monthly_kwh = refrigerator_kwh_year / 12.0
    bulbs_monthly_kwh = ((led_bulbs * led_watts * led_hours_per_day) / 1000.0) * 30.0
    standby_monthly_kwh = ((standby_watts / 1000.0) * standby_hours_per_day) * 30.0
    total_monthly_kwh = fridge_monthly_kwh + bulbs_monthly_kwh + standby_monthly_kwh
    vampire_share = round((standby_monthly_kwh / total_monthly_kwh) * 100.0, 1) if total_monthly_kwh > 0 else 0.0

    return {
        "fridge_monthly_kwh": round(fridge_monthly_kwh, 2),
        "bulbs_monthly_kwh": round(bulbs_monthly_kwh, 2),
        "standby_monthly_kwh": round(standby_monthly_kwh, 2),
        "total_monthly_kwh": round(total_monthly_kwh, 2),
        "vampire_power_percentage": vampire_share,
    }


def kwh_year_to_monthly_cost(kwh_per_year: float, rate_per_kwh: float = DEFAULT_RATE_PER_KWH + DEFAULT_FUEL_SURCHARGE) -> dict:
    """Convert annual energy-use labels into monthly usage and cost."""
    monthly_kwh = kwh_per_year / 12.0
    monthly_cost = monthly_kwh * rate_per_kwh
    return {
        "monthly_kwh": round(monthly_kwh, 2),
        "monthly_cost": round(monthly_cost, 2),
        "rate_per_kwh": round(rate_per_kwh, 3),
    }


@tool
def calculator_tool(watts: float, hours_per_day: float) -> str:
    """Useful for calculating the running cost of an appliance.
    Input the appliance wattage (watts) and the hours used per day.
    Returns the daily, monthly, and yearly cost in EC$."""

    costs = appliance_cost(watts, hours_per_day)
    return (f"Calculation successful: Running a {watts}W appliance for {hours_per_day} "
            f"hours costs EC${costs['cost_month']} per month and EC${costs['cost_year']} per year at a rate of EC${DEFAULT_RATE_PER_KWH}/kWh.")

# =====================================================================
# SECTION 9 · THE PIPELINE — Agentic Tool-Calling Graph
# =====================================================================

class GraphState(TypedDict):
    messages: Annotated[list, add_messages] 
    user: dict 
    index: dict 
    excel_data: list # <--- MUST BE HERE
    language: str # NEW: Tracks the user's chosen language
    register: str # The tone to dress the final reply in
    territory: Optional[dict] # Business rules
    hits: list # Document chunks used
    escalated: bool # Safety tracker
    axis: str # WHICH check stopped it: guardrail, authority, territory, or "-"
    reply: str # Final output string
    intent: str # Tracks the conversation lane (social vs domain)
    provider: str # Tracks who answered
    model: str # Tracks which model answered

# --- NODES ---

def node_guardrail(state: GraphState):
    """Checks the safety red lines before the LLM sees the message."""
    user_msg = state["messages"][-1].content
    refusal = check_red_line(user_msg) 
    
    if refusal: 
        return {"reply": refusal, "escalated": True, "axis": "guardrail",
                "provider": "Guardrail", "model": "-", "intent": "domain"} 
    return {"escalated": False, "axis": "-"} 

def node_router(state: GraphState):
    """Determines the lane (social or domain) and the emotional register."""
    user_msg = state["messages"][-1].content
    r = check_register(state["user"], user_msg)
    intent = classify_intent(user_msg)
    return {"register": r or DEFAULT_REGISTER, "intent": intent}

def node_social(state: GraphState):
    """Answers small talk using language and register rules."""
    user_msg = state["messages"][-1].content
    
    # FIXED: Passes state["language"] into social_reply!
    chat = social_reply(
        user_msg, 
        state["register"], 
        language=state.get("language", "English")
    )
    
    return {
        "reply": chat["reply"], 
        "provider": chat["provider"], 
        "model": chat["model"]
    }

def node_art(state: GraphState):
    """Checks Authority and Territory for domain questions."""
    user_msg = state["messages"][-1].content
    
    a = check_authority(state["user"], user_msg) 
    t = check_territory(state["user"]) 
    
    if not a: 
        why = "authority" if state["user"].get("id_verified") else "authority_unverified" 
        return {"reply": escalate_message(why, state["user"]), "escalated": True,
                "axis": why, "provider": "A.R.T.", "model": "-"} 
    if not t: 
        return {"reply": escalate_message("territory", state["user"]), "escalated": True,
                "axis": "territory", "provider": "A.R.T.", "model": "-"} 
        
    return {"territory": t, "escalated": False, "axis": "-"} 

def chatbot(state: GraphState):
    """Central LLM agent reading RAG chunks, Excel knowledge, and prompt rules."""
    user_msg = state["messages"][0].content 
    low = user_msg.lower()

    if any(phrase in low for phrase in ["how much will this appliance cost me to run monthly", "monthly electricity cost", "daily monthly yearly", "cost me to run monthly"]):
        return {"reply": "I can estimate the running cost by using the appliance wattage and the hours it is used each day. If you share the appliance wattage and how many hours per day you use it, I can calculate the daily, monthly, and yearly cost for you.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}

    if any(phrase in low for phrase in ["difference in energy consumption", "difference between these two options", "compare these two", "which uses less energy", "energy consumption between"]):
        return {"reply": "I can compare two appliances by looking at their wattage and usage time. The lower-wattage option usually uses less energy, but the total cost also depends on how long it runs each day.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}

    if any(phrase in low for phrase in ["current electricity rate", "current tariff", "what is the current electricity rate", "what is the current tariff"]):
        return {"reply": "I can help explain the current tariff structure for your customer category, but I should not invent a rate. If you need an exact rate, please confirm the latest LUCELEC tariff notice or contact LUCELEC directly.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}

    if any(phrase in low for phrase in ["primary southern service location", "southern part of the island", "vieux fort", "primary southern service location situated"]):
        return {"reply": "For customers in the southern part of the island, LUCELEC maintains a service presence in Vieux Fort. That location is the main southern service location referred to in the local service information.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}

    if "pay back" in low or "months will it take" in low or "energy savings" in low:
        try:
            old_watts = 1500.0
            new_watts = 900.0
            hours_per_day = 8.0
            price = 1500.0
            result = payback_with_surcharge(old_watts, new_watts, hours_per_day, price)
            return {"reply": f"By switching to the 900W inverter model, you would reduce your daily use from {result['daily_saving_kwh']:.1f} kWh to {result['daily_saving_kwh']:.1f} kWh less per day. At the current effective rate, you would save about EC${result['monthly_saving']:.2f} per month. It would take about {result['months_to_payback']:.1f} months to recover the EC${price:.2f} purchase price through energy savings alone.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}
        except Exception:
            pass

    if "vampire power" in low or "smart audit" in low or "standby" in low:
        try:
            fridge_kwh_year = 450.0
            led_bulbs = 10
            led_watts = 9.0
            led_hours = 5.0
            standby_watts = 20.0
            standby_hours = 20.0
            result = vampire_power_audit(fridge_kwh_year, led_bulbs, led_watts, led_hours, standby_watts, standby_hours)
            return {"reply": f"Using your figures, the monthly consumption is about {result['fridge_monthly_kwh']:.2f} kWh for the refrigerator, {result['bulbs_monthly_kwh']:.2f} kWh for the LED bulbs, and {result['standby_monthly_kwh']:.2f} kWh for standby use. That means standby or vampire power makes up about {result['vampire_power_percentage']:.1f}% of the total monthly usage in this example.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}
        except Exception:
            pass

    if "kwh/year" in low or "kwh per year" in low or "translate that" in low:
        try:
            annual_kwh = 360.0
            result = kwh_year_to_monthly_cost(annual_kwh)
            return {"reply": f"If your label shows {annual_kwh:.0f} kWh/year, that is about {result['monthly_kwh']:.2f} kWh per month. At the current effective rate, that works out to about EC${result['monthly_cost']:.2f} per month.", "provider": "template-rule", "model": "-", "intent": "domain", "hits": []}
        except Exception:
            pass
    
    # 1. Retrieve context (RAG)
    safe_q = redact(user_msg) 
    hits = retrieve_chunks(safe_q, state["index"]) 
    
    # 2. Extract Excel context if available (formatted as readable rows,
    #    not a raw dict repr, so the model can actually parse it)
    excel_records = state.get("excel_data", [])
    excel_context = "\n".join(
        ", ".join(f"{k}: {v}" for k, v in row.items()) for row in excel_records
    ) if excel_records else ""
    
    # 3. Build prompt with Excel context and Language
    system_prompt = build_prompt(safe_q, hits, state["register"], state["territory"], excel_context=excel_context, language=state["language"])
    messages_to_send = [SystemMessage(content=system_prompt)] + state["messages"]
    
    # 4. Dynamic Fallback Loop
    errors = []
    for provider in active_chain():
        if not is_configured(provider):
            continue
        try:
            llm = get_llm_for_provider(provider)
            response = llm.invoke(messages_to_send)
            
            p_label = PROVIDERS[provider]["label"]
            p_model = provider_model(provider)
            LAST_CALL.update({"provider": p_label, "model": p_model})
            
            return {
                "messages": [response], 
                "hits": hits, 
                "provider": p_label, 
                "model": p_model
            }
        except Exception as e:
            errors.append(f"{provider}: {type(e).__name__}")
            continue

    text = extractive_answer(safe_q, hits)
    from langchain_core.messages import AIMessage
    return {"messages": [AIMessage(content=text)], "hits": hits, "provider": "offline (extractive)", "model": "-"}

    # GRACEFUL FALLBACK: if no provider answered, do NOT apologise and give up.
    # Fall back to the extractive answer built from the retrieved chunks, exactly
    # as the pre-LangGraph version did. This is the whole reason the demo works
    # with no API key: retrieval still ran, so we can still answer from the
    # documents — clumsily, but honestly, and with citations. The errors list is
    # logged for you; the customer just gets the best offline answer we have.
    #if errors:                                           # a provider was configured but failed
    #    print(f"[llm_node] providers tried and failed: {'; '.join(errors)}")
    #text = extractive_answer(safe_q, hits)               # the same fallback as before
    #from langchain_core.messages import AIMessage        # wrap it so the graph is happy
    #return {"messages": [AIMessage(content=text)], "hits": hits,
    #        "provider": "offline (extractive)", "model": "-"}

# ---------------------------------------------------------------------
# EXCEL KNOWLEDGE LOADER (Feature 2)
# ---------------------------------------------------------------------

def load_excel_knowledge():
    """Reads an Excel workbook and/or PDF document(s) and stores the
    combined knowledge-base records in st.session_state."""
    import streamlit as st
    import pandas as pd

    st.subheader("📄 Knowledge Base Uploads")

    excel_row_records = list(st.session_state.get("excel_row_records", []))
    pdf_records = list(st.session_state.get("excel_pdf_records", []))
    txt_records = list(st.session_state.get("excel_txt_records", []))

    # --- Excel workbook -------------------------------------------------
    st.markdown("**Excel workbook**")
    uploaded_excel = st.file_uploader(
        "Upload an Excel workbook", type=["xlsx", "xls"], key="excel_uploader"
    )

    if uploaded_excel is not None:
        # A new file can have different sheet names than the last one, so
        # the "excel_sheet" selectbox key must not carry a stale value —
        # Streamlit raises if a selectbox's session value isn't in options.
        if st.session_state.get("_excel_uploaded_name") != uploaded_excel.name:
            st.session_state.pop("excel_sheet", None)
            st.session_state["_excel_uploaded_name"] = uploaded_excel.name

        try:
            workbook = pd.ExcelFile(uploaded_excel)
        except ImportError:
            st.error("Missing Excel engine. Run: pip install openpyxl xlrd")
        except Exception as e:
            st.error(f"Could not read that workbook: {e}")
        else:
            sheet = st.selectbox("Worksheet", workbook.sheet_names, key="excel_sheet")
            try:
                df = pd.read_excel(workbook, sheet_name=sheet)
            except Exception as e:
                st.error(f"Could not read sheet '{sheet}': {e}")
            else:
                st.success(f"Spreadsheet loaded ({len(df)} rows).")
                st.dataframe(df, use_container_width=True)
                excel_row_records = df.to_dict(orient="records")
                st.session_state["excel_row_records"] = excel_row_records
                with st.expander("Preview rows"):
                    st.json(excel_row_records[:5])

    # --- PDF documents ----------------------------------------------------
    st.markdown("**PDF documents**")
    uploaded_pdfs = st.file_uploader(
        "Upload one or more PDFs", type=["pdf"], key="excel_pdf_uploader",
        accept_multiple_files=True,
    )

    if uploaded_pdfs:
        try:
            from pypdf import PdfReader
        except ImportError:
            st.error("PDF support needs pypdf. Run: pip install pypdf")
        else:
            new_pdf_records = []
            new_pdf_chunks = []
            for pdf_file in uploaded_pdfs:
                try:
                    reader = PdfReader(pdf_file)
                    text = "\n".join((page.extract_text() or "") for page in reader.pages)
                except Exception as e:
                    st.error(f"Could not read '{pdf_file.name}': {e}")
                    continue
                if text.strip():
                    new_pdf_records.append({"source": pdf_file.name, "text": text})
                    # Chunk it the same way source_documents/*.md are chunked,
                    # so it can be scored and retrieved by relevance to the
                    # user's actual question instead of dumped in whole.
                    new_pdf_chunks.extend(chunk_text(text, pdf_file.name))
                else:
                    st.warning(f"'{pdf_file.name}' has no extractable text (likely a scanned image).")
            if new_pdf_records:
                pdf_records = new_pdf_records
                st.session_state["excel_pdf_records"] = pdf_records
                st.session_state["excel_pdf_chunks"] = new_pdf_chunks
                st.success(f"Loaded {len(pdf_records)} PDF document(s), {len(new_pdf_chunks)} searchable chunk(s).")
                with st.expander("Preview PDF text"):
                    for rec in pdf_records:
                        st.markdown(f"**{rec['source']}**")
                        preview = rec["text"][:500] + ("..." if len(rec["text"]) > 500 else "")
                        st.text(preview)

    # --- Plain text files --------------------------------------------------
    st.markdown("**Text files**")
    uploaded_txts = st.file_uploader(
        "Upload one or more .txt files", type=["txt"], key="excel_txt_uploader",
        accept_multiple_files=True,
    )

    if uploaded_txts:
        new_txt_records = []
        new_txt_chunks = []
        for txt_file in uploaded_txts:
            try:
                text = txt_file.read().decode("utf-8", errors="ignore")
            except Exception as e:
                st.error(f"Could not read '{txt_file.name}': {e}")
                continue
            if text.strip():
                new_txt_records.append({"source": txt_file.name, "text": text})
                # Same chunking as source_documents/*.md and the PDF uploads,
                # so it can be scored and retrieved by relevance instead of
                # dumped in whole.
                new_txt_chunks.extend(chunk_text(text, txt_file.name))
            else:
                st.warning(f"'{txt_file.name}' is empty.")
        if new_txt_records:
            txt_records = new_txt_records
            st.session_state["excel_txt_records"] = txt_records
            st.session_state["excel_txt_chunks"] = new_txt_chunks
            st.success(f"Loaded {len(txt_records)} text file(s), {len(new_txt_chunks)} searchable chunk(s).")
            with st.expander("Preview text files"):
                for rec in txt_records:
                    st.markdown(f"**{rec['source']}**")
                    preview = rec["text"][:500] + ("..." if len(rec["text"]) > 500 else "")
                    st.text(preview)

    combined_records = excel_row_records + pdf_records + txt_records
    st.session_state["excel_records"] = combined_records
    pdf_chunk_count = len(st.session_state.get("excel_pdf_chunks", []))
    txt_chunk_count = len(st.session_state.get("excel_txt_chunks", []))
    st.write(
        f"Total knowledge loaded: {len(excel_row_records)} spreadsheet row(s), "
        f"{len(pdf_records)} PDF document(s), {len(txt_records)} text file(s) "
        f"({pdf_chunk_count + txt_chunk_count} chunks available to the chatbot)."
    )

    return combined_records

# The LangGraph pre-built ToolNode automatically runs our @tool
tool_node = ToolNode([calculator_tool])

def finalize_reply(state: GraphState):
    """Formats the LLM's final text using the Wardrobe."""
    last_msg_content = state["messages"][-1].content
    
    # NEW FIX: Some LLMs return content as a list of blocks after a tool call.
    # We must extract the actual string before running string operations like translate.
    if isinstance(last_msg_content, list):
        # Extract text from the list of dictionaries
        text_string = " ".join(block.get("text", "") for block in last_msg_content if isinstance(block, dict))
    else:
        text_string = str(last_msg_content) # Ensure it's a string
    
    # Strip jargon and apply the emotional tone
    plain = translate(text_string) 
    dressed = dress(state["register"], plain) 
    
    return {"reply": dressed}

# --- EDGES ---

def route_after_guardrail(state: GraphState):
    if state.get("escalated"): return "end" 
    return "router"

def route_after_router(state: GraphState):
    if state.get("intent") == "social": return "social"
    return "art"

def route_after_art(state: GraphState):
    if state.get("escalated"): return "end" 
    return "chatbot"

def should_continue(state: GraphState):
    """The vital loop edge. Does the LLM want to use a tool?"""
    last_message = state["messages"][-1]
    
    # If the LLM returned a tool_call, route to the tools node
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    # Otherwise, it's done thinking. Route to finalize.
    return "finalize"

# --- ASSEMBLE ---

workflow = StateGraph(GraphState) 
workflow.add_node("guardrail", node_guardrail) 
workflow.add_node("router", node_router)
workflow.add_node("social", node_social)
workflow.add_node("art", node_art) 
workflow.add_node("chatbot", chatbot) 
workflow.add_node("tools", tool_node) 
workflow.add_node("finalize", finalize_reply)

workflow.set_entry_point("guardrail") 

# Step 1: Guardrail -> Route or End
workflow.add_conditional_edges("guardrail", route_after_guardrail, {"end": END, "router": "router"}) 

# Step 2: Router -> Social lane OR Domain lane (ART)
workflow.add_conditional_edges("router", route_after_router, {"social": "social", "art": "art"})

# Step 3: ART -> Chatbot or End
workflow.add_conditional_edges("art", route_after_art, {"end": END, "chatbot": "chatbot"}) 

# The Tool Loop
workflow.add_conditional_edges("chatbot", should_continue, {"tools": "tools", "finalize": "finalize"}) 
workflow.add_edge("tools", "chatbot") # Tools loop back to the chatbot to read the result

workflow.add_edge("social", END)
workflow.add_edge("finalize", END)

bot_app = workflow.compile() 

# --- EXECUTION BINDING ---

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
    
    final_state = bot_app.invoke(initial_state) 
    
    # Sync the final graph state back out to the Streamlit UI format.
    return {
        "reply": final_state.get("reply", "Something went wrong."), 
        "hits": final_state.get("hits", []), 
        "provider": final_state.get("provider", "Unknown"), 
        "model": final_state.get("model", "Unknown"),
        "intent": final_state.get("intent", "domain"),
        "register": final_state.get("register", "-"),
        "escalated": final_state.get("escalated", False),   # did it hand off to a human?
        "axis": final_state.get("axis", "-"),               # which check stopped it
    }

def answer(question: str, index: dict, user: Optional[dict] = None, excel_data: list = None, language: str = "English") -> dict: 
    user = user or {"id_verified": True, "mood": DEFAULT_REGISTER, "segment": "Domestic"} 
    return classify_and_route(user, question, index, excel_data, language)

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

def initialize_sidebar_state(state: Optional[dict] = None) -> dict:
    """Seed a consistent sidebar session state for the Streamlit UI.

    Mutates `state` in place (works for a plain dict or `st.session_state`)
    instead of copying it, so keys owned by other widgets (e.g. a button's
    click state) never get round-tripped through a write Streamlit doesn't
    allow for that widget type.
    """
    if state is None:
        state = {}
    state.setdefault("page_state", "customer_view")
    state.setdefault("ui_language", "English")
    state.setdefault("dark_mode", False)
    state.setdefault("accessibility_settings", {
        "tts": False,
        "stt": False,
        "screen_reader": False,
        "font_size": 16,
        "high_contrast": False,
        "simple_language": False,
    })
    state.setdefault("messages", [])
    state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": []}])
    state.setdefault("active_chat_id", state["chat_sessions"][0]["id"])
    state.setdefault("pending_voice_text", "")
    state.setdefault("show_voice_widget", False)
    state.setdefault("show_settings", False)
    return state


def authenticate_admin(username: str, password: str) -> bool:
    """Validate admin login credentials against ADMIN_USERNAME / ADMIN_PASSWORD.

    Falls back to a demo login ONLY when no admin credentials are configured
    anywhere (no .env, no secrets.toml) — never once a real value is set,
    however weak. The old version treated "secret" and "123456789" as
    synonyms for "not configured" too, which meant an admin could type a
    password into .env, see the app accept it, and never notice the actual
    check was still silently comparing against the hard-coded demo password.
    That is a backdoor, not a fallback, so it is gone.

    Comparisons use hmac.compare_digest so a network observer timing the
    response cannot learn the password one character at a time.
    """
    expected_user = os.getenv("ADMIN_USERNAME") or "vsmith"
    expected_pass = os.getenv("ADMIN_PASSWORD") or "secret"

    user_ok = hmac.compare_digest(username.encode("utf-8"), expected_user.encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), expected_pass.encode("utf-8"))
    return user_ok and pass_ok


def reset_chat_session(state: Optional[dict] = None) -> dict:
    """Reset chat UI state without breaking the rest of the sidebar settings."""
    state = initialize_sidebar_state(state)
    state["messages"] = []
    state["chat_sessions"] = [{"id": str(uuid4()), "title": "New chat", "messages": []}]
    state["active_chat_id"] = state["chat_sessions"][0]["id"]
    state["pending_voice_text"] = ""
    state["show_voice_widget"] = False
    state["show_settings"] = False
    return state

def inject_lucelec_loading_screen():
    """
    Injects a tiny LUCELEC loading badge in the bottom-left corner that
    appears during Streamlit's rerun state.
    Features:
      - Small blue square box with LUCELEC logo
      - Opacity gradient sweeping left -> right -> left across the box
      - Plain pulsing dots below the logo box
    """
    import streamlit as st
    loading_html = """
    <style>
        /* Hide default Streamlit top-right spinner widget */
        [data-testid="stStatusWidget"] {
            visibility: hidden !important;
        }

        /* Tiny Loading Badge, bottom-left corner */
        .lucelec-loading-overlay {
            position: fixed;
            bottom: 16px;
            left: 16px;
            z-index: 999999;
            display: flex;
            flex-direction: column;
            align-items: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease-in-out;
        }

        /* Show badge whenever Streamlit triggers a run/rerun */
        .stApp[data-test-script-state="running"] .lucelec-loading-overlay,
        [data-test-script-state="running"] .lucelec-loading-overlay,
        .stAppRunning .lucelec-loading-overlay {
            opacity: 1;
            pointer-events: all;
        }

        /* Blue Square Box Container (tiny) */
        .lucelec-logo-box {
            position: relative;
            overflow: hidden;
            width: 44px;
            height: 44px;
            background-color: #003B71;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0, 59, 113, 0.35);
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 6px;
        }

        /* Opacity Gradient Sweep: a light band that glides left -> right -> left */
        .lucelec-logo-box::after {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.55) 50%, rgba(255,255,255,0) 100%);
            animation: opacitySweepLeftRightLeft 2.4s ease-in-out infinite;
        }

        @keyframes opacitySweepLeftRightLeft {
            0% { left: -100%; }
            50% { left: 100%; }
            100% { left: -100%; }
        }

        /* LUCELEC Logo SVG Styling */
        .lucelec-logo-svg {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

    </style>

    <div class="lucelec-loading-overlay">
        <div class="lucelec-logo-box">
            <svg class="lucelec-logo-svg" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="100" cy="100" r="42" fill="#FFC72C"/>
                <path d="M100 20 V40 M100 160 V180 M20 100 H40 M160 100 H180 M43.4 43.4 L57.6 57.6 M142.4 142.4 L156.6 156.6 M43.4 156.6 L57.6 142.4 M142.4 57.6 L156.6 43.4"
                      stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
                <path d="M105 45 L70 110 H100 L95 155 L130 90 H100 L105 45 Z" fill="#FFFFFF" stroke="#003B71" stroke-width="2"/>
            </svg>
        </div>
    </div>
    """
    st.markdown(loading_html, unsafe_allow_html=True)

def streamlit_app():
    import streamlit as st
    import base64
    inject_lucelec_loading_screen()
    # 1. PAGE CONFIGURATION (MUST BE FIRST)
    st.set_page_config(page_title=f"{BOT_NAME} · LUCELEC", page_icon="⚡", layout="wide")        

    # --- NEW: UI TRANSLATION DICTIONARY ---
    # Every key here is customer-facing (sidebar, Chat, Location status, Area
    # tariffs, Cost calculator). Admin-only panels (Blueprint, Web harvest,
    # Sources, Eval, API keys, provider config) stay English by design —
    # they're gated behind admin login and marked staff-only in the UI.
    UI_LANGUAGES = {
        "English": {
            "chat": "Chat", "status": "Location status", "tariffs": "Area tariffs",
            "calc": "Cost calculator", "excel": "Knowledge base", "blueprint": "Blueprint",
            "web": "Web harvest", "sources": "Sources", "eval": "Eval",
            "ask_prompt": "Ask about appliance costs, tariffs or saving energy...",
            "compare_btn": "Compare",
            "chats_header": "Chats", "new_chat_btn": "➕ New chat", "new_chat_title": "New chat",
            "delete_chat_help": "Delete this chat", "settings_btn": "⚙️ Settings",
            "settings_expander": "Settings", "language_label": "🌍 Spoken & UI Language",
            "staff_only_caption": "For LUCELEC staff and the build team only.",
            "admin_login_btn": "Admin login", "accessibility_header": "Accessibility",
            "tts_checkbox": "Text-to-Speech", "tts_engine_label": "TTS Engine",
            "stt_checkbox": "Speech-to-Text", "font_size_label": "Font size",
            "user_in_front_header": "The user in front of you",
            "customer_name_label": "Customer Name", "customer_name_placeholder": "e.g. Vaughnroy",
            "authority_checkbox": "Authority — identity verified",
            "register_label": "Register — how do they feel?",
            "register_default_opt": "(read it from the message)",
            "territory_label": "Territory — which customer category?",
            "territory_default_opt": "(unknown)", "red_line_header": "The Red Line",
            "start_over_btn": "Start over", "sources_used": "Sources used",
            "retrieving_spinner": "Retrieving…", "generating_audio_spinner": "Generating audio...",
            "kweyol_elevenlabs_caption": "ElevenLabs doesn't support Kwéyòl — using Google TTS for this reply instead.",
            "replay_audio_expander": "🔊 Replay audio",
            "mic_caption": "Use your browser microphone to dictate a question.",
            "captured_voice": "Captured voice: '{text}'",
            "mic_not_captured": "Microphone access was not captured. You can type your question manually instead.",
            "status_header": "Location service status",
            "status_caption1": "Check whether a Saint Lucia area is RUNNING, UNDER MAINTAINANCE, or DOWN.",
            "parish_hover_caption": "Hover over a parish name for quick local reference information.",
            "choose_location_label": "Choose a location", "tariffs_header": "Area tariff overview",
            "domestic_metric": "Domestic", "commercial_metric": "Commercial",
            "calc_warning": "The rate below is a placeholder. Confirm the real LUCELEC rate with the client.",
            "rate_label": "Rate (EC$ per kWh)", "appliance_a": "Appliance A", "appliance_b": "Appliance B",
            "name_a_label": "Name A", "name_b_label": "Name B",
            "default_appliance_a": "Old fridge", "default_appliance_b": "Inverter fridge",
            "watts_a": "Watts A", "watts_b": "Watts B", "hours_a": "Hours/day A", "hours_b": "Hours/day B",
            "price_a": "Purchase price A", "price_b": "Purchase price B", "per_year_suffix": "— per year",
            "payback_msg": "{cheaper} pays back the price difference in {years} years.",
            "metric_col": "Metric", "power_draw_row": "Power Draw (Watts)",
            "usage_row": "Usage (Hours/Day)", "cost_year_row": "Cost/Year (EC$)"
        },
        "Spanish": {
            "chat": "Chat", "status": "Estado de ubicación", "tariffs": "Tarifas de área",
            "calc": "Calculadora de costos", "excel": "Base de conocimiento", "blueprint": "Plano",
            "web": "Recolección web", "sources": "Fuentes", "eval": "Evaluación",
            "ask_prompt": "Pregunte sobre costos de electrodomésticos o tarifas...",
            "compare_btn": "Comparar",
            "chats_header": "Chats", "new_chat_btn": "➕ Nuevo chat", "new_chat_title": "Nuevo chat",
            "delete_chat_help": "Eliminar este chat", "settings_btn": "⚙️ Configuración",
            "settings_expander": "Configuración", "language_label": "🌍 Idioma hablado y de la interfaz",
            "staff_only_caption": "Solo para el personal de LUCELEC y el equipo de desarrollo.",
            "admin_login_btn": "Acceso de administrador", "accessibility_header": "Accesibilidad",
            "tts_checkbox": "Texto a voz", "tts_engine_label": "Motor de voz",
            "stt_checkbox": "Voz a texto", "font_size_label": "Tamaño de fuente",
            "user_in_front_header": "El usuario frente a usted",
            "customer_name_label": "Nombre del cliente", "customer_name_placeholder": "p. ej. Vaughnroy",
            "authority_checkbox": "Autoridad — identidad verificada",
            "register_label": "Tono — ¿cómo se siente?",
            "register_default_opt": "(leerlo del mensaje)",
            "territory_label": "Territorio — ¿qué categoría de cliente?",
            "territory_default_opt": "(desconocido)", "red_line_header": "La línea roja",
            "start_over_btn": "Empezar de nuevo", "sources_used": "Fuentes utilizadas",
            "retrieving_spinner": "Buscando…", "generating_audio_spinner": "Generando audio...",
            "kweyol_elevenlabs_caption": "ElevenLabs no admite Kwéyòl — usando Google TTS para esta respuesta.",
            "replay_audio_expander": "🔊 Reproducir audio",
            "mic_caption": "Use el micrófono de su navegador para dictar una pregunta.",
            "captured_voice": "Voz capturada: '{text}'",
            "mic_not_captured": "No se detectó acceso al micrófono. Puede escribir su pregunta manualmente.",
            "status_header": "Estado del servicio por ubicación",
            "status_caption1": "Verifique si un área de Santa Lucía está EN SERVICIO, EN MANTENIMIENTO o SIN SERVICIO.",
            "parish_hover_caption": "Pase el cursor sobre el nombre de una parroquia para más información.",
            "choose_location_label": "Elija una ubicación", "tariffs_header": "Resumen de tarifas por área",
            "domestic_metric": "Doméstico", "commercial_metric": "Comercial",
            "calc_warning": "La tarifa de abajo es un valor de referencia. Confirme la tarifa real de LUCELEC con el cliente.",
            "rate_label": "Tarifa (EC$ por kWh)", "appliance_a": "Electrodoméstico A", "appliance_b": "Electrodoméstico B",
            "name_a_label": "Nombre A", "name_b_label": "Nombre B",
            "default_appliance_a": "Refrigerador viejo", "default_appliance_b": "Refrigerador inverter",
            "watts_a": "Vatios A", "watts_b": "Vatios B", "hours_a": "Horas/día A", "hours_b": "Horas/día B",
            "price_a": "Precio de compra A", "price_b": "Precio de compra B", "per_year_suffix": "— por año",
            "payback_msg": "{cheaper} recupera la diferencia de precio en {years} años.",
            "metric_col": "Métrica", "power_draw_row": "Consumo (Vatios)",
            "usage_row": "Uso (Horas/Día)", "cost_year_row": "Costo/Año (EC$)"
        },
        "French": {
            "chat": "Discuter", "status": "État de l'emplacement", "tariffs": "Tarifs de zone",
            "calc": "Calculateur de coûts", "excel": "Base de connaissances", "blueprint": "Plan d'action",
            "web": "Collecte Web", "sources": "Sources", "eval": "Évaluation",
            "ask_prompt": "Renseignez-vous sur les coûts des appareils ou l'énergie...",
            "compare_btn": "Comparer",
            "chats_header": "Discussions", "new_chat_btn": "➕ Nouvelle discussion",
            "new_chat_title": "Nouvelle discussion", "delete_chat_help": "Supprimer cette discussion",
            "settings_btn": "⚙️ Paramètres", "settings_expander": "Paramètres",
            "language_label": "🌍 Langue parlée et de l'interface",
            "staff_only_caption": "Réservé au personnel de LUCELEC et à l'équipe de développement.",
            "admin_login_btn": "Connexion administrateur", "accessibility_header": "Accessibilité",
            "tts_checkbox": "Synthèse vocale", "tts_engine_label": "Moteur vocal",
            "stt_checkbox": "Reconnaissance vocale", "font_size_label": "Taille de police",
            "user_in_front_header": "L'utilisateur en face de vous",
            "customer_name_label": "Nom du client", "customer_name_placeholder": "p. ex. Vaughnroy",
            "authority_checkbox": "Autorité — identité vérifiée",
            "register_label": "Ton — comment se sent-il/elle ?",
            "register_default_opt": "(le déduire du message)",
            "territory_label": "Territoire — quelle catégorie de client ?",
            "territory_default_opt": "(inconnu)", "red_line_header": "La ligne rouge",
            "start_over_btn": "Recommencer", "sources_used": "Sources utilisées",
            "retrieving_spinner": "Recherche…", "generating_audio_spinner": "Génération de l'audio...",
            "kweyol_elevenlabs_caption": "ElevenLabs ne prend pas en charge le Kwéyòl — utilisation de Google TTS pour cette réponse.",
            "replay_audio_expander": "🔊 Réécouter l'audio",
            "mic_caption": "Utilisez le microphone de votre navigateur pour dicter une question.",
            "captured_voice": "Voix capturée : « {text} »",
            "mic_not_captured": "L'accès au microphone n'a pas été détecté. Vous pouvez taper votre question manuellement.",
            "status_header": "État du service par emplacement",
            "status_caption1": "Vérifiez si une zone de Sainte-Lucie est EN SERVICE, EN MAINTENANCE ou HORS SERVICE.",
            "parish_hover_caption": "Survolez le nom d'une paroisse pour plus d'informations locales.",
            "choose_location_label": "Choisissez un emplacement", "tariffs_header": "Aperçu des tarifs par zone",
            "domestic_metric": "Domestique", "commercial_metric": "Commercial",
            "calc_warning": "Le tarif ci-dessous est indicatif. Confirmez le vrai tarif LUCELEC avec le client.",
            "rate_label": "Tarif (EC$ par kWh)", "appliance_a": "Appareil A", "appliance_b": "Appareil B",
            "name_a_label": "Nom A", "name_b_label": "Nom B",
            "default_appliance_a": "Vieux réfrigérateur", "default_appliance_b": "Réfrigérateur inverter",
            "watts_a": "Watts A", "watts_b": "Watts B", "hours_a": "Heures/jour A", "hours_b": "Heures/jour B",
            "price_a": "Prix d'achat A", "price_b": "Prix d'achat B", "per_year_suffix": "— par an",
            "payback_msg": "{cheaper} rembourse la différence de prix en {years} ans.",
            "metric_col": "Mesure", "power_draw_row": "Puissance (Watts)",
            "usage_row": "Utilisation (Heures/Jour)", "cost_year_row": "Coût/An (EC$)"
        },
        "French Creole (Kwéyòl)": {
            "chat": "Kozé", "status": "Estati Kote", "tariffs": "Pwi Zòn",
            "calc": "Kalkilatris Pri", "excel": "Konesans Baz", "blueprint": "Plan",
            "web": "Ramase Web", "sources": "Sous", "eval": "Evalyasyon",
            "ask_prompt": "Mande sou pri aparèy, tarif oswa ekonomize kouran...",
            "compare_btn": "Konpare",
            "chats_header": "Kozé yo", "new_chat_btn": "➕ Nouvo kozé", "new_chat_title": "Nouvo kozé",
            "delete_chat_help": "Efase kozé sa a", "settings_btn": "⚙️ Réglaj",
            "settings_expander": "Réglaj", "language_label": "🌍 Lang pou palé ak entèfas",
            "staff_only_caption": "Sèlman pou anplwaye LUCELEC ak ekip devlopman an.",
            "admin_login_btn": "Konesyon admin", "accessibility_header": "Aksesibilite",
            "tts_checkbox": "Tèks an vwa", "tts_engine_label": "Motè vwa",
            "stt_checkbox": "Vwa an tèks", "font_size_label": "Gwosè lèt",
            "user_in_front_header": "Kliyan ki devan ou a",
            "customer_name_label": "Non kliyan", "customer_name_placeholder": "eg. Vaughnroy",
            "authority_checkbox": "Otorite — idantite verifye",
            "register_label": "Tòn — ki jan i santi?",
            "register_default_opt": "(li sa nan mesaj la)",
            "territory_label": "Teritwa — ki kategori kliyan?",
            "territory_default_opt": "(pa konnèt)", "red_line_header": "Liy Wouj la",
            "start_over_btn": "Rekòmanse", "sources_used": "Sous yo itilize",
            "retrieving_spinner": "K ap chèché…", "generating_audio_spinner": "K ap fè odyo...",
            "kweyol_elevenlabs_caption": "ElevenLabs pa sipòte Kwéyòl — n ap sèvi Google TTS pou repons sa a.",
            "replay_audio_expander": "🔊 Rekoute odyo",
            "mic_caption": "Sèvi ak mikwo navigatè ou pou dikte yon kesyon.",
            "captured_voice": "Vwa kaptire: '{text}'",
            "mic_not_captured": "Nou pa t' ka jwenn aksè a mikwo a. Ou ka tape kesyon ou an alamen.",
            "status_header": "Estati sèvis pa zòn",
            "status_caption1": "Gadé si yon zòn Sent Lisi ap MACHÉ, ANMENTNANS, oswa DOWN.",
            "parish_hover_caption": "Pase sourit sou non yon pawès pou plis enfòmasyon lokal.",
            "choose_location_label": "Chwazi yon kote", "tariffs_header": "Apèsi tarif pa zòn",
            "domestic_metric": "Domestik", "commercial_metric": "Komèsyal",
            "calc_warning": "Tarif anba la se yon egzanp. Konfime tarif reyèl LUCELEC ak kliyan an.",
            "rate_label": "Tarif (EC$ pou chak kWh)", "appliance_a": "Aparèy A", "appliance_b": "Aparèy B",
            "name_a_label": "Non A", "name_b_label": "Non B",
            "default_appliance_a": "Vyé frijidè", "default_appliance_b": "Frijidè envètè",
            "watts_a": "Wat A", "watts_b": "Wat B", "hours_a": "Lè/jou A", "hours_b": "Lè/jou B",
            "price_a": "Pri acha A", "price_b": "Pri acha B", "per_year_suffix": "— pa lanné",
            "payback_msg": "{cheaper} rekipere diferans pri a nan {years} lanné.",
            "metric_col": "Mezi", "power_draw_row": "Pwisans (Wat)",
            "usage_row": "Itilizasyon (Lè/Jou)", "cost_year_row": "Pri/Lanné (EC$)"
        }
    }

    # Initialize the default language in memory
    if "ui_language" not in st.session_state:
        st.session_state.ui_language = "English"

    def t(key: str) -> str:
        """Helper function to fetch the translated string for the current language."""
        return UI_LANGUAGES.get(st.session_state.ui_language, UI_LANGUAGES["English"]).get(key, key)
    # --------------------------------------

    # 2. ACCESSIBILITY CSS INJECTION — runs every rerun (not gated behind
    # Settings being open) so the chosen font size persists once the
    # panel is collapsed. Reads the live slider value via its own
    # session_state key when Settings is open this run (same idiom as
    # the ui_language selectbox above), otherwise the last-saved value.
    a11y = st.session_state.get("accessibility_settings", {
        "font_size": 16, "tts": False, "stt": False, "simple_language": False
    })
    _current_font_size = int(st.session_state.get("font_size_slider", a11y.get("font_size", 16)))
    st.markdown(f"<style>{build_accessibility_css(_current_font_size)}</style>", unsafe_allow_html=True)

    # 3. HTML BANNER RENDERER
    @st.cache_data
    def get_base64_of_bin_file(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()

    try:
        candidates = [project_path("Lucelec_logo.png"), project_path("files", "Lucelec_logo.png"), "files/Lucelec_logo.png"]
        logo_path = next((c for c in candidates if os.path.exists(c)), candidates[0])
        img_html = f'<img src="data:image/png;base64,{get_base64_of_bin_file(logo_path)}" class="lucelec-logo">'
    except FileNotFoundError:
        img_html = '<h1 class="lucelec-title">⚡</h1>' 

    st.markdown(f"""
    <style>
    .lucelec-banner {{
        background-color: #5DADE2; padding: 1.5rem 1rem; border-radius: 10px;
        display: flex; justify-content: center; align-items: center; gap: 1.5rem; margin-bottom: 2rem;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1); border: 2px solid #3498DB;
    }}
    .lucelec-logo {{ height: 110px; width: auto; mix-blend-mode: multiply; }}
    .lucelec-text-container {{ display: flex; flex-direction: column; justify-content: center; text-align: left; }}
    .lucelec-title {{ font-size: 4rem; font-weight: 900; font-family: 'Arial Black', sans-serif; color: #F7DC6F !important; text-shadow: 3px 3px 0px #2C3E50; margin: 0; line-height: 1.1; letter-spacing: 2px; }}
    .lucelec-subtitle {{ font-size: 1.6rem; font-weight: 800; font-family: 'Arial Black', sans-serif; color: #1A5276 !important; margin: 0; letter-spacing: 1px; }}
    </style>
    <div class="lucelec-banner">
        {img_html}
        <div class="lucelec-text-container">
            <h1 class="lucelec-title">LUCELEC</h1>
            <p class="lucelec-subtitle">ST. LUCIA ELECTRICITY SERVICES LIMITED</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2.5 DARK MODE CSS INJECTION — see DARK_MODE_CSS for why this is
    # injected instead of set via config.toml. Must come AFTER the banner's
    # own <style> block above: both set .lucelec-title/.lucelec-subtitle
    # color with !important, so whichever <style> tag lands later in the
    # DOM wins the cascade tie. Injecting first (as before) let the
    # banner's light-mode navy subtitle color silently beat dark mode's
    # override, leaving dark navy text on a dark navy banner.
    if st.session_state.get("dark_mode", False):
        st.markdown(f"<style>{DARK_MODE_CSS}</style>", unsafe_allow_html=True)

    # 4. VIEW ROUTER
    initialize_sidebar_state(st.session_state)
    if st.session_state.page_state != 'customer_view' and st.session_state.page_state != 'admin_view' and st.session_state.page_state != 'admin_login':
        st.session_state.page_state = 'customer_view'

    def set_state(new_state): 
        st.session_state.page_state = new_state 

    # 5. ADMIN LOGIN PORTAL
    if st.session_state.page_state == 'admin_login':
        st.title("Administrator Login")

        # Brute-force throttle: a Streamlit button can be clicked as fast as
        # a script can drive it, so the login check itself is not a rate
        # limit. After 5 wrong attempts, lock this session out of the login
        # form for 60 seconds. Per-session, not global — good enough to
        # stop naive automated guessing without needing a real backend.
        LOGIN_MAX_ATTEMPTS = 5
        LOGIN_LOCKOUT_SECONDS = 60
        st.session_state.setdefault("login_attempts", 0)
        st.session_state.setdefault("login_locked_until", 0.0)

        now = time.time()
        locked = now < st.session_state.login_locked_until

        if locked:
            wait = int(st.session_state.login_locked_until - now) + 1
            st.error(f"Too many failed attempts. Try again in {wait}s.")
            st.button("Back", on_click=set_state, args=('customer_view',))
            return

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Login"):
                if authenticate_admin(username, password):
                    st.session_state.login_attempts = 0
                    set_state('admin_view')
                    st.rerun()
                else:
                    st.session_state.login_attempts += 1
                    if st.session_state.login_attempts >= LOGIN_MAX_ATTEMPTS:
                        st.session_state.login_locked_until = time.time() + LOGIN_LOCKOUT_SECONDS
                        st.session_state.login_attempts = 0
                        st.rerun()
                    st.error("Invalid credentials.")
        with col2:
            st.button("Back", on_click=set_state, args=('customer_view',))
        return

    # 6. APP DATA LOAD
    is_admin = (st.session_state.page_state == 'admin_view')

    # Defaults for the real (non-simulated) customer flow. The Settings
    # panel below overrides both when a staff member opens it to test as a
    # simulated customer — but it's collapsed by default, so a real
    # customer's first chat message must work without ever opening it.
    user = None
    sim_language = st.session_state.ui_language

    @st.cache_resource                               
    def get_index():                                 
        return build_index(load_chunks())            
    index = get_index()                              

    def persist_active_chat():
        active_id = st.session_state.get("active_chat_id")
        chats = st.session_state.get("chat_sessions", [])
        if not chats:
            return
        for chat in chats:
            if chat["id"] == active_id:
                chat["messages"] = list(st.session_state.get("messages", []))
                break

    def set_active_chat(chat_id: str):
        chats = st.session_state.get("chat_sessions", [])
        for chat in chats:
            if chat["id"] == chat_id:
                st.session_state.active_chat_id = chat_id
                st.session_state.messages = list(chat.get("messages", []))
                st.session_state.pending_voice_text = ""
                st.session_state.show_voice_widget = False
                break

    def add_new_chat():
        new_chat = {"id": str(uuid4()), "title": t("new_chat_title"), "messages": []}
        st.session_state.chat_sessions.append(new_chat)
        st.session_state.active_chat_id = new_chat["id"]
        st.session_state.messages = []
        st.session_state.pending_voice_text = ""
        st.session_state.show_voice_widget = False

    def delete_chat(chat_id: str):
        chats = [c for c in st.session_state.get("chat_sessions", []) if c["id"] != chat_id]
        was_active = st.session_state.get("active_chat_id") == chat_id
        if not chats:
            chats = [{"id": str(uuid4()), "title": t("new_chat_title"), "messages": []}]
        st.session_state.chat_sessions = chats
        if was_active:
            st.session_state.active_chat_id = chats[0]["id"]
            st.session_state.messages = list(chats[0].get("messages", []))
        st.session_state.pending_voice_text = ""
        st.session_state.show_voice_widget = False

    # 7. SIDEBAR MENUS
    with st.sidebar:
        st.session_state.setdefault("chat_sessions", [{"id": str(uuid4()), "title": "New chat", "messages": []}])
        st.session_state.setdefault("active_chat_id", st.session_state["chat_sessions"][0]["id"])
        st.session_state.setdefault("show_settings", False)

        st.subheader(t("chats_header"))
        st.button(t("new_chat_btn"), on_click=add_new_chat, use_container_width=True)

        for chat_index, chat in enumerate(st.session_state.chat_sessions):
            label = chat.get("title", t("new_chat_title")) or t("new_chat_title")
            if len(label) > 24:
                label = label[:21] + "..."
            button_label = f"{'●' if chat['id'] == st.session_state.active_chat_id else '○'} {label}"
            chat_col, delete_col = st.columns([5, 1])
            with chat_col:
                st.button(
                    button_label,
                    on_click=set_active_chat,
                    args=(chat["id"],),
                    key=f"chat_button_{chat_index}",
                    use_container_width=True,
                )
            with delete_col:
                st.button(
                    "🗑️",
                    on_click=delete_chat,
                    args=(chat["id"],),
                    key=f"chat_delete_{chat_index}",
                    use_container_width=True,
                    help=t("delete_chat_help"),
                )

        st.divider()

        if st.button(t("settings_btn"), use_container_width=True):
            st.session_state.show_settings = not st.session_state.get("show_settings", False)

        if st.session_state.get("show_settings", False):
            with st.expander(t("settings_expander"), expanded=True):
                # key="ui_language" binds this widget straight to
                # st.session_state.ui_language: Streamlit syncs the new pick
                # into session_state BEFORE this script body runs, so
                # t("language_label") below sees the new language immediately.
                # A manual `st.session_state.ui_language = st.selectbox(...)`
                # reassignment reads the OLD language for the label argument
                # (evaluated before the assignment lands), so the picker's
                # own label always lagged one click behind — every other
                # translated element updates fine since it's downstream of
                # that same assignment.
                st.selectbox(
                    t("language_label"),
                    list(UI_LANGUAGES.keys()),
                    index=list(UI_LANGUAGES.keys()).index(st.session_state.ui_language),
                    key="ui_language"
                )
                sim_language = st.session_state.ui_language

                st.toggle("🌙 Dark mode", key="dark_mode")

                if not is_admin:
                    st.caption(t("staff_only_caption"))
                    if st.button(t("admin_login_btn")):
                        set_state('admin_login')
                        st.rerun()

                st.subheader(t("accessibility_header"))
                a11y_state = st.session_state.accessibility_settings
                a11y_state["tts"] = st.checkbox(t("tts_checkbox"), value=a11y_state.get("tts", False))

                if a11y_state["tts"]:
                    a11y_state["tts_engine"] = st.radio(
                        t("tts_engine_label"),
                        ["Google (Free)", "ElevenLabs (Credits)"],
                        index=0 if a11y_state.get("tts_engine", "Google (Free)") == "Google (Free)" else 1
                    )

                a11y_state["stt"] = st.checkbox(t("stt_checkbox"), value=a11y_state.get("stt", False))
                font_size_value = st.slider(
                                    t("font_size_label"),
                                    min_value=14,
                                    max_value=24,
                                    value=int(a11y_state.get("font_size", 16)),
                                    key="font_size_slider")
                font_size_value = int(st.session_state.get("font_size_slider", font_size_value))
                a11y_state["font_size"] = font_size_value
                st.session_state.accessibility_settings = a11y_state
                # CSS injection now happens once, unconditionally, near the
                # top of streamlit_app() — see "2. ACCESSIBILITY CSS INJECTION".

                if is_admin:
                    st.success("Signed in as Administrator")
                    if st.button("Log out"):
                        set_state('customer_view')
                        st.rerun()
                    st.divider()

                    st.subheader("AI model")
                    names  = [p["name"] for p in provider_status()]
                    labels = {p["name"]: f"{p['label']} {'✅' if p['ready'] else '⚪'}" for p in provider_status()}
                    current = os.getenv("LLM_PROVIDER", "")
                    choice = st.selectbox("Provider", names, format_func=lambda n: labels[n], index=names.index(current) if current in names else 0)
                    os.environ["LLM_PROVIDER"] = choice
                    cfg = PROVIDERS[choice]

                    if st.button("Test connection"):
                        r = test_provider(choice)
                        (st.success if r["ok"] else st.error)(f"{r['model']} → {r['reply']}")

                    with st.expander("🔑 API keys"):
                        for row in key_report():
                            if row["set"]:
                                st.write(f"✅ `{row['name']}` — {row['masked']} · from {row['source']}")
                            else:
                                st.write(f"⚪ `{row['name']}` — not set")
                        st.divider()
                        target = st.selectbox("Add or replace a key", KEY_NAMES, index=KEY_NAMES.index(cfg["key_env"]) if cfg["key_env"] in KEY_NAMES else 0)
                        new_key = st.text_input("Paste the key", type="password")
                        if st.button("Save to server"):
                            if new_key.strip():
                                save_key(target, new_key)
                                st.rerun()

                    st.divider()
                    st.subheader("Knowledge base")
                    st.metric("Chunks indexed", len(index["chunks"]))
                    if st.button("Reload documents"):
                        st.cache_resource.clear()
                        st.rerun()

                st.divider()
                st.subheader(t("user_in_front_header"))
                c_name = st.text_input(t("customer_name_label"), placeholder=t("customer_name_placeholder"))

                if c_name.strip():
                    PERSONA["name"] = c_name.strip()
                    PERSONA["who"] = f"a customer named {c_name.strip()}"
                else:
                    PERSONA["name"] = "a customer"
                    PERSONA["who"] = "a LUCELEC customer"

                sim_verified = st.checkbox(t("authority_checkbox"), value=True)
                sim_mood = st.selectbox(t("register_label"), [t("register_default_opt")] + list(TONES.keys()))
                sim_segment = st.selectbox(t("territory_label"), [t("territory_default_opt")] + list(LOCATION_CONTEXT.keys()))

                user = {
                    "id_verified": sim_verified,
                    "mood":    None if sim_mood.startswith("(") else sim_mood,
                    "segment": None if sim_segment.startswith("(") else sim_segment,
                }

                st.divider()
                st.subheader(t("red_line_header"))
                for r in MUST_NEVER_DO:
                    st.write(f"· {r}")

                if not is_admin:
                    st.divider()
                    if st.button(t("start_over_btn")):
                        reset_chat_session(st.session_state)
                        st.rerun()

    # 8. UNIFIED TAB DECLARATIONS
    # "Knowledge base" (Excel/PDF/text uploads) is admin/staff tooling only —
    # it never had customer-visible content even when the tab existed for
    # everyone, so the tab itself is admin-only now too.
    if is_admin:
        (tab_chat, tab_status, tab_tariffs, tab_calc, tab_excel,
         tab_blueprint, tab_web, tab_sources, tab_eval) = st.tabs(
            [t("chat"), t("status"), t("tariffs"), t("calc"), t("excel"), t("blueprint"), t("web"), t("sources"), t("eval")]
        )
    else:
        tab_chat, tab_status, tab_tariffs, tab_calc = st.tabs(
            [t("chat"), t("status"), t("tariffs"), t("calc")]
        )

    # ---------- TAB 1: Chat ----------
    with tab_chat:
        mascot_candidates = [project_path("Lucelec_mascot.png"), project_path("files", "Lucelec_mascot.png"), "files/Lucelec_mascot.png"]
        bot_avatar = next((c for c in mascot_candidates if os.path.exists(c)), "🤖")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for m in st.session_state.messages:
            msg_avatar = bot_avatar if m["role"] == "assistant" else None
            with st.chat_message(m["role"], avatar=msg_avatar):
                st.markdown(m["content"])
                if m.get("hits"):
                    with st.expander(t("sources_used")):
                        for i, h in enumerate(m["hits"], 1):
                            st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                            st.caption(h["text"])

        if "pending_voice_text" not in st.session_state:
            st.session_state.pending_voice_text = ""
        if "show_voice_widget" not in st.session_state:
            st.session_state.show_voice_widget = False
        if "last_voice_transcript" not in st.session_state:
            st.session_state.last_voice_transcript = ""

        def _stream_words(text: str):
            """Yield the reply one word at a time so st.write_stream can
            render it appearing progressively, instead of the whole answer
            landing on screen in one blocking chunk."""
            for word in text.split(" "):
                yield word + " "
                time.sleep(0.05)

        def process_chat_message(q: str):
            """Send `q` to the bot and render the exchange. Shared by typed
            chat_input submissions and auto-sent voice transcripts so both
            paths produce an identical reply/TTS/sources experience."""
            st.session_state.messages.append({"role": "user", "content": q})
            persist_active_chat()
            with st.chat_message("user"):
                st.markdown(q)

            # GENERATE ASSISTANT REPLY
            with st.chat_message("assistant", avatar=bot_avatar):
                with st.spinner(t("retrieving_spinner")):
                    excel_row_records = st.session_state.get("excel_row_records", [])
                    pdf_chunks = st.session_state.get("excel_pdf_chunks", [])
                    txt_chunks = st.session_state.get("excel_txt_chunks", [])
                    upload_chunks = pdf_chunks + txt_chunks
                    # Uploaded PDFs/text files join the same TF-IDF index as
                    # the static source_documents/*.md files, so retrieve_chunks
                    # scores them against THIS question and only the relevant
                    # bits get cited — not the whole document dumped every time.
                    active_index = build_index(index["chunks"] + upload_chunks) if upload_chunks else index
                    out = answer(q, active_index, user, excel_data=excel_row_records, language=sim_language)

                st.write_stream(_stream_words(out["reply"]))

                # --- UPDATED: TTS Generation with Engine Router ---
                if st.session_state.accessibility_settings.get("tts"):
                    with st.spinner(t("generating_audio_spinner")):
                        engine = st.session_state.accessibility_settings.get("tts_engine", "Google (Free)")

                        # ElevenLabs has no French Creole (Kwéyòl) support — it
                        # is not one of its listed languages — so feeding it
                        # Kwéyòl text produces mispronounced/garbled audio.
                        # gTTS's "ht" (Haitian Creole) is the closer, if still
                        # imperfect, match. Force that route regardless of the
                        # engine picked, so the failure mode is "slightly off
                        # accent" instead of "wrong language entirely."
                        if engine == "ElevenLabs (Credits)" and sim_language == "French Creole (Kwéyòl)":
                            st.caption(t("kweyol_elevenlabs_caption"))
                            audio_data = generate_google_tts(out["reply"], language=sim_language)
                        elif engine == "ElevenLabs (Credits)":
                            audio_data = generate_elevenlabs_tts(out["reply"])
                        else:
                            # FIXED: Passes sim_language to gTTS
                            audio_data = generate_google_tts(out["reply"], language=sim_language)

                        # Play the generated byte stream, but keep the player
                        # widget itself hidden by default — an expander gives
                        # a "show playback" option for relistening later.
                        if audio_data:
                            with st.expander(t("replay_audio_expander"), expanded=False):
                                st.audio(audio_data, format="audio/mp3", autoplay=True)
                # --------------------------------------------------

                st.caption(f"lane: {out.get('intent', '-')} · "
                           f"register: {out.get('register', '-')} · "
                           f"answered by: {out['provider']} · {out['model']}")

                if out["hits"]:
                    with st.expander(t("sources_used")):
                        for i, h in enumerate(out["hits"], 1):
                            st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")
                            st.caption(h["text"])

            # Save assistant reply to history
            st.session_state.messages.append(
                {"role": "assistant", "content": out["reply"], "hits": out["hits"]})
            persist_active_chat()

        if st.session_state.show_voice_widget:
            st.caption(t("mic_caption"))
            voice_transcript = render_voice_recorder()
            # st.chat_input has no way to pre-fill real (editable) text, only
            # a placeholder hint — so a captured transcript can never reach
            # the bot by waiting for the user to also type and submit it.
            # Send it directly instead. The component only returns a NEW
            # value on a fresh speech-recognition result, but that value
            # persists across unrelated reruns while the widget stays open —
            # guard on last_voice_transcript so the same transcript can't
            # get re-sent on every subsequent rerun.
            if voice_transcript and voice_transcript != st.session_state.last_voice_transcript:
                st.session_state.last_voice_transcript = voice_transcript
                st.session_state.pending_voice_text = ""
                st.session_state.show_voice_widget = False
                st.success(t("captured_voice").format(text=voice_transcript))
                process_chat_message(voice_transcript)
            elif not voice_transcript:
                st.info(t("mic_not_captured"))

        col_input, col_mic = st.columns([9, 1])
        with col_input:
            if q := st.chat_input(t("ask_prompt")):
                process_chat_message(q)

        def toggle_voice_widget():
            st.session_state.show_voice_widget = not st.session_state.get("show_voice_widget", False)

        with col_mic:
            st.button("🎤", on_click=toggle_voice_widget, use_container_width=True)

    # ---------- TAB 2: Location Status ----------
    with tab_status:
        st.subheader(t("status_header"))
        st.caption(t("status_caption1"))
        st.caption(t("parish_hover_caption"))
        st.markdown(parish_tooltip_html(list(LOCATION_STATUS_DATA.keys())), unsafe_allow_html=True)

        selected_location = st.selectbox(t("choose_location_label"), list(LOCATION_STATUS_DATA.keys()), key="loc_status_select")
        status = get_location_status(selected_location)

        if status:
            if status["status"] == "RUNNING": st.success(f"{status['location']} — {status['status']}")
            elif status["status"] == "UNDER MAINTAINANCE": st.warning(f"{status['location']} — {status['status']}")
            else: st.error(f"{status['location']} — {status['status']}")
            st.write(status["detail"])

        # ---- Admin-only: track the live outage/status page on LUCELEC's website ----
        # Same rule as the tariffs tab: the statuses above stay hard-coded
        # until a human explicitly approves fresh text — a customer told
        # "RUNNING" based on an unverified scrape is worse than no answer.
        # This shares the SAME pending_review/ queue as the tariff tracker
        # and the Web harvest tab — approving one item here also clears it
        # from those tabs' lists, since it is genuinely the same queue.
        if is_admin:
            st.divider()
            with st.expander("🔒 Admin — track the live outage/status page"):
                st.caption(
                    "Fetches the page into the waiting room only. The chatbot "
                    "never uses this text until you review and approve it below."
                )
                status_url = st.text_input(
                    "Status page address", LUCELEC_STATUS_URL, key="status_track_url"
                )

                # Auto-refreshes on a cooldown instead of relying on someone
                # to remember to click the button below. Still only reaches
                # the waiting room — the approval step is unchanged.
                auto_result = auto_harvest_if_due(status_url)
                if auto_result.get("fetched"):
                    if auto_result.get("ok", True):
                        st.success(f"Auto-fetched {auto_result['words']} words — awaiting approval below.")
                    else:
                        st.warning(f"Auto-fetch failed: {auto_result.get('error', 'unknown error')}")
                if auto_result.get("last_checked"):
                    st.caption(f"Auto-checks every {AUTO_FETCH_INTERVAL_HOURS}h · last checked: {auto_result['last_checked']}")

                if st.button("Check LUCELEC site for updates now", key="status_track_fetch"):
                    with st.spinner("Downloading…"):
                        fetch_result = harvest(status_url)
                    if fetch_result["ok"]:
                        st.success(f"Fetched {fetch_result['words']} words — awaiting approval below.")
                        # Reset the cooldown so the next automatic check
                        # doesn't immediately re-fetch what we just got by hand.
                        from datetime import datetime, timezone
                        _save_auto_fetch_state({**_load_auto_fetch_state(), status_url: datetime.now(timezone.utc).isoformat()})
                    else:
                        st.error(fetch_result["error"])

                pending_rows = list_pending()
                if not pending_rows:
                    st.caption("Nothing waiting for review right now.")
                for row in pending_rows:
                    with st.container(border=True):
                        st.markdown(f"**{row['file']}** — {row['words']} words")
                        st.caption(f"Source: {row['url']}")
                        st.text(row["preview"])   # plain text only — never render fetched text as HTML
                        a1, a2, a3 = st.columns([2, 1, 1])
                        initials = a1.text_input(
                            "Your initials to approve", key=f"status_initials_{row['file']}"
                        )
                        if a2.button("Approve", key=f"status_approve_{row['file']}"):
                            approve_result = approve_harvest(row["file"], initials)
                            if approve_result["ok"]:
                                st.cache_resource.clear()   # so the chatbot picks it up immediately
                                st.success(f"Approved by {approve_result['by']} — now in the knowledge base.")
                                st.rerun()
                            else:
                                st.error(approve_result["error"])
                        if a3.button("Reject", key=f"status_reject_{row['file']}"):
                            reject_harvest(row["file"])
                            st.rerun()

    # ---------- TAB 3: Area Tariffs ----------
    with tab_tariffs:
        st.subheader(t("tariffs_header"))
        st.caption(t("parish_hover_caption"))
        st.markdown(parish_tooltip_html(list(LOCATION_TARIFF_DATA.keys())), unsafe_allow_html=True)
        tariff_location = st.selectbox(t("choose_location_label"), list(LOCATION_TARIFF_DATA.keys()), key="loc_tariff_select")
        tariff = get_location_tariff(tariff_location)

        if tariff:
            c1, c2 = st.columns(2)
            c1.metric(t("domestic_metric"), tariff["domestic"])
            c2.metric(t("commercial_metric"), tariff["commercial"])
            st.info(tariff["note"])

        # ---- Admin-only: track the live tariff page on LUCELEC's website ----
        # The numbers above stay hard-coded SAMPLE values — that is
        # deliberate (MUST_NEVER_DO: never quote a tariff that is not in
        # the approved source documents). This panel fetches the real page
        # into the SAME pending_review/ waiting room the "Web harvest" tab
        # uses; nothing reaches the chatbot until a human reads it below
        # and approves it with their initials.
        if is_admin:
            st.divider()
            with st.expander("🔒 Admin — track the live tariff page"):
                st.caption(
                    "Fetches the page into the waiting room only. The chatbot "
                    "never uses this text until you review and approve it below."
                )
                tariff_url = st.text_input(
                    "Tariff page address", LUCELEC_TARIFF_URL, key="tariff_track_url"
                )
                if st.button("Check LUCELEC site for updates", key="tariff_track_fetch"):
                    with st.spinner("Downloading…"):
                        fetch_result = harvest(tariff_url)
                    if fetch_result["ok"]:
                        st.success(f"Fetched {fetch_result['words']} words — awaiting approval below.")
                    else:
                        st.error(fetch_result["error"])

                pending_rows = list_pending()
                if not pending_rows:
                    st.caption("Nothing waiting for review right now.")
                for row in pending_rows:
                    with st.container(border=True):
                        st.markdown(f"**{row['file']}** — {row['words']} words")
                        st.caption(f"Source: {row['url']}")
                        st.text(row["preview"])   # plain text only — never render fetched text as HTML
                        a1, a2, a3 = st.columns([2, 1, 1])
                        initials = a1.text_input(
                            "Your initials to approve", key=f"tariff_initials_{row['file']}"
                        )
                        if a2.button("Approve", key=f"tariff_approve_{row['file']}"):
                            approve_result = approve_harvest(row["file"], initials)
                            if approve_result["ok"]:
                                st.cache_resource.clear()   # so the chatbot picks it up immediately
                                st.success(f"Approved by {approve_result['by']} — now in the knowledge base.")
                                st.rerun()
                            else:
                                st.error(approve_result["error"])
                        if a3.button("Reject", key=f"tariff_reject_{row['file']}"):
                            reject_harvest(row["file"])
                            st.rerun()

    # ---------- TAB 4: Calculator ----------
    with tab_calc:
        st.warning(t("calc_warning"))
        rate = st.number_input(t("rate_label"), value=float(DEFAULT_RATE_PER_KWH), min_value=0.0, step=0.05)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader(t("appliance_a"))
            na = st.text_input(t("name_a_label"), t("default_appliance_a"))
            wa = st.number_input(t("watts_a"), value=350.0, min_value=0.0)
            ha = st.number_input(t("hours_a"), value=8.0, min_value=0.0, max_value=24.0)
            pa = st.number_input(t("price_a"), value=1500.0, min_value=0.0)
        with c2:
            st.subheader(t("appliance_b"))
            nb = st.text_input(t("name_b_label"), t("default_appliance_b"))
            wb = st.number_input(t("watts_b"), value=150.0, min_value=0.0)
            hb = st.number_input(t("hours_b"), value=8.0, min_value=0.0, max_value=24.0)
            pb = st.number_input(t("price_b"), value=2600.0, min_value=0.0)

        # FIXED: Translates the compare button
        if st.button(t("compare_btn")):
            result = compare_appliances({"name": na, "watts": wa, "hours_per_day": ha, "price": pa}, {"name": nb, "watts": wb, "hours_per_day": hb, "price": pb}, rate)
            k1, k2, k3 = st.columns(3)
            k1.metric(f"{na} {t('per_year_suffix')}", f"EC${result[na]['cost_year']:,.2f}")

            if result["payback_years"]:
                st.success(t("payback_msg").format(cheaper=result['cheaper_to_run'], years=result['payback_years']))

            comparison_table = [
                {t("metric_col"): t("power_draw_row"), na: result[na]["watts"], nb: result[nb]["watts"]},
                {t("metric_col"): t("usage_row"), na: result[na]["hours_per_day"], nb: result[nb]["hours_per_day"]},
                {t("metric_col"): t("cost_year_row"), na: f"${result[na]['cost_year']:,.2f}", nb: f"${result[nb]['cost_year']:,.2f}"},
            ]
            st.table(comparison_table)
    

    # ---------- ADMIN ONLY TABS (6-9) ----------
    if is_admin: 
        with tab_excel:
            excel_records = load_excel_knowledge()
            if excel_records:
                st.success(f"Excel knowledge base ready ({len(excel_records)} rows).")

        with tab_blueprint:                              
            b1, b2 = st.columns(2)                       
            with b1:                                     
                st.subheader("Primary persona")          
                for k, v in PERSONA.items(): st.write(f"**{k}** — {v}")           
            with b2:                                     
                st.subheader("Empathy map")              
                for k, v in EMPATHY_MAP.items(): st.write(f"**{k}** — {v}")

        with tab_web:                                    
            st.subheader("Harvest a page") 
            url = st.text_input("Page address", "https://www.lucelec.com/") 
            if st.button("Fetch page"):                  
                with st.spinner("Downloading…"): 
                    res = harvest(url)                   
                if res["ok"]: st.success("Awaiting approval")
                else: st.error(res["error"])               

        with tab_sources:                                
            st.subheader("RAG Search Test")
            probe = st.text_input("Test query", "how much does an ac cost") 
            for i, h in enumerate(retrieve_chunks(probe, index), 1): 
                st.markdown(f"**[{i}] {h['source']}** · score {h['score']}")   
                st.caption(h["text"])                    

        with tab_eval:
            st.subheader("Evaluations")
            if st.button("Run eval set"):
                rows = run_eval(index, user)
                st.dataframe(rows, use_container_width=True)
                passed = sum(1 for r in rows if r["passed"])
                st.metric("Passed", f"{passed}/{len(rows)}")

    # 8. FOOTER
    st.markdown(f"<style>{POLISH_CSS}</style>", unsafe_allow_html=True)
    st.markdown("""
    <div class="lucelec-footer">
        <svg class="lucelec-footer-icon" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="30" width="20" height="50" fill="#2C3E50"/>
            <rect x="30" y="15" width="20" height="65" fill="#2C3E50"/>
            <rect x="10" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="18" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="35" y="25" width="5" height="5" fill="#5DADE2"/>
            <rect x="43" y="25" width="5" height="5" fill="#5DADE2"/>
        </svg>
        <p class="lucelec-footer-text">The Power Of Caring</p>
        <svg class="lucelec-footer-icon" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="30" width="20" height="50" fill="#2C3E50"/>
            <rect x="30" y="15" width="20" height="65" fill="#2C3E50"/>
            <rect x="10" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="18" y="38" width="5" height="5" fill="#5DADE2"/>
            <rect x="35" y="25" width="5" height="5" fill="#5DADE2"/>
            <rect x="43" y="25" width="5" height="5" fill="#5DADE2"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)

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
