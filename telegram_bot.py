import asyncio
import logging
import os
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message
)
from aiogram.filters import Command

from database import Database
from api_client import PanelAPIClient
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
        self.api_client: Optional[PanelAPIClient] = None
        
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
                InlineKeyboardButton(text="🔄 Sync Admins", callback_data=f"{MENU_PREFIX}sync_admins"),
                InlineKeyboardButton(text="⚡ Toggle Sync", callback_data=f"{MENU_PREFIX}sync")
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data=f"{MENU_PREFIX}settings"),
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
            elif action == "sync_admins":
                await self.sync_admins_from_api(callback)
            elif action == "settings":
                await self.show_settings(callback)
            elif action.startswith("set_"):
                await self.handle_settings_action(callback, action)
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

    async def sync_admins_from_api(self, callback: CallbackQuery):
        """Sync admins from Panel API and create topics for them"""
        try:
            # Check if API client is configured
            if not self.api_client:
                text = """⚠️ <b>API Not Configured</b>

To sync admins from the panel, configure these in your .env file:

<code>PANEL_API_URL=https://your-panel.com</code>
<code>PANEL_USERNAME=admin</code>
<code>PANEL_PASSWORD=password</code>

Then restart the bot."""
                
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                await callback.answer("API not configured", show_alert=True)
                return
            
            # Show loading message
            await callback.message.edit_text(
                "🔄 <b>Syncing Admins...</b>\n\nFetching admins from panel API...",
                parse_mode="HTML"
            )
            await callback.answer()
            
            # Test API connection
            if not await self.api_client.test_connection():
                await callback.message.edit_text(
                    "❌ <b>Connection Failed</b>\n\nCould not connect to panel API. Check your credentials.",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                return
            
            # Fetch all admins from API
            admins = await self.api_client.get_all_admins()
            
            if not admins:
                await callback.message.edit_text(
                    "📝 <b>No Admins Found</b>\n\nNo admins returned from the panel API.",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                return
            
            # Process each admin
            created_topics = 0
            updated_admins = 0
            errors = 0
            
            for admin in admins:
                admin_username = admin.get('username', 'unknown')
                admin_telegram_id = admin.get('telegram_id')
                
                if not admin_telegram_id:
                    continue  # Skip admins without telegram_id
                
                admin_telegram_id = str(admin_telegram_id)
                
                # Check if admin already exists
                existing = await self.db.get_admin_topic(admin_telegram_id)
                
                if existing:
                    # Update username if changed
                    if existing['admin_username'] != admin_username:
                        await self.db.set_admin_topic(
                            admin_telegram_id=admin_telegram_id,
                            admin_username=admin_username,
                            chat_id=existing['chat_id'],
                            topic_id=existing['topic_id']
                        )
                        updated_admins += 1
                else:
                    # New admin - create topic if we have fallback chat
                    topic_id = None
                    chat_id = self.fallback_chat_id
                    
                    if chat_id:
                        try:
                            # Try to create a forum topic for this admin
                            logger.info(f"Creating topic for admin {admin_username} in chat {chat_id}")
                            topic = await self.bot.create_forum_topic(
                                chat_id=int(chat_id),
                                name=f"👤 {admin_username}"[:128]
                            )
                            topic_id = str(topic.message_thread_id)
                            created_topics += 1
                            logger.info(f"Created topic {topic_id} for admin: {admin_username}")
                        except Exception as e:
                            error_msg = str(e)
                            logger.error(f"Could not create topic for {admin_username}: {error_msg}")
                            if "not enough rights" in error_msg.lower() or "can't manage" in error_msg.lower():
                                logger.error("Bot needs 'Manage Topics' permission in the forum group!")
                            elif "chat not found" in error_msg.lower():
                                logger.error(f"Chat {chat_id} not found. Ensure FALLBACK_CHAT_ID is correct.")
                            elif "not a forum" in error_msg.lower() or "supergroup" in error_msg.lower():
                                logger.error("The group must have Topics enabled (Forum supergroup).")
                            errors += 1
                    else:
                        logger.warning(f"No FALLBACK_CHAT_ID set - cannot create topic for {admin_username}")
                    
                    # Save admin mapping
                    await self.db.set_admin_topic(
                        admin_telegram_id=admin_telegram_id,
                        admin_username=admin_username,
                        chat_id=chat_id or "",
                        topic_id=topic_id
                    )
            
            # Update sync status
            await self.db.set_sync_status("initial_sync_complete", "true")
            await self.db.set_sync_status("last_sync", datetime.now().isoformat())
            
            # Show results
            text = f"""✅ <b>Admin Sync Complete</b>

<b>Results:</b>
📥 Total admins from API: {len(admins)}
🆕 New topics created: {created_topics}
🔄 Admins updated: {updated_admins}
⚠️ Errors: {errors}

<i>All admins with telegram_id are now registered.</i>"""
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )
            
            logger.info(f"Admin sync completed: {len(admins)} admins, {created_topics} topics created")
            
        except Exception as e:
            logger.error(f"Admin sync error: {str(e)}")
            await callback.message.edit_text(
                f"❌ <b>Sync Error</b>\n\n{str(e)}",
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )

    async def show_help(self, callback: CallbackQuery):
        """Show help information"""
        help_text = """📖 <b>How It Works</b>

<b>1️⃣ Admin Sync (API)</b>
• Press "🔄 Sync Admins" to fetch all admins from panel
• Bot automatically creates a topic for each admin
• Requires PANEL_API_URL, PANEL_USERNAME, PANEL_PASSWORD in .env

<b>2️⃣ Webhook Integration</b>
The bot receives webhook events from your panel when users are created or updated.

<b>3️⃣ Automatic Topic Routing</b>
Each admin gets their own forum topic. Notifications for their users go to their topic.

<b>4️⃣ Payment Tracking</b>
Each notification includes buttons:
• ✅ Paid - User has paid
• ❌ Unpaid - User hasn't paid
• ➕ Add to Settlement List

<b>5️⃣ Message Conditions</b>
• <code>user_created</code>: Always sends
• <code>user_updated</code>: Only when:
  - Expiry extended by ≥7 days
  - Status changed to on_hold

<b>6️⃣ Setup Steps</b>
1. Add bot to forum group (as admin)
2. Set FALLBACK_CHAT_ID to group ID
3. Configure panel API credentials
4. Press "Sync Admins" to create topics
5. Enable sync with "Toggle Sync"
6. Configure webhook URL in panel"""
        
        await callback.message.edit_text(
            help_text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer()

    async def show_about(self, callback: CallbackQuery):
        """Show about information"""
        about_text = """ℹ️ <b>About Accounting Bot</b>

<b>Version:</b> 2.1.0
<b>Type:</b> Webhook + API Accounting

<b>Key Features:</b>
• 🔄 Panel API integration
• 👥 Auto admin topic creation
• 💰 Payment status tracking
• 📋 Settlement list management
• 📊 Statistics and reporting
• 🔘 Button-based interface

<b>Architecture:</b>
• FastAPI webhook receiver
• Aiogram Telegram bot
• Panel API client
• SQLite database

<i>Built for seamless panel integration.</i>"""
        
        await callback.message.edit_text(
            about_text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer()

    async def show_settings(self, callback: CallbackQuery):
        """Show settings menu"""
        # Get current settings
        sync_status = await self.db.get_sync_status("initial_sync_complete")
        sync_emoji = "✅" if sync_status == "true" else "❌"
        
        api_status = "✅ Connected" if self.api_client else "❌ Not configured"
        chat_status = f"✅ {self.fallback_chat_id}" if self.fallback_chat_id else "❌ Not set"
        
        text = f"""⚙️ <b>Settings</b>

<b>Current Configuration:</b>

<b>🔄 Sync Status:</b> {sync_emoji} {"Enabled" if sync_status == "true" else "Disabled"}
<b>📡 Panel API:</b> {api_status}
<b>💬 Forum Chat:</b> {chat_status}

<b>Actions:</b>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Disable Sync" if sync_status == "true" else "🟢 Enable Sync",
                    callback_data=f"{MENU_PREFIX}set_toggle_sync"
                )
            ],
            [
                InlineKeyboardButton(text="🗑 Clear All Admins", callback_data=f"{MENU_PREFIX}set_clear_admins")
            ],
            [
                InlineKeyboardButton(text="🔄 Reset Topics", callback_data=f"{MENU_PREFIX}set_reset_topics")
            ],
            [
                InlineKeyboardButton(text="📊 View Config", callback_data=f"{MENU_PREFIX}set_view_config")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data=f"{MENU_PREFIX}main")
            ]
        ])
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()

    async def handle_settings_action(self, callback: CallbackQuery, action: str):
        """Handle settings sub-actions"""
        try:
            if action == "set_toggle_sync":
                current = await self.db.get_sync_status("initial_sync_complete")
                new_status = "false" if current == "true" else "true"
                await self.db.set_sync_status("initial_sync_complete", new_status)
                await callback.answer(f"Sync {'enabled' if new_status == 'true' else 'disabled'} ✅")
                # Refresh settings view - use try/except to handle "message not modified"
                try:
                    await self.show_settings(callback)
                except Exception:
                    pass  # Ignore if message content is the same
                
            elif action == "set_clear_admins":
                # Show confirmation
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="⚠️ Yes, Clear All", callback_data=f"{MENU_PREFIX}set_confirm_clear"),
                        InlineKeyboardButton(text="❌ Cancel", callback_data=f"{MENU_PREFIX}settings")
                    ]
                ])
                await callback.message.edit_text(
                    "⚠️ <b>Confirm Clear Admins</b>\n\nThis will remove all registered admins from the database.\nTopics in Telegram will NOT be deleted.\n\nAre you sure?",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                await callback.answer()
                
            elif action == "set_confirm_clear":
                # Execute clear
                admin_topics = await self.db.get_all_admin_topics()
                for admin in admin_topics:
                    await self.db.delete_admin_topic(admin['admin_telegram_id'])
                await callback.answer(f"Cleared {len(admin_topics)} admins ✅", show_alert=True)
                await self.show_settings(callback)
                
            elif action == "set_reset_topics":
                # Reset topic IDs (keep admins, clear topic references)
                admin_topics = await self.db.get_all_admin_topics()
                reset_count = 0
                for admin in admin_topics:
                    if admin['topic_id']:
                        await self.db.set_admin_topic(
                            admin_telegram_id=admin['admin_telegram_id'],
                            admin_username=admin['admin_username'],
                            chat_id=admin['chat_id'],
                            topic_id=None
                        )
                        reset_count += 1
                await callback.answer(f"Reset {reset_count} topic references ✅", show_alert=True)
                await self.show_settings(callback)
                
            elif action == "set_view_config":
                # Show current environment config
                config_text = f"""📊 <b>Current Configuration</b>

<b>Bot Token:</b> <code>{'✅ Set' if os.getenv('BOT_TOKEN') else '❌ Missing'}</code>
<b>Webhook Secret:</b> <code>{'✅ Set' if os.getenv('WEBHOOK_SECRET') else '⚠️ Not set'}</code>

<b>Panel API:</b>
• URL: <code>{os.getenv('PANEL_API_URL', 'Not set')}</code>
• Username: <code>{os.getenv('PANEL_USERNAME', 'Not set')}</code>
• Password: <code>{'✅ Set' if os.getenv('PANEL_PASSWORD') else '❌ Missing'}</code>

<b>Chat Settings:</b>
• Chat ID: <code>{self.fallback_chat_id or 'Not set'}</code>
• Topic ID: <code>{self.fallback_topic_id or 'Not set'}</code>

<b>Server:</b>
• Host: <code>{os.getenv('HOST', '0.0.0.0')}</code>
• Port: <code>{os.getenv('PORT', '8080')}</code>
• Debug: <code>{os.getenv('DEBUG', 'False')}</code>

<i>Edit .env file and restart to change settings.</i>"""
                
                await callback.message.edit_text(
                    config_text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 Back to Settings", callback_data=f"{MENU_PREFIX}settings")]
                    ])
                )
                await callback.answer()
                
            else:
                await callback.answer("Unknown setting action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Settings action error: {str(e)}")
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

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
                             fallback_chat_id: str = None, fallback_topic_id: str = None,
                             include_buttons: bool = True):
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
        
        # Create keyboard (only if include_buttons is True)
        keyboard = create_accounting_keyboard(username, admin_telegram_id, event_key) if include_buttons else None
        
        # Send message
        kwargs = {
            'chat_id': int(chat_id),
            'text': truncate_text(message),
            'parse_mode': 'HTML'
        }
        
        if keyboard:
            kwargs['reply_markup'] = keyboard
        
        if topic_id:
            kwargs['message_thread_id'] = int(topic_id)
        
        await telegram_bot.bot.send_message(**kwargs)
        
        logger.info(f"Message sent to admin {admin_username} at chat {chat_id}:{topic_id}")
        
    except Exception as e:
        logger.error(f"Error sending message to admin topic: {str(e)}")
