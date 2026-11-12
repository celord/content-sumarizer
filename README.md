# content-sumarizer

Telegram bot that turns TikTok links into Obsidian notes. See `GLOSSARY.md` for vocabulary.

## Run it

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Get your chat id: message [@userinfobot](https://t.me/userinfobot), or send your bot a message and open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to read `message.chat.id` (groups have negative ids).
3. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN`, `ALLOWED_CHAT_IDS`, `ANTHROPIC_API_KEY`,
   `GROQ_API_KEY` and `VAULT_PATH` (absolute path of your Obsidian Vault).
4. Start it:

   ```sh
   docker compose up -d
   ```

Send a TikTok link to the bot from an allowed chat. It reacts with ⏳, then replies with the title, tags and
Note path; the Note appears in `${VAULT_PATH}/${NOTE_SUBFOLDER}`.

## Develop

```sh
uv run pytest
```
