# Accounting Bot

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</div>

<div align="center">
  <h3>🤖 Smart Telegram Bot for User Accounting Management</h3>
  <p>Advanced webhook processing system with interactive buttons and smart routing</p>
</div>

---

## Features

- 🔄 **Automatic Webhook Processing**: Receives and processes `user_created` and `user_updated` events
- 📍 **Smart Routing**: Sends messages to each admin's dedicated topic (auto-created)
- ⚡ **Advanced Filtering**: Sends messages only under specific conditions (expire increase ≥7 days or status change to on_hold)
- 🎮 **Interactive Buttons**: Track payment status and add to settlement list with inline buttons
- 💾 **Local Database**: Stores snapshots and accounting information
- 👥 **Auto Admin Registration**: Automatically registers admins and creates topics when they first appear
- 🔘 **Button-Based UI**: No commands needed - everything works with inline buttons

## Installation

### 1. Clone the Project

```bash
git clone https://github.com/MatinDehghanian/accounting_bot.git
cd accounting_bot
```

### 2. Automatic Setup

```bash
chmod +x setup.sh
./setup.sh
```

### 3. Configuration

Edit the `.env` file:

```bash
# Telegram Bot Token (get from @BotFather)
BOT_TOKEN=1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# Webhook Secret (optional)
WEBHOOK_SECRET=your_webhook_secret_here

# Fallback chat for admins (REQUIRED - your forum group ID)
FALLBACK_CHAT_ID=-1001234567890
FALLBACK_TOPIC_ID=

# Panel API Settings (for syncing admins)
PANEL_API_URL=https://your-panel.com
PANEL_USERNAME=admin
PANEL_PASSWORD=your_password

# Server Settings
HOST=0.0.0.0
PORT=8080
DEBUG=False
```

### 4. Run with Docker (Recommended)

```bash
# Create .env file first
cp .env.example .env
# Edit .env with your settings
nano .env

# Build and run with Docker
docker-compose up -d

# View logs
docker-compose logs -f accounting-bot
```

### 5. Run without Docker (Alternative)

```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python main.py
```

## Usage

### Button-Based Interface

The bot uses **inline buttons** instead of commands. Just send any message to the bot and you'll see the main menu:

**Main Menu Options:**
- 📊 **Statistics** - View system stats and admin count
- 👥 **Admin List** - See all registered admins and their topics
- 🔄 **Sync Admins** - Fetch admins from Panel API and create topics
- ⚡ **Toggle Sync** - Enable/disable processing of user_updated events
- ⚙️ **Settings** - Configure and manage bot settings
- 📖 **Help** - How the bot works
- ℹ️ **About** - Bot information

### Automatic Admin Topic Creation

When an admin creates or updates a user through the panel:

1. Bot receives the webhook event
2. If it's a new admin, bot automatically:
   - Registers the admin
   - Creates a dedicated forum topic for them
3. Sends the notification to the admin's topic

### Webhook Setup in Panel

In your panel's webhook settings:

```
URL: https://your-server.com/webhook
Secret: your_webhook_secret_here (optional)
```

## Message Structure

### user_created
Always sent:

```
🧾 Accounting | user_created

👤 User: username (id: 123)  
👮 Admin: admin_name (tg_id: 987654321)

Details:
⚡ Status: active
📊 Data Limit: 10.0 GB
📅 Expire: 1403/12/15 - 14:30
🕐 Created: 1403/11/20 - 10:15
```

### user_updated  
Only sent when:
- Expiry increased by at least 7 days
- Status changed to `on_hold`

## Interactive Buttons

Each message includes 3 buttons:

- **✅ Paid**: Mark payment as received
- **❌ Unpaid**: Mark as not paid  
- **➕ Add to Settlement**: Add to settlement list

Clicking any button updates the message and records the result.

## Database Structure

- `users_snapshot`: Latest user state snapshots
- `payments`: Payment status for each user
- `settlement_list`: Users requiring settlement
- `admin_topics`: Admin to topic mappings (auto-created)
- `audit_log`: Log of all operations

## API Endpoints

- `POST /webhook` - Receive panel webhooks
- `GET /health` - System health status
- `GET /stats` - System statistics

## Important Notes

1. **Forum Group**: Add bot as admin to a forum-enabled group
2. **Auto Topics**: Topics are created automatically for each admin
3. **Fallback**: Set `FALLBACK_CHAT_ID` to your main group ID
4. **Enable Sync**: Use the "Enable Sync" button before user_updated events work
5. **Logs**: All operations are recorded in audit_log

## Troubleshooting

### "Bot not found" error
- Check bot token
- `/start` the bot

### "Chat not found" error  
- Verify Chat ID
- Add bot to the group as admin
- Check bot permissions

### user_updated messages not sending
- Enable sync using the button in bot menu
- Check trigger conditions (7+ days expire increase or on_hold status change)

### Topics not being created
- Make sure the group has forum topics enabled
- Bot needs admin permissions with "Manage Topics" privilege
- Check FALLBACK_CHAT_ID is correctly set to the forum group ID
- Verify the group ID starts with -100
- Run "Sync Admins" to create topics for existing admins

## Docker Deployment

Docker is the **recommended** way to run the bot:

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# 2. Build and run
docker-compose up -d

# 3. View logs
docker-compose logs -f accounting-bot

# 4. Stop
docker-compose down

# 5. Rebuild after changes
docker-compose up -d --build
```

### Docker without Compose

```bash
# Build image
docker build -t accounting-bot .

# Run container
docker run -d \
  --name accounting-bot \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  accounting-bot
```

## Updating

### Quick Update (Recommended)

```bash
chmod +x update.sh
./update.sh
```

The update script will:
- Backup your `.env` and database
- Pull latest changes from git
- Rebuild and restart (Docker or venv)
- Show recent logs

### Manual Update

**Docker:**
```bash
git pull origin main
docker-compose down
docker-compose up -d --build
```

**Venv:**
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
# Restart the bot (Ctrl+C and run again, or restart systemd service)
sudo systemctl restart accounting-bot
```

## Support

For questions and issues:

- 📋 **Issues**: [Report Issue or Suggestion](https://github.com/PasarGuard/accounting-bot/issues)
- 💬 **Discussions**: [General Discussions](https://github.com/PasarGuard/accounting-bot/discussions)

## Contributing

We welcome community contributions! 

- 🤝 [Contributing Guide](CONTRIBUTING.md)
- 🐛 [Report Bug](https://github.com/PasarGuard/accounting-bot/issues/new?template=bug_report.md)
- ✨ [Feature Request](https://github.com/PasarGuard/accounting-bot/issues/new?template=feature_request.md)

## License

This project is released under the [MIT License](LICENSE).

---

<div align="center">
  <p>Made with ❤️</p>
  <p>⭐ If this project was helpful, show your support by giving it a star</p>
</div>
