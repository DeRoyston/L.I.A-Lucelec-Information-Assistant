# L.I.A User Guide

*L.I.A — LUCELEC Information Assistant.*

This guide covers everyone who uses the app: customers chatting with L.I.A
(Part 1) and LUCELEC staff running it day to day (Part 2).

## Quick reference

| I want to... | Go to |
|---|---|
| Ask about an appliance, bill, or tariff | Chat tab |
| Check if my area has an outage | Location status tab |
| See domestic/commercial rates | Area tariffs tab |
| Compare two appliances' running cost | Cost calculator tab |
| Change language, dark mode, text size | Settings (sidebar) |
| Have replies read aloud | Settings → Accessibility → Text-to-Speech |
| Speak instead of type | 🎙️ button beside the chat box |
| Share a spreadsheet/PDF for L.I.A to reference | ➕ button beside the chat box |
| Log in as staff | "LUCELEC staff? Log in here" link on the start screen |
| Add/remove a staff account | Settings → Staff accounts *(staff only)* |
| Approve new website content | Web harvest tab *(staff only)* |
| Test which documents answer a query | Sources tab *(staff only)* |
| Run the quality checks | Eval tab *(staff only)* |

---

## Part 1 — Using L.I.A

### 1. Starting a conversation

The first screen asks a few quick questions before you reach the chat:

- **Spoken & UI Language** — English, Spanish, French, or French Creole (Kwéyòl). Everything L.I.A says will be in this language.
- **Dark mode** — a toggle, if you'd rather not use a bright screen.
- **Customer Name** — optional. If you give it, L.I.A will use it.
- **Register** *(how you're feeling)* — usually leave this on "(read it from the message)". L.I.A picks up your tone from what you actually type.
- **Territory** — **required**. Pick the category that best describes you: Domestic, Commercial, Industrial, Hotel/Tourism, Government/Public Sector, or Agricultural. This determines which rules and rates apply to your questions.

Press **Continue** to reach the chat.

> You don't have to get Territory right in the form. If you skip ahead and
> L.I.A asks you directly in the chat, just answer in plain words —
> "I'm a hotel," "domestic," "we're a business" — and it'll be understood.

### 2. What you can ask

L.I.A can help with:

- What an appliance costs to run (fridge, AC, water heater, and more)
- How to read an energy label or a bill
- Whether standby/vampire power is costing you anything
- General tariff and billing structure
- Energy-saving tips
- Whether your area is running normally, under maintenance, or has an outage

L.I.A will **not** guess at or confirm anything about your specific account —
your balance, a payment plan, a personal rate agreement. Those questions get
handed to the right LUCELEC desk instead of answered, on purpose: it's
built to never invent a number that isn't actually on file.

L.I.A also remembers the conversation as it goes — if it asks you a
follow-up question, you can just answer it directly and it'll understand
the context, the same as talking to a person.

### 3. Speaking instead of typing

Click the 🎙️ button beside the chat box. Speak your question; when it's
captured, it's sent automatically — no need to also type or press enter.

### 4. Hearing replies read aloud

Open **Settings** in the sidebar → **Accessibility** → turn on
**Text-to-Speech**. Choose the reading voice (Google, free, or ElevenLabs
if credits are configured). Each reply gets a small "🔊 Replay audio"
section underneath if you want to hear it again.

### 5. Sharing a document

Click the **➕** button beside the chat box to upload an Excel, PDF, or text
file (up to 25MB) — L.I.A will reference it alongside its normal knowledge
for the rest of that conversation. Useful for asking questions about your
own bill or a spreadsheet of appliance data.

### 6. Checking outage status

**Location status** tab → pick your parish from the dropdown. Shows
Running, Under Maintenance, or Down, plus a short note.

### 7. Looking up tariffs

**Area tariffs** tab → pick a location to see the domestic and commercial
rate figures on file, with a short explanatory note.

### 8. Comparing two appliances

**Cost calculator** tab → enter the wattage, hours-per-day, and price for
two appliances, plus the electricity rate. Press **Compare** for the
yearly running cost of each and which one pays for itself sooner.

### 9. Changing language, text size, or theme

All in **Settings** (sidebar) → **Accessibility**: dark mode, font size
(14–24), text-to-speech, speech-to-text. Language is its own dropdown at
the top of Settings.

### 10. Managing your conversation

The sidebar lists your chats. **➕ New chat** starts a fresh one; each chat
gets its own 🗑️ to delete it. Chats are titled automatically from your
first message.

---

## Part 2 — Staff & Administrator Guide

### 1. Logging in

From the start screen, click **"LUCELEC staff? Log in here."** Enter your
username and password. Five wrong attempts locks the form for 60 seconds.

Staff bypass the customer intake screen entirely and land straight in the
full app, with four extra tabs (below) and extra Settings sections.

### 2. Managing staff accounts

**Settings → Staff accounts** (visible once logged in as staff). Lists
every account; each has a 🗑️ to remove it (you can't remove your own
account or the last remaining one). **➕ Add staff account** creates a new
one — username, optional display name, password. Passwords are hashed,
never stored in plain text.

### 3. Choosing and testing the AI model

**Settings → AI model.** Pick which provider answers questions
(OpenAI/Gemini/Groq — ✅ means a key is configured and ready). **Test
connection** sends a real ping and shows the reply. **🔑 API keys**
lists every provider's key status (masked) and lets you paste in a new
one, saved to the server.

If a provider that was working suddenly isn't, two common causes: the
provider's free daily limit was reached (it'll auto-fall-back to the next
provider in the chain), or the underlying AI model was retired by the
provider (ask a developer to check — this has happened before).

### 4. Reloading the knowledge base

**Settings → Knowledge base** shows how many chunks are currently indexed.
Press **Reload documents** any time you've added a new file to
`source_documents/` on the server, or want to confirm a knowledge-base
change took effect.

### 5. Adding real website content (Web harvest)

L.I.A never uses website content until a human has read and approved it.
The flow, in the **Web harvest** tab (also reachable from the admin panel
inside **Area tariffs** and **Location status** for those specific pages):

1. Paste the page address and press **Check LUCELEC site for updates** (or
   let the automatic periodic check do it).
2. The fetched text lands in a waiting room — you'll see a preview and word
   count, never rendered as a live page, just plain text.
3. Type your initials and press **Approve** to add it to the live
   knowledge base immediately, or **Reject** to discard it.

Nothing reaches a customer's chat until this approval step happens.

### 6. Testing what L.I.A would retrieve (Sources tab)

Type any question into the **Sources** tab's test box to see exactly which
document chunks would be used to answer it, and their relevance score.
Useful for checking "why did/didn't L.I.A know that?" before assuming
something is broken.

### 7. Running the quality checks (Eval tab)

**Eval** tab → **Run eval set** runs a fixed list of test questions
(appliance questions, must-refuse account questions, small talk, and one
per reply tone) against a **fixed test customer**, not your own current
Settings — so the result is the same no matter who runs it or what their
Territory/Register happens to be set to. A score below "all passing" is
worth investigating before it reaches customers.

### 8. The Blueprint tab

Teaching/reference material — the design personas, empathy maps, and every
tone L.I.A can reply in, with a live sample of each. Not something you
edit day to day; useful for understanding the *why* behind how replies are
written.

### 9. Simulating a customer

**Settings → "The user in front of you."** The same Name/Register/
Territory fields the customer gate asks for — staff can change these to
test how L.I.A responds to a different kind of customer, without needing a
second browser session.

### 10. The Red Line

**Settings** shows, read-only, the hard rules L.I.A is built to never
break — no invented tariffs, no discussing a specific account, no wiring
or repair instructions, no promised refunds or outcomes. This isn't
configurable from the UI on purpose.
