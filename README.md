# AURA - AI Girlfriend Telegram Bot

**Stage 2**: Personality System + Free LLM Integration

## Current Features
- Age gate (18+)
- 2 Characters:
  - **AURA** 💕 – Caring, romantic + naughty (Hinglish)
  - **Riya** 🔥 – Bold, spicy & teasing
- Real AI chat using free LLMs (Groq or OpenRouter)
- Conversation history (remembers last ~8 exchanges)
- /character, /clear, /help, /about
- Typing indicator
- Fallback replies if no API key
- Fixed for Python 3.12+ / Termux event loop issue

## Setup on Termux (Android) – Clean way

### 1. Install basics (agar pehle se nahi kiya)
```bash
pkg update && pkg upgrade -y
pkg install python git -y
pip install --upgrade pip
```

### 2. Clean extract (important)
```bash
cd ~/storage/downloads
rm -rf aura-bot
unzip botbygrok.zip -d aura-bot
cd aura-bot
```

### 3. Install packages
```bash
pip install -r requirements.txt
```

### 4. Create clean .env
```bash
cp .env.example .env
nano .env
```

**Correct format (no extra spaces, no quotes needed):**
```
BOT_TOKEN=1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```

**Galat format mat daalna** (jaise comments same line pe, ya "BOT_TOKEN = ..." with spaces around = sometimes issues create karta hai).

Save: `Ctrl+O` → Enter → `Ctrl+X`

### 5. Free API keys kaise lein

**Groq (Recommended – fast & free):**
1. Browser mein https://console.groq.com kholo
2. Google/GitHub se login
3. Left side **API Keys** → Create API Key
4. Copy karke `.env` mein `GROQ_API_KEY=` ke aage paste

**OpenRouter (optional):**
https://openrouter.ai → Keys → Create

### 6. Run the bot
```bash
python bot/main.py
```

Agar sahi hai to dikhega:
```
Starting AURA Bot (Stage 2 – Personality + Free LLM)...
Groq API key found ✓
Bot is running... Press Ctrl+C to stop.
```

Telegram pe bot ko `/start` bhejo.

## Commands
| Command     | Description                  |
|-------------|------------------------------|
| /start      | Start / Restart              |
| /character  | Change girlfriend            |
| /clear      | Clear chat history           |
| /help       | Help                         |
| /about      | About the bot                |

## Common Errors & Fixes

**1. `There is no current event loop`**
→ Is zip mein already fix hai. Naya zip use karo.

**2. `Python-dotenv could not parse statement`**
→ `.env` file galat format mein hai. `nano .env` kholo aur clean KEY=value format use karo. Extra text/comments hatado.

**3. Bot Stage 1 dikha raha hai**
→ Purana main.py chal raha hai. Clean extract karo (upar wala step 2).

**4. API key nahi mili**
→ Fallback replies aayenge. Real AI ke liye GROQ_API_KEY daalo.

## Background mein chalane ke liye
```bash
nohup python bot/main.py > bot.log 2>&1 &
```

## Next Stage
Stage 4: Image support (placeholder selfies) (bot restart ke baad bhi history rahegi)
