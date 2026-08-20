# L.I.A — Status Report

*A plain-language summary for LUCELEC, prepared 2026-08-19.*

## What L.I.A does today

- **Appliance cost estimates** — works out what it costs to run a fridge, AC unit, water heater, and more, before a customer buys.
- **Tariff & billing basics** — explains how billing works in plain terms, without ever inventing a specific rate that isn't on file.
- **Outage & maintenance status** — looks up whether a parish is running normally, under maintenance, or affected by an outage.
- **Energy-saving guidance** — standby power, energy labels, and what actually moves the needle on a bill.
- **Real conversation, not a form** — remembers what was said earlier in the chat (new this week).
- **Knows its limits** — anything account-specific (balance, payment plans) is handed straight to a human desk, on purpose.

## Fixed this week (6 reports → 6 resolved)

1. **Assistant remembers the conversation.** The big one. Previously every message was treated as a brand-new, disconnected question — if L.I.A asked a follow-up and the customer answered it, the reply that came back had nothing to do with what was just said. It now keeps track of the last several exchanges.
2. **Replies picked up the wrong tone.** A worried, reassuring tone meant for billing concerns was showing up on plain greetings like "hi". Fixed.
3. **Customer category wasn't sticking.** If a customer answered "domestic" or "hotel" directly in chat, the account-type field in the background wasn't updating — could ask again unnecessarily. Fixed.
4. **Responses were quietly falling back to basic mode.** One AI provider had discontinued the specific model L.I.A was using; switched to a current model. Full responses are back.
5. **Internal quality checks weren't reliable.** The tool used to test answers before changes go live gave inconsistent results depending on who was logged in — now tests against a fixed scenario every time, and covers more ground.
6. **"What does L.I.A stand for?" had no answer.** Small gap — now correctly answers LUCELEC Information Assistant.

## Still open

- **Code isn't backed up off this machine yet.** Full version history exists locally; no off-machine backup configured. Recommend setting one up.
- **A finished feature is built but not switched on.** A "replay this audio" control for voice responses is complete and tested on a separate branch — just needs merging in.
- **One AI provider has a daily free-tier limit.** If Google Gemini's daily cap is hit, L.I.A automatically switches to a backup provider (Groq) — service doesn't stop.

---
*L.I.A — LUCELEC Information Assistant*
