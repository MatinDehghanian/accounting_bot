import asyncio
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message
)
from aiogram.filters import Command

from database import Database
from utils import (
    parse_callback_data, create_callback_data, 
    format_persian_datetime, truncate_text
)

# Configure logging
logger = logging.getLogger(__name__)


# Callback data prefixes for menu navigation
MENU_PREFIX = "menu:"


class TelegramBot:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.db: Optional[Database] = None
        
        # Default fallback chat/topic for unmapped admins
        self.fallback_chat_id = None
        self.fallback_topic_id = None

    async def init(self, token: str = None):
        """Initialize telegram bot"""
        if not token:
            token = "YOUR_BOT_TOKEN"
        
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = Database()
        
        # Register handlers - only /start command, rest is buttons
        self.dp.message(Command("start"))(self.cmd_start)
        
        # Handle any text message to show main menu
        self.dp.message(F.text)(self.handle_text_message)
        
        # Menu navigation callbacks
        self.dp.callback_query(F.data.startswith(MENU_PREFIX))(self.handle_menu_callback)
        
        # Accounting action callbacks (paid, unpaid, settlement)
        self.dp.callback_query(F.data.startswith(("paid:", "unpaid:", "add_settlement:")))(self.handle_accounting_callback)
        
        logger.info("Telegram bot initialized with button navigation")

    def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu inline keyboard"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistics", callback_data=f"{MENU_PREFIX}stats"),
                InlineKeyboardButton(text="👥 Admin List", callback_data=f"{MENU_PREFIX}admins")
            ],
            [
                InlineKeyboardButton(text="🔄 Enable Sync", callback_data=f"{MENU_PREFIX}sync"),
                InlineKeyboardButton(text="📖 Help", callback_data=f"{MENU_PREFIX}help")
            ],
            [
                InlineKeyboardButton(text="ℹ️ About", callback_data=f"{MENU_PREFIX}about")
            ]
        ])
        return keyboard

    def get_back_keyboard(self) -> InlineKeyboardMarkup:
        """Create back to menu keyboard"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data=f"{MENU_PREFIX}main")]
        ])
        return keyboard

    async def cmd_start(self, message: Message):
        """Handle /start command - show main menu"""
        await self.show_main_menu(message)

    async def handle_text_message(self, message: Message):
        """Handle any text message - show main menu"""
        await self.show_main_menu(message)

    async def show_main_menu(self, message: Message):
        """Display main menu with inline buttons"""
        welcome_text = """🤖 <b>Accounting Bot</b>

Welcome! This bot manages user accounting information via webhooks.

<b>Features:</b>
• Automatic admin topic creation
• Payment tracking (Paid/Unpaid)
• Settlement list management
• Real-time webhook notifications

Select an option below:"""
        
        await message.reply(
            welcome_text, 
            parse_mode="HTML",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def handle_menu_callback(self, callback: CallbackQuery):
        """Handle menu navigation callbacks"""
        action = callback.data.replace(MENU_PREFIX, "")
        
        try:
            if action == "main":
                await self.show_main_menu_edit(callback)
            elif action == "stats":
                await self.show_stats(callback)
            elif action == "admins":
                await self.show_admins(callback)
            elif action == "sync":
                await self.enable_sync(callback)
            elif action == "sync_disable":
                await self.disable_sync(callback)
            elif action == "help":
                await self.show_help(callback)
            elif action == "about":
                await self.show_about(callback)
            else:
                await callback.answer("Unknown action", show_alert=True)
        except Exception as e:
            logger.error(f"Menu callback error: {str(e)}")
            await callback.answer("❌ Error processing request", show_alert=True)

    async def show_main_menu_edit(self, callback: CallbackQuery):
        """Edit message to show main menu"""
        welcome_text = """🤖 <b>Accounting Bot</b>

Welcome! This bot manages user accounting information via webhooks.

<b>Features:</b>
• Automatic admin topic creation
• Payment tracking (Paid/Unpaid)
• Settlement list management
• Real-time webhook notifications

Select an option below:"""
        
        await callback.message.edit_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=self.get_main_menu_keyboard()
        )
        await callback.answer()

    async def show_stats(self, callback: CallbackQuery):
        """Show system statistics"""
        try:
            sync_status = await self.db.get_sync_status("initial_sync_complete")
            last_sync = await self.db.get_sync_status("last_sync")
            
            sync_emoji = "✅" if sync_status == "true" else "❌"
            sync_text = "Enabled" if sync_status == "true" else "Disabled"
            
            last_sync_text = format_persian_datetime(last_sync) if last_sync else "Never"
            
            admin_topics = await self.db.get_all_admin_topics()
            admin_count = len(admin_topics)
            
            text = f"""📊 <b>System Statistics</b>

<b>🔄 Sync Status:</b> {sync_emoji} {sync_text}
<b>🕐 Last Activity:</b> {last_sync_text}
<b>👥 Registered Admins:</b> {admin_count}

<b>🤖 Bot Status:</b> ✅ Active
<b>💾 Database:</b> ✅ Connected

<i>Admins are automatically registered when they create/update users through the panel.</i>"""
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def show_admins(self, callback: CallbackQuery):
        """Show list of registered admins"""
        try:
            admin_topics = await self.db.get_all_admin_topics()
            
            if not admin_topics:
                text = """👥 <b>Registered Admins</b>

📝 No admins registered yet.

<i>Admins will be automatically registered when they create or update users through the panel webhook.</i>"""
            else:
                text = "👥 <b>Registered Admins:</b>\n\n"
                
                for i, admin in enumerate(admin_topics, 1):
                    username = admin['admin_username'] or 'Unknown'
                    text += f"<b>{i}. {username}</b>\n"
                    text += f"   🆔 TG ID: <code>{admin['admin_telegram_id']}</code>\n"
                    text += f"   💬 Chat: <code>{admin['chat_id']}</code>\n"
                    
                    if admin['topic_id']:
                        text += f"   🗂 Topic: <code>{admin['topic_id']}</code>\n"
                    else:
                        text += "   🗂 Topic: Main chat\n"
                    text += "\n"
                
                text += "<i>Topics are created automatically for each admin.</i>"
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def enable_sync(self, callback: CallbackQuery):
        """Enable sync mode"""
        try:
            current_status = await self.db.get_sync_status("initial_sync_complete")
            
            if current_status == "true":
                # Already enabled - show confirmation to disable
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔴 Disable Sync", callback_data=f"{MENU_PREFIX}sync_disable"),
                        InlineKeyboardButton(text="🔙 Back", callback_data=f"{MENU_PREFIX}main")
                    ]
                ])
                text = """🔄 <b>Sync Status</b>

✅ Sync is currently <b>ENABLED</b>

The bot will process all user_updated events.

Do you want to disable it?"""
            else:
                # Not enabled - enable it
                await self.db.set_sync_status("initial_sync_complete", "true")
                await self.db.set_sync_status("last_sync", datetime.now().isoformat())
                
                keyboard = self.get_back_keyboard()
                text = """🔄 <b>Sync Enabled</b>

✅ Sync has been <b>ENABLED</b> successfully!

The bot will now process all webhook events including user_updated.

<i>Note: Since there's no direct API access, the bot learns about users from webhook events.</i>"""
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await callback.answer("Sync enabled ✅" if current_status != "true" else "")
            
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def disable_sync(self, callback: CallbackQuery):
        """Disable sync mode"""
        try:
            await self.db.set_sync_status("initial_sync_complete", "false")
            
            text = """🔄 <b>Sync Disabled</b>

❌ Sync has been <b>DISABLED</b>.

The bot will only process user_created events.
user_updated events will be ignored until sync is re-enabled."""
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )
            await callback.answer("Sync disabled")
            
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def show_help(self, callback: CallbackQuery):
        """Show help information"""
        help_text = """📖 <b>How It Works</b>

<b>1️⃣ Webhook Integration</b>
The bot receives webhook events from your panel when users are created or updated.

<b>2️⃣ Automatic Admin Detection</b>
When an admin creates/updates a user, the bot automatically:
• Registers the admin
• Creates a dedicated topic (if in a forum group)
• Sends notifications to the right place

<b>3️⃣ Payment Tracking</b>
Each notification includes buttons to mark:
• ✅ Paid - User has paid
• ❌ Unpaid - User hasn't paid
• ➕ Add to Settlement List

<b>4️⃣ Message Conditions</b>
• <code>user_created</code>: Always sends notification
• <code>user_updated</code>: Only when:
  - Expiry extended by ≥7 days
  - Status changed to on_hold

<b>5️⃣ Setup Requirements</b>
• Add bot to your group (as admin)
• Enable forum topics (optional)
• Configure webhook URL in panel
• Enable sync in this bot"""
        
        await callback.message.edit_text(
            help_text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer()

    async def show_about(self, callback: CallbackQuery):
        """Show about information"""
        about_text = """ℹ️ <b>About Accounting Bot</b>

<b>Version:</b> 2.0.0
<b>Type:</b> Webhook-based Accounting

<b>Key Features:</b>
• 🔄 Real-time webhook processing
• 👥 Automatic admin topic creation
• 💰 Payment status tracking
• 📋 Settlement list management
• 📊 Statistics and reporting

<b>Architecture:</b>
• FastAPI webhook receiver
• Aiogram Telegram bot
• SQLite database
• Async processing

<i>Built for seamless panel integration.</i>"""
        
        await callback.message.edit_text(
            about_text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer()

    async def handle_accounting_callback(self, callback: CallbackQuery):
        """Handle accounting action callbacks (paid, unpaid, settlement)"""
        try:
            # Parse callback data
            callback_data = parse_callback_data(callback.data)
            action_type = callback_data['action_type']
            username = callback_data['username']
            admin_telegram_id = callback_data['admin_telegram_id']
            event_key = callback_data['event_key']
            
            clicker_id = str(callback.from_user.id)
            clicker_name = callback.from_user.full_name or callback.from_user.username or "Unknown"
            
            current_time = format_persian_datetime(datetime.now().isoformat())
            
            # Process based on action type
            if action_type == "paid":
                await self.handle_payment_status(callback, username, "Paid", clicker_id, clicker_name, current_time)
            
            elif action_type == "unpaid":
                await self.handle_payment_status(callback, username, "Unpaid", clicker_id, clicker_name, current_time)
            
            elif action_type == "add_settlement":
                await self.handle_add_settlement(callback, username, clicker_id, clicker_name, current_time)
            
            # Log the action
            await self.db.log_audit(
                log_type=f"callback_{action_type}",
                username=username,
                admin_telegram_id=admin_telegram_id,
                actor_telegram_id=clicker_id,
                payload={"action": action_type, "event_key": event_key}
            )
            
        except Exception as e:
            logger.error(f"Callback handling error: {str(e)}")
            await callback.answer("❌ Processing error", show_alert=True)

    async def handle_payment_status(self, callback: CallbackQuery, username: str, 
                                  status: str, clicker_id: str, clicker_name: str, current_time: str):
        """Handle payment status callbacks"""
        
        # Check current status
        current_payment = await self.db.get_payment_status(username)
        
        if current_payment and current_payment['payment_status'] == status:
            await callback.answer(f"Already marked as {status}", show_alert=False)
            return
        
        # Update payment status
        await self.db.set_payment_status(username, status, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Remove any existing payment status line
        lines = original_text.split('\n')
        filtered_lines = [line for line in lines if not any(marker in line for marker in ['✅ Paid', '❌ Unpaid'])]
        
        # Add new status
        emoji = "✅" if status == "Paid" else "❌"
        status_line = f"\n{emoji} {status} marked by {clicker_name} at {current_time}"
        
        new_text = '\n'.join(filtered_lines) + status_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer(f"{status} marked ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("Marked but error updating message")

    async def handle_add_settlement(self, callback: CallbackQuery, username: str, 
                                   clicker_id: str, clicker_name: str, current_time: str):
        """Handle add to settlement callbacks"""
        
        # Add to settlement list
        await self.db.add_to_settlement(username, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Check if already added
        if "➕ Added to settlement list" in original_text:
            await callback.answer("Already added to settlement list", show_alert=False)
            return
        
        # Add settlement line
        settlement_line = f"\n➕ Added to settlement list by {clicker_name} at {current_time}"
        new_text = original_text + settlement_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer("Added to settlement list ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("Added but error updating message")


def create_accounting_keyboard(username: str, admin_telegram_id: str, event_key: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for accounting actions"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Paid",
                callback_data=create_callback_data("paid", username, admin_telegram_id, event_key)
            ),
            InlineKeyboardButton(
                text="❌ Unpaid", 
                callback_data=create_callback_data("unpaid", username, admin_telegram_id, event_key)
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Add to Settlement",
                callback_data=create_callback_data("add_settlement", username, admin_telegram_id, event_key)
            )
        ]
    ])
    
    return keyboard


async def auto_register_admin(admin_telegram_id: str, admin_username: str, 
                              db: Database, bot: Bot, target_chat_id: str) -> Tuple[str, Optional[str]]:
    """
    Automatically register admin and create topic if needed.
    This is called when we receive a webhook event from a new admin.
    
    Returns: (chat_id, topic_id)
    """
    
    # Check if admin already exists
    existing = await db.get_admin_topic(admin_telegram_id)
    if existing:
        # Update username if changed
        if existing['admin_username'] != admin_username:
            await db.set_admin_topic(
                admin_telegram_id=admin_telegram_id,
                admin_username=admin_username,
                chat_id=existing['chat_id'],
                topic_id=existing['topic_id']
            )
        return existing['chat_id'], existing.get('topic_id')
    
    # New admin - try to create a topic for them
    topic_id = None
    
    if target_chat_id:
        try:
            # Try to create a forum topic for this admin
            topic = await bot.create_forum_topic(
                chat_id=int(target_chat_id),
                name=f"👤 {admin_username}"[:128],  # Max 128 chars for topic name
                icon_custom_emoji_id=None
            )
            topic_id = str(topic.message_thread_id)
            logger.info(f"Created topic {topic_id} for admin {admin_username}")
        except Exception as e:
            # Group might not support topics, use main chat
            logger.warning(f"Could not create topic for {admin_username}: {str(e)}")
            topic_id = None
    
    # Save admin mapping
    await db.set_admin_topic(
        admin_telegram_id=admin_telegram_id,
        admin_username=admin_username,
        chat_id=target_chat_id or "",
        topic_id=topic_id
    )
    
    logger.info(f"Registered new admin: {admin_username} ({admin_telegram_id})")
    
    return target_chat_id, topic_id


async def send_to_admin_topic(admin_telegram_id: str, admin_username: str, message: str, 
                             username: str, event_key: str, db: Database, 
                             fallback_chat_id: str = None, fallback_topic_id: str = None):
    """Send message to admin's dedicated topic with auto-registration"""
    
    from webhook_receiver import telegram_bot
    
    if not telegram_bot.bot:
        logger.error("Telegram bot not initialized")
        return
    
    try:
        # Auto-register admin if new (creates topic automatically)
        chat_id, topic_id = await auto_register_admin(
            admin_telegram_id=admin_telegram_id,
            admin_username=admin_username,
            db=db,
            bot=telegram_bot.bot,
            target_chat_id=fallback_chat_id or telegram_bot.fallback_chat_id
        )
        
        # Use fallback if no chat_id
        if not chat_id:
            chat_id = fallback_chat_id or telegram_bot.fallback_chat_id
            topic_id = fallback_topic_id or telegram_bot.fallback_topic_id
        
        if not chat_id:
            logger.error(f"No chat_id available for admin {admin_telegram_id}. Set FALLBACK_CHAT_ID in .env")
            return
        
        # Create keyboard
        keyboard = create_accounting_keyboard(username, admin_telegram_id, event_key)
        
        # Send message
        kwargs = {
            'chat_id': int(chat_id),
            'text': truncate_text(message),
            'parse_mode': 'HTML',
            'reply_markup': keyboard
        }
        
        if topic_id:
            kwargs['message_thread_id'] = int(topic_id)
        
        await telegram_bot.bot.send_message(**kwargs)
        
        logger.info(f"Message sent to admin {admin_username} at chat {chat_id}:{topic_id}")
        
    except Exception as e:
        logger.error(f"Error sending message to admin topic: {str(e)}")
