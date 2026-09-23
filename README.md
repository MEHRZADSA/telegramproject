# Wage Manager Telegram Bot

A simple Telegram bot to manage employee wages, bonuses and fines **with mutual confirmation**.

Employees send a **photo** or **text** as proof of work → you approve or reject it and set the wage amount.  
Then the **employee must also Accept or Decline**. Only after both sides agree is the money added.

Same rule applies to bonuses and fines – everything is mutual. Both sides can always see the balance and history.

---

## Features

| Who        | What they can do                                      |
|------------|-------------------------------------------------------|
| **Employee** | Send photo / text as work proof<br>Accept or Decline proposed wage/bonus/fine<br>/balance<br>/history |
| **Admin**    | Approve / Reject with buttons<br>Set wage amount manually<br>/register, /list, /bonus, /fine |

---

## Quick Setup

### 1. Create a Telegram Bot

1. Open Telegram and talk to [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the **token** (looks like `123456:ABC-DEF...`)

### 2. Get your Telegram User ID

1. Talk to [@userinfobot](https://t.me/userinfobot) or [@getidsbot](https://t.me/getidsbot)
2. Copy your numeric ID (e.g. `123456789`)

### 3. Install & Configure

```bash
# Clone / copy the folder, then:
cd wage_bot

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Linux / macOS
# or:  venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create config file
cp .env.example .env
```

Edit the `.env` file:

```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_IDS=123456789
```

You can put several admin IDs separated by commas: `ADMIN_IDS=111,222,333`

### 4. Run the bot

```bash
python bot.py
```

Leave the terminal open. The bot is now online.

---

## How to use

### Register an employee

1. Employee opens the bot and sends `/start`
2. Bot shows their Telegram ID (e.g. `987654321`)
3. Employee tells you the ID
4. You run:

```
/register 987654321 John Doe
```

Employee receives a confirmation and can start working.

### Employee sends work proof

Just send a **photo** (with optional caption) or a **text message**.

You (admin) immediately receive the content with two buttons:

- ✅ **Approve** → bot asks you for the amount → type e.g. `50` or `75.5`
- ❌ **Reject** → employee is notified

### Give bonus or fine

```
/bonus John 20 Extra effort
/fine John 10 Late arrival
```

Name matching is case-insensitive and works with multi-word names.

### Useful commands

| Command              | Who      | Description                     |
|----------------------|----------|---------------------------------|
| `/start`             | Everyone | Welcome + show your ID          |
| `/balance`           | Employee | Current balance                 |
| `/history`           | Employee | Last 15 transactions            |
| `/register <id> <name>` | Admin | Register new employee         |
| `/list`              | Admin    | All employees + balances        |
| `/bonus <name> <amt> [note]` | Admin | Add bonus                 |
| `/fine <name> <amt> [note]`  | Admin | Apply fine                  |
| `/help`              | Everyone | Show available commands         |
| `/cancel`            | Admin    | Cancel entering amount          |

---

## Data storage

Everything is stored in a local SQLite file: `wage_bot.db`  
No extra database server needed. You can back it up simply by copying the file.

---

## Tips

- Keep the bot running on a cheap VPS, Raspberry Pi, or your own computer (use `screen` / `tmux` or a systemd service).
- You can have multiple admins by listing several IDs in `ADMIN_IDS`.
- The bot only works in **private chat** (not groups) for simplicity and privacy.

---

## Troubleshooting

| Problem                        | Solution                                      |
|--------------------------------|-----------------------------------------------|
| Bot doesn't answer             | Make sure `python bot.py` is running          |
| "Admin only" message           | Check that your ID is in `ADMIN_IDS`          |
| Employee not notified          | They must press `/start` at least once        |
| Name not found for bonus/fine  | Use exact name from `/list`                   |

Enjoy managing wages easily! 💰
