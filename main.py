import asyncio
import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv

from webhook_receiver import app, db, telegram_bot
from api_client import PanelAPIClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Accounting Bot...")
    
    # Initialize database
    await db.init_db()
    
    # Initialize telegram bot
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables")
        raise ValueError("BOT_TOKEN is required")
    
    await telegram_bot.init(token=bot_token)
    
    # Set fallback chat/topic
    telegram_bot.fallback_chat_id = os.getenv('FALLBACK_CHAT_ID')
    telegram_bot.fallback_topic_id = os.getenv('FALLBACK_TOPIC_ID')
    telegram_bot.backup_topic_id = os.getenv('BACKUP_TOPIC_ID')
    
    # Initialize Panel API client if credentials provided
    panel_url = os.getenv('PANEL_API_URL')
    panel_username = os.getenv('PANEL_USERNAME')
    panel_password = os.getenv('PANEL_PASSWORD')
    
    if panel_url and panel_username and panel_password:
        telegram_bot.api_client = PanelAPIClient(
            base_url=panel_url,
            username=panel_username,
            password=panel_password
        )
        logger.info(f"📡 Panel API client configured for: {panel_url}")
    else:
        logger.warning("⚠️ Panel API credentials not configured - admin sync disabled")
    
    # Create backup topic if not exists
    await create_backup_topic_if_needed()
    
    # Start telegram bot polling in background
    polling_task = asyncio.create_task(start_telegram_polling())
    
    logger.info("✅ Accounting Bot started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Accounting Bot...")
    polling_task.cancel()
    
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    
    if telegram_bot.bot:
        await telegram_bot.bot.session.close()
    
    logger.info("✅ Shutdown complete")


async def create_backup_topic_if_needed():
    """Create backup topic for automated messages if not exists"""
    try:
        chat_id = telegram_bot.fallback_chat_id
        
        if not chat_id or not chat_id.lstrip('-').isdigit():
            logger.warning("⚠️ Cannot create backup topic - FALLBACK_CHAT_ID not set correctly")
            return
        
        # Check if backup topic already exists in database
        backup_topic_id = await db.get_sync_status("backup_topic_id")
        
        if backup_topic_id:
            telegram_bot.backup_topic_id = backup_topic_id
            logger.info(f"📂 Using existing backup topic: {backup_topic_id}")
            return
        
        # Check if provided via env
        if telegram_bot.backup_topic_id:
            await db.set_sync_status("backup_topic_id", telegram_bot.backup_topic_id)
            logger.info(f"📂 Using configured backup topic: {telegram_bot.backup_topic_id}")
            return
        
        # Create new backup topic
        try:
            topic = await telegram_bot.bot.create_forum_topic(
                chat_id=int(chat_id),
                name="📦 Auto Backups",
                icon_custom_emoji_id=None
            )
            telegram_bot.backup_topic_id = str(topic.message_thread_id)
            await db.set_sync_status("backup_topic_id", telegram_bot.backup_topic_id)
            logger.info(f"📂 Created backup topic: {telegram_bot.backup_topic_id}")
            
            # Send welcome message to backup topic
            await telegram_bot.bot.send_message(
                chat_id=int(chat_id),
                message_thread_id=int(telegram_bot.backup_topic_id),
                text="📦 <b>Auto Backup Topic</b>\n\nAutomated backup messages and system notifications will be posted here.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Could not create backup topic: {e}")
            
    except Exception as e:
        logger.error(f"Error in create_backup_topic_if_needed: {e}")


async def send_backup_message(message: str, file_path: str = None):
    """Send a message to the backup topic, optionally with a file"""
    try:
        chat_id = telegram_bot.fallback_chat_id
        topic_id = telegram_bot.backup_topic_id
        
        if not chat_id or not topic_id:
            logger.warning("Cannot send backup message - backup topic not configured")
            return False
        
        kwargs = {
            'chat_id': int(chat_id),
            'message_thread_id': int(topic_id),
            'parse_mode': 'HTML'
        }
        
        if file_path:
            from aiogram.types import FSInputFile
            document = FSInputFile(file_path)
            kwargs['document'] = document
            kwargs['caption'] = message
            await telegram_bot.bot.send_document(**kwargs)
        else:
            kwargs['text'] = message
            await telegram_bot.bot.send_message(**kwargs)
        
        return True
    except Exception as e:
        logger.error(f"Error sending backup message: {e}")
        return False


async def start_telegram_polling():
    """Start telegram bot polling"""
    try:
        if telegram_bot.dp:
            logger.info("🤖 Starting Telegram bot polling...")
            await telegram_bot.dp.start_polling(telegram_bot.bot)
    except asyncio.CancelledError:
        logger.info("Telegram polling cancelled")
    except Exception as e:
        logger.error(f"Error in telegram polling: {str(e)}")


# Update app with lifespan
app.router.lifespan_context = lifespan


def main():
    """Main function to run the application"""
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )


if __name__ == "__main__":
    main()