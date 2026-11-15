# Telegram Study Buddy Bot

A Telegram bot that answers programming questions using an LLM (Groq, reached
through the OpenAI SDK). It remembers each conversation separately, so you can
ask follow-up questions, and it prints the token usage and estimated cost of
every single reply to the console.

Built for **Class 02 — Structured Outputs, Streaming and Your First Chatbot**
(AI Engineering Bootcamp, Assignment 3).

## What the bot does

- Replies to **every text message** with an LLM answer.
- Keeps a **separate conversation history for each chat**, identified by its
  Telegram chat id, and saves it to a JSON file so the history survives a restart.
- Trims each request to the system prompt plus the last *N* messages, so a long
  conversation never turns into an expensive request.
- `/start` greets you, `/reset` clears **only your own** history.
- Logs **tokens in, tokens out and an estimated cost in USD** for every reply.
- Shows Telegram's **"typing…" indicator** while the model is thinking.
- Survives API failures: a failed request is logged, you get a friendly message,
  and the bot keeps running.

## Setup

### 1. Create your bot with BotFather

1. Open Telegram and search for **@BotFather** (the one with the blue checkmark).
2. Send `/newbot`.
3. Send a **display name** for your bot, e.g. `My Study Buddy`.
4. Send a **username**, which must be unique and end in `bot`,
   e.g. `mehreen_study_buddy_bot`.
5. BotFather replies with a token that looks like
   `123456789:AAH...`. **Copy it** — this is your `TELEGRAM_BOT_TOKEN`.

Keep this token private. Anyone who has it controls your bot. If it ever leaks,
send `/revoke` to BotFather to get a new one.

### 2. Get a Groq API key

Create a free key at <https://console.groq.com/keys>. This is your
`GROQ_API_KEY`.

### 3. Clone the project and create the virtual environment

This project needs **Python 3.12** (3.15 is too new for some of these packages).

```powershell
git clone <your-repo-url>
cd class-02-telegram-bot
py -V:3.12 -m venv venv
venv\Scripts\activate
python -V          # should print Python 3.12.x
```

On macOS or Linux, use `python3.12 -m venv venv` and `source venv/bin/activate`.

### 4. Install the dependencies

```powershell
pip install -r requirements.txt
```

### 5. Create your .env file

Copy the example file and fill in the two values from steps 1 and 2:

```powershell
copy .env.example .env
```

Then open `.env` and paste your values:

```
TELEGRAM_BOT_TOKEN=123456789:AAH...your token from BotFather...
GROQ_API_KEY=gsk_...your key from the Groq console...
```

Every other setting in `.env.example` is optional and already has a sensible
default. `.env` is listed in `.gitignore`, so **it is never committed**.

### 6. Run the bot

```powershell
python run.py
```

You should see:

```
06:11:35 INFO     run | Secrets found: TELEGRAM_BOT_TOKEN=True GROQ_API_KEY=True
06:11:35 INFO     bot.application | Bot configured: model=openai/gpt-oss-20b ...
06:11:35 INFO     run | Bot is running. Press Ctrl+C to stop.
```

Now open your bot in Telegram (BotFather gave you a `t.me/...` link), send
`/start`, and start asking questions. Keep the terminal open — the bot only
works while `run.py` is running. Stop it with `Ctrl+C`.

## Commands

| Command  | What it does                                                   |
| -------- | -------------------------------------------------------------- |
| `/start` | Greets you and lists the commands.                             |
| `/reset` | Deletes your chat's history. Other chats are left untouched.    |
| *(any text)* | Gets an LLM answer that takes your recent messages into account. |

## How history works

The model itself has no memory — it only knows what we send it on each request.
So the bot keeps the conversation and resends the recent part every time.

- **One history per chat.** Histories are stored in a single JSON object keyed by
  the Telegram chat id, e.g. `{"123456789": [...], "987654321": [...]}`. A chat
  can only ever read its own key, so two users never see each other's messages.
- **Saved to disk.** The file lives at `data/telegram_histories.json`
  (configurable via `HISTORY_FILE`) and is written with `ensure_ascii=False`, so
  Urdu and Roman Urdu stay readable in the file instead of becoming `\uXXXX`.
- **Written atomically.** The data is written to a temporary file and then moved
  into place, so a crash in the middle of a write cannot corrupt your history.
- **Trimmed.** Each request is the system prompt plus the last
  `MAX_HISTORY_MESSAGES` messages (default 12). Older messages are dropped, which
  keeps every request cheap and predictable.
- **Only successful turns are stored.** The question and answer are saved
  together *after* the model replies, so a failed request never leaves a dangling
  question in your history.
- **The system prompt is not stored** in the file. It is added on the way out
  from `SYSTEM_PROMPT`, so changing the bot's personality in `.env` takes effect
  immediately for every chat.

## Token and cost logging

Every reply logs one line:

```
INFO  bot.handlers | chat=123456789 tokens_in=123 tokens_out=45 total=168 est_cost_usd=0.000023
```

- `tokens_in` comes from `response.usage.prompt_tokens`
- `tokens_out` comes from `response.usage.completion_tokens`
- `est_cost_usd` is `(tokens_in × input_price + tokens_out × output_price) / 1,000,000`

The two prices come from `INPUT_PRICE_PER_MILLION_TOKENS` and
`OUTPUT_PRICE_PER_MILLION_TOKENS` in `.env`. The defaults are example values —
check the current paid prices for your model at <https://groq.com/pricing>
and update them so the estimate is accurate.

## Project structure

```
bot/
  __init__.py       Package marker and version.
  config.py         Settings read from .env and validated at startup; fails loudly if a key is missing.
  history.py        ConversationStore: per-chat history, trimming, atomic JSON load/save.
  llm.py            StudyBuddyLlm: sends messages to the model, returns reply text + token usage + cost.
  handlers.py       Telegram handlers for /start, /reset and plain text, plus the "typing…" indicator.
  application.py    Wires settings, store, LLM and handlers into a ready-to-run Application.
run.py              Entry point: python run.py
tests/              Plain pytest tests for the history store and the settings.
requirements.txt    Dependencies.
.env.example        Template for .env — copy it, never commit the real one.
.gitignore          Keeps .env, data/ and venv/ out of git.
data/               Created on first run; holds telegram_histories.json (gitignored).
```

## Tests

The conversation store and the settings can be tested without a Telegram token
or an API key:

```powershell
python -m pytest
```

The tests check that each chat keeps its own history, that history is trimmed to
the last N messages, that Urdu text round-trips through JSON unchanged, that
`/reset` clears only the target chat, that a corrupted history file does not
crash the bot, and that a missing key produces a clear error.

## Screenshots

> Replace each placeholder below with your own screenshot. Save the image files
> in a `screenshots/` folder next to this README, then the links will work.

### 1. A normal conversation (with a follow-up question)

![Conversation with the bot](screenshots/01-conversation.png)

### 2. The `/start` command

![The /start greeting](screenshots/02-start.png)

### 3. `/reset` — before and after, showing the bot forgot

![Before and after /reset](screenshots/03-reset.png)

### 4. The terminal showing the token and cost logs

![Token logs in the terminal](screenshots/04-token-logs.png)

## Notes on secrets

- `.env` is gitignored and no key is ever written to a log. On startup the bot
  logs only *whether* each secret was found (`TELEGRAM_BOT_TOKEN=True`), never
  the value.
- `data/` is gitignored too, because conversation histories contain real
  messages.
- Before pushing, run `git status` and make sure neither `.env` nor
  `data/telegram_histories.json` appears in the list.
