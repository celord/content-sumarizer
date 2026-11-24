# content-sumarizer

Telegram bot that turns TikTok and X (Twitter) links into Obsidian notes. See `GLOSSARY.md` for vocabulary.

## Run it

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Get your chat id: message [@userinfobot](https://t.me/userinfobot), or send your bot a message and open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to read `message.chat.id` (groups have negative ids).
3. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN`, `ALLOWED_CHAT_IDS` and `VAULT_PATH`
   (absolute path of your Obsidian Vault). Then pick one option for each of the two model steps.
   `.env.example` has the exact values for each.

   | Step | Options |
   |---|---|
   | Analysis | Anthropic Haiku (default), NVIDIA NIM, OpenRouter, local Ollama |
   | Speech-to-text (videos without subtitles) | Groq Whisper (default), local Whisper |

4. Start it with API models only:

   ```sh
   docker compose up -d --build
   ```

   Or with local models on an NVIDIA GPU (tested on an RTX 3060 12 GB: Whisper uses about 2 GB,
   `qwen3:8b` about 7 GB). This needs the NVIDIA Container Toolkit.

   ```sh
   docker compose --profile local up -d --build
   # one-time model downloads, kept in Docker volumes:
   docker compose exec ollama ollama pull qwen3:8b
   docker compose exec whisper curl -X POST http://localhost:8000/v1/models/deepdml/faster-whisper-large-v3-turbo-ct2
   ```

   You can mix the two, for example local Whisper with NVIDIA NIM for Analysis.

Send a TikTok or X (Twitter) link to the bot from an allowed chat. X links are text tweets: the bot reads
the tweet (and any quoted tweet) through the public FxTwitter API and ignores attached media. It reacts with 👀, then replies with the title, tags and
Note path; the Note appears in `${VAULT_PATH}/${NOTE_FOLDER}/TikTok` or `.../Twitter`.

## Keep yt-dlp current

TikTok changes often, and old `yt-dlp` versions stop downloading ("Download failed" replies).
Dependabot opens a PR for each new `yt-dlp` release. After merging it, update the server:

```sh
git pull && docker compose up -d --build
```

To update by hand: `uv lock --upgrade-package yt-dlp`, commit `uv.lock`, then rebuild.

## Develop

```sh
uv run pytest
```
