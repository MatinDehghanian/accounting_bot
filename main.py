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