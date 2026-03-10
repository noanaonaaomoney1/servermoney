# Multi-Guild Economy Bot

Discord-as-a-Database (DaaB) implementation for multi-guild economy and management.

## Features
- **DaaB Persistence**: Stores all guild data in hidden Discord channels using JSON attachments.
- **Economy**: `/balance`, `/daily`, `/work`, `/pay`, `/leaderboard`.
- **Shop**: `/product-add`, `/buy`, etc. Support for role rewards and DM delivery.
- **Leveling**: Message-based XP gain with configurable rates.
- **Gambling**: `/coinflip`, `/slot`.
- **Admin**: Audit logging, tax configuration, currency naming, and more.

## Deployment on Render
1. Create a new **Web Service** or **Background Worker** on Render.
2. Connect your GitHub repository.
3. Set Environment Variable:
   - `DISCORD_TOKEN`: Your bot token.
4. Render will use the `Dockerfile` to build and run the bot.

*Note: Since this bot uses Discord channels for persistence, it is "stateless" from the server's perspective, making it perfect for Render's ephemeral disk.*
