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
        
        # Backup topic for automated messages
        self.backup_topic_id = None

    async def init(self, token: str = None):
        """Initialize telegram bot"""
        if not token:
            token = "YOUR_BOT_TOKEN"
        
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = Database()
        
        # Register handlers - only /start command, rest is buttons
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("setadmin"))(self.cmd_setadmin)
        
        # Handle any text message to show main menu
        self.dp.message(F.text)(self.handle_text_message)
        
        # Menu navigation callbacks
        self.dp.callback_query(F.data.startswith(MENU_PREFIX))(self.handle_menu_callback)
        
        # Accounting action callbacks (paid, unpaid, settlement, pricing, dismiss)
        self.dp.callback_query(F.data.startswith((
            "paid:", "unpaid:", "add_settlement:", 
            "set_price:", "dismiss:", "price_"
        )))(self.handle_accounting_callback)
        
        logger.info("Telegram bot initialized with button navigation")

    def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu inline keyboard"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistics", callback_data=f"{MENU_PREFIX}stats"),
                InlineKeyboardButton(text="👥 Admin List", callback_data=f"{MENU_PREFIX}admins")
            ],
            [
                InlineKeyboardButton(text="� My Settlement", callback_data=f"{MENU_PREFIX}my_settlement"),
                InlineKeyboardButton(text="💳 Checkout", callback_data=f"{MENU_PREFIX}checkout")
            ],
            [
                InlineKeyboardButton(text="�🔄 Sync Admins", callback_data=f"{MENU_PREFIX}sync_admins"),
                InlineKeyboardButton(text="⚡ Toggle Sync", callback_data=f"{MENU_PREFIX}sync")
            ],
            [
                InlineKeyboardButton(text="🧾 Admin Sales", callback_data=f"{MENU_PREFIX}admin_sales"),
                InlineKeyboardButton(text="⏰ Expiry Groups", callback_data=f"{MENU_PREFIX}expiry_groups")
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

    async def cmd_setadmin(self, message: Message):
        """Handle /setadmin command - set main bot admin ID"""
        try:
            # Extract telegram_id from command
            # Format: /setadmin 123456789
            parts = message.text.split()
            
            if len(parts) != 2:
                await message.reply(
                    "❌ <b>Usage:</b> <code>/setadmin YOUR_TELEGRAM_ID</code>\n\n"
                    f"Your ID: <code>{message.from_user.id}</code>\n\n"
                    "To use your own ID, send: <code>/setadmin " + str(message.from_user.id) + "</code>",
                    parse_mode="HTML"
                )
                return
            
            admin_id = parts[1]
            
            # Validate it's numeric
            if not admin_id.isdigit():
                await message.reply(
                    "❌ <b>Error:</b> Telegram ID must be numeric.\n\n"
                    f"Your ID: <code>{message.from_user.id}</code>",
                    parse_mode="HTML"
                )
                return
            
            # Save to database
            await self.db.set_sync_status("main_bot_admin_id", admin_id)
            
            await message.reply(
                f"✅ <b>Main Bot Admin Set</b>\n\n"
                f"ID: <code>{admin_id}</code>\n\n"
                "This admin will manage topics for panel admins without telegram_id.",
                parse_mode="HTML"
            )
            
            logger.info(f"Main bot admin set to {admin_id} by {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Error setting main admin: {str(e)}")
            await message.reply(f"❌ Error: {str(e)}")

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
            elif action == "my_settlement":
                await self.show_my_settlement(callback)
            elif action == "checkout":
                await self.handle_checkout(callback)
            elif action == "confirm_checkout":
                await self.confirm_checkout(callback)
            elif action == "admin_sales":
                await self.show_admin_sales(callback)
            elif action.startswith("sales_"):
                admin_name = action.replace("sales_", "")
                await self.show_admin_sales_report(callback, admin_name)
            elif action == "expiry_groups":
                await self.show_expiry_groups(callback)
            elif action.startswith("expiry_"):
                await self.handle_expiry_action(callback, action)
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
                    
                    tg_id = admin.get('admin_telegram_id')
                    if tg_id:
                        text += f"   🆔 TG ID: <code>{tg_id}</code>\n"
                    else:
                        text += "   🆔 TG ID: <i>None (Panel only)</i>\n"
                    
                    text += f"   💬 Chat: <code>{admin['chat_id']}</code>\n"
                    
                    if admin['topic_id']:
                        text += f"   🗂 Topic: <code>{admin['topic_id']}</code>\n"
                    else:
                        text += "   🗂 Topic: Main chat\n"
                    
                    managed_by = admin.get('managed_by')
                    if managed_by:
                        text += f"   👤 Managed by: <code>{managed_by}</code>\n"
                    
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
            no_telegram_id_count = 0
            
            # Get main bot admin from settings (for admins without telegram_id)
            main_bot_admin = await self.db.get_sync_status("main_bot_admin_id")
            
            for admin in admins:
                admin_username = admin.get('username', 'unknown')
                admin_telegram_id = admin.get('telegram_id')
                
                # Track if admin has no telegram_id
                assigned_to_main_admin = False
                if not admin_telegram_id:
                    no_telegram_id_count += 1
                    assigned_to_main_admin = True
                    if not main_bot_admin:
                        logger.warning(f"Admin {admin_username} has no telegram_id and no main bot admin set - skipping")
                        continue
                
                admin_telegram_id_str = str(admin_telegram_id) if admin_telegram_id else None
                
                # Check if admin already exists (by username)
                existing = await self.db.get_admin_topic(admin_username)
                
                if existing:
                    # Update if anything changed
                    if (existing.get('admin_telegram_id') != admin_telegram_id_str or 
                        existing.get('managed_by') != (main_bot_admin if assigned_to_main_admin else None)):
                        await self.db.set_admin_topic(
                            admin_username=admin_username,
                            admin_telegram_id=admin_telegram_id_str,
                            chat_id=existing['chat_id'],
                            topic_id=existing['topic_id'],
                            managed_by=main_bot_admin if assigned_to_main_admin else None
                        )
                        updated_admins += 1
                else:
                    # New admin - create topic if we have fallback chat
                    topic_id = None
                    chat_id = self.fallback_chat_id
                    
                    if chat_id:
                        try:
                            # Try to create a forum topic for this admin
                            topic_name = f"👤 {admin_username}"
                            if assigned_to_main_admin:
                                topic_name = f"📋 {admin_username} (Panel)"
                            
                            logger.info(f"Creating topic for admin {admin_username} in chat {chat_id}")
                            topic = await self.bot.create_forum_topic(
                                chat_id=int(chat_id),
                                name=topic_name[:128]
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
                        admin_username=admin_username,
                        admin_telegram_id=admin_telegram_id_str,
                        chat_id=chat_id or "",
                        topic_id=topic_id,
                        managed_by=main_bot_admin if assigned_to_main_admin else None
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
👤 No telegram_id (assigned to main admin): {no_telegram_id_count}
⚠️ Errors: {errors}

<i>All admins with telegram_id are now registered.</i>"""
            
            if no_telegram_id_count > 0 and not main_bot_admin:
                text += "\n\n⚠️ <b>Note:</b> Some admins have no telegram_id. Set main bot admin in settings to assign them."
            
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

    async def show_admin_sales(self, callback: CallbackQuery):
        """Show admin sales selection menu"""
        try:
            if not self.api_client:
                await callback.message.edit_text(
                    "⚠️ <b>API Not Configured</b>\n\nPanel API is required for admin sales report.",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                await callback.answer()
                return

            # Get registered admins
            admin_topics = await self.db.get_all_admin_topics()
            if not admin_topics:
                await callback.message.edit_text(
                    "📝 <b>No admins registered.</b>\n\nSync admins first.",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                await callback.answer()
                return

            # Build selection keyboard
            buttons = []
            buttons.append([InlineKeyboardButton(
                text="📊 All Admins",
                callback_data=f"{MENU_PREFIX}sales_all"
            )])
            
            for admin in admin_topics:
                admin_username = admin.get('admin_username', 'Unknown')
                if admin_username and admin_username != 'Unknown':
                    buttons.append([InlineKeyboardButton(
                        text=f"👤 {admin_username}",
                        callback_data=f"{MENU_PREFIX}sales_{admin_username}"
                    )])
            
            buttons.append([InlineKeyboardButton(
                text="🔙 Back to Menu",
                callback_data=f"{MENU_PREFIX}main"
            )])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(
                "🧾 <b>Admin Sales Report</b>\n\nSelect an admin to view their sales:",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await callback.answer()

        except Exception as e:
            logger.error(f"Admin sales menu error: {str(e)}")
            await callback.message.edit_text(
                f"❌ <b>Error:</b> {str(e)}",
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )

    async def show_admin_sales_report(self, callback: CallbackQuery, selected_admin: str = None):
        """Show admin sales report - unsettled users per admin or specific admin"""
        try:
            await callback.message.edit_text(
                "🔄 <b>Loading Admin Sales Report...</b>\n\nFetching data...",
                parse_mode="HTML"
            )
            await callback.answer()

            # Get registered admins from our DB
            admin_topics = await self.db.get_all_admin_topics()
            if not admin_topics:
                await callback.message.edit_text(
                    "📝 <b>No admins registered.</b>\n\nSync admins first.",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                return

            # Filter to selected admin if specified
            if selected_admin and selected_admin != "all":
                admin_topics = [a for a in admin_topics if a.get('admin_username') == selected_admin]

            # Get local renew data: usernames that have user_updated (expire extended) in audit_log
            renewed_users = await self.db.get_renewed_usernames()

            admin_data = {}

            for admin in admin_topics:
                admin_username = admin.get('admin_username', 'Unknown')
                if not admin_username or admin_username == 'Unknown':
                    continue

                # Fetch only this admin's users from the API
                users = await self.api_client.get_all_users(admin=admin_username)
                if not users:
                    continue

                for user in users:
                    username = user.get('username', '')
                    data_limit = user.get('data_limit', 0) or 0
                    data_limit_gb = data_limit / (1024 ** 3)

                    # Check payment status from our DB
                    payment = await self.db.get_payment_status(username)
                    payment_status = payment.get('payment_status') if payment else None

                    # Skip users that are already paid or dismissed
                    if payment_status in ('Paid', 'Dismissed'):
                        continue

                    if admin_username not in admin_data:
                        admin_data[admin_username] = {
                            'create_gb': 0, 'create_count': 0,
                            'renew_gb': 0, 'renew_count': 0,
                            'total_gb': 0, 'total_count': 0
                        }

                    # Check our DB to see if this user was renewed
                    is_renew = username in renewed_users

                    if is_renew:
                        admin_data[admin_username]['renew_gb'] += data_limit_gb
                        admin_data[admin_username]['renew_count'] += 1
                    else:
                        admin_data[admin_username]['create_gb'] += data_limit_gb
                        admin_data[admin_username]['create_count'] += 1

                    admin_data[admin_username]['total_gb'] += data_limit_gb
                    admin_data[admin_username]['total_count'] += 1

            if not admin_data:
                await callback.message.edit_text(
                    "✅ <b>All Clear!</b>\n\nAll users have been settled (Paid/Dismissed).",
                    parse_mode="HTML",
                    reply_markup=self.get_back_keyboard()
                )
                return

            # Build report
            if selected_admin and selected_admin != "all":
                text = f"🧾 <b>Admin Sales Report - {selected_admin}</b>\n"
            else:
                text = "🧾 <b>Admin Sales Report - All Admins</b>\n"
            text += "<i>Unsettled users only (not Paid/Dismissed)</i>\n\n"

            for admin_name in sorted(admin_data.keys()):
                data = admin_data[admin_name]
                text += f"👮 <b>{admin_name}</b>\n"
                text += f"   📊 Total: <b>{data['total_gb']:.1f} GB</b> ({data['total_count']} users)\n"
                text += f"   🆕 Create: {data['create_gb']:.1f} GB ({data['create_count']} users)\n"
                text += f"   🔄 Renew: {data['renew_gb']:.1f} GB ({data['renew_count']} users)\n\n"

            # Grand totals
            grand_total_gb = sum(d['total_gb'] for d in admin_data.values())
            grand_total_users = sum(d['total_count'] for d in admin_data.values())
            text += f"━━━━━━━━━━━━━━━━━━\n"
            text += f"📦 <b>Grand Total: {grand_total_gb:.1f} GB ({grand_total_users} users)</b>"

            # Truncate if too long
            from utils import truncate_text
            text = truncate_text(text)

            # Back button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to Admin Sales", callback_data=f"{MENU_PREFIX}admin_sales")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data=f"{MENU_PREFIX}main")]
            ])

            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Admin sales report error: {str(e)}")
            await callback.message.edit_text(
                f"❌ <b>Error:</b> {str(e)}",
                parse_mode="HTML",
                reply_markup=self.get_back_keyboard()
            )

    async def show_expiry_groups(self, callback: CallbackQuery):
        """Show expiry group settings and status"""
        try:
            # Get current settings
            threshold_days = await self.db.get_sync_status("expiry_threshold_days")
            group_id = await self.db.get_sync_status("expiry_group_id")
            remove_enabled = await self.db.get_sync_status("expiry_remove_enabled")
            last_check = await self.db.get_sync_status("expiry_last_check")
            auto_enabled = await self.db.get_sync_status("expiry_auto_enabled")

            threshold_text = f"{threshold_days} days" if threshold_days else "Not set"
            group_text = f"Group #{group_id}" if group_id else "Not set"
            remove_text = "✅ Yes" if remove_enabled == "true" else "❌ No"
            auto_text = "✅ Enabled" if auto_enabled == "true" else "❌ Disabled"
            last_check_text = format_persian_datetime(last_check) if last_check else "Never"

            text = f"""⏰ <b>Auto-Expiry Group Assignment</b>

<b>Current Settings:</b>
📅 Threshold: <b>{threshold_text}</b>
🏷 Group ID: <b>{group_text}</b>
🗑 Remove if > threshold: {remove_text}
🤖 Auto-check (24h): {auto_text}
🕐 Last check: {last_check_text}

<i>Users expiring within the threshold will be added to the specified group.
Users with more time remaining will be removed from that group (if enabled).</i>

<b>Configure:</b>"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📅 Set Threshold ({threshold_text})",
                        callback_data=f"{MENU_PREFIX}expiry_set_threshold"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"🏷 Set Group ({group_text})",
                        callback_data=f"{MENU_PREFIX}expiry_set_group"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"🗑 Toggle Remove: {remove_text}",
                        callback_data=f"{MENU_PREFIX}expiry_toggle_remove"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"🤖 Toggle Auto: {auto_text}",
                        callback_data=f"{MENU_PREFIX}expiry_toggle_auto"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="▶️ Run Now",
                        callback_data=f"{MENU_PREFIX}expiry_run_now"
                    )
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

        except Exception as e:
            logger.error(f"Expiry groups error: {str(e)}")
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def handle_expiry_action(self, callback: CallbackQuery, action: str):
        """Handle expiry group sub-actions"""
        try:
            if action == "expiry_set_threshold":
                # Show threshold options
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="3 days", callback_data=f"{MENU_PREFIX}expiry_threshold_3"),
                        InlineKeyboardButton(text="5 days", callback_data=f"{MENU_PREFIX}expiry_threshold_5"),
                        InlineKeyboardButton(text="7 days", callback_data=f"{MENU_PREFIX}expiry_threshold_7"),
                    ],
                    [
                        InlineKeyboardButton(text="10 days", callback_data=f"{MENU_PREFIX}expiry_threshold_10"),
                        InlineKeyboardButton(text="14 days", callback_data=f"{MENU_PREFIX}expiry_threshold_14"),
                        InlineKeyboardButton(text="30 days", callback_data=f"{MENU_PREFIX}expiry_threshold_30"),
                    ],
                    [
                        InlineKeyboardButton(text="🔙 Back", callback_data=f"{MENU_PREFIX}expiry_groups")
                    ]
                ])
                await callback.message.edit_text(
                    "📅 <b>Set Expiry Threshold</b>\n\nUsers expiring within this many days will be added to the group:",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                await callback.answer()

            elif action.startswith("expiry_threshold_"):
                days = action.replace("expiry_threshold_", "")
                await self.db.set_sync_status("expiry_threshold_days", days)
                await callback.answer(f"Threshold set to {days} days ✅", show_alert=True)
                await self.show_expiry_groups(callback)

            elif action == "expiry_set_group":
                # Fetch groups from API and show selection
                if not self.api_client:
                    await callback.answer("API not configured", show_alert=True)
                    return

                groups = await self.api_client.get_all_groups()
                if not groups:
                    await callback.answer("No groups found in panel", show_alert=True)
                    return

                buttons = []
                row = []
                for group in groups:
                    group_name = group.get('name', 'Unknown')
                    group_id = group.get('id', 0)
                    row.append(InlineKeyboardButton(
                        text=f"#{group_id} {group_name}",
                        callback_data=f"{MENU_PREFIX}expiry_group_{group_id}"
                    ))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                buttons.append([
                    InlineKeyboardButton(text="🔙 Back", callback_data=f"{MENU_PREFIX}expiry_groups")
                ])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await callback.message.edit_text(
                    "🏷 <b>Select Group</b>\n\nChoose the group to assign to users near expiry:",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                await callback.answer()

            elif action.startswith("expiry_group_"):
                group_id = action.replace("expiry_group_", "")
                await self.db.set_sync_status("expiry_group_id", group_id)
                await callback.answer(f"Group set to #{group_id} ✅", show_alert=True)
                await self.show_expiry_groups(callback)

            elif action == "expiry_toggle_remove":
                current = await self.db.get_sync_status("expiry_remove_enabled")
                new_val = "false" if current == "true" else "true"
                await self.db.set_sync_status("expiry_remove_enabled", new_val)
                await callback.answer(f"Remove {'enabled' if new_val == 'true' else 'disabled'} ✅")
                await self.show_expiry_groups(callback)

            elif action == "expiry_toggle_auto":
                current = await self.db.get_sync_status("expiry_auto_enabled")
                new_val = "false" if current == "true" else "true"
                await self.db.set_sync_status("expiry_auto_enabled", new_val)
                await callback.answer(f"Auto-check {'enabled' if new_val == 'true' else 'disabled'} ✅")
                await self.show_expiry_groups(callback)

            elif action == "expiry_run_now":
                await self.run_expiry_group_check(callback)

            else:
                await callback.answer("Unknown expiry action", show_alert=True)

        except Exception as e:
            logger.error(f"Expiry action error: {str(e)}")
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    async def run_expiry_group_check(self, callback: CallbackQuery = None):
        """
        Check all users' expiry dates and assign/remove group IDs.
        Can be called from button (with callback) or from background scheduler (without).
        """
        try:
            # Get settings
            threshold_days = await self.db.get_sync_status("expiry_threshold_days")
            group_id = await self.db.get_sync_status("expiry_group_id")
            remove_enabled = await self.db.get_sync_status("expiry_remove_enabled")

            if not threshold_days or not group_id:
                if callback:
                    await callback.answer("⚠️ Set threshold and group first!", show_alert=True)
                return

            threshold = int(threshold_days)
            target_group = int(group_id)

            if callback:
                await callback.message.edit_text(
                    "🔄 <b>Running Expiry Check...</b>\n\nFetching all users from panel...",
                    parse_mode="HTML"
                )
                await callback.answer()

            if not self.api_client:
                if callback:
                    await callback.message.edit_text(
                        "⚠️ <b>API not configured</b>",
                        parse_mode="HTML",
                        reply_markup=self.get_back_keyboard()
                    )
                return

            # Fetch all users
            all_users = await self.api_client.get_all_users()
            if not all_users:
                if callback:
                    await callback.message.edit_text(
                        "📝 <b>No users found in panel.</b>",
                        parse_mode="HTML",
                        reply_markup=self.get_back_keyboard()
                    )
                return

            from utils import calculate_days_left

            added_count = 0
            removed_count = 0
            errors = 0
            skipped = 0

            for user in all_users:
                username = user.get('username', '')
                expire = user.get('expire')
                current_groups = user.get('group_ids') or []
                status = user.get('status', '')

                # Skip users without expiry (unlimited)
                if not expire:
                    skipped += 1
                    continue

                # Skip non-active users
                if status not in ('active', 'on_hold'):
                    skipped += 1
                    continue

                days_left = calculate_days_left(expire)
                if days_left is None:
                    skipped += 1
                    continue

                has_group = target_group in current_groups

                if days_left <= threshold and not has_group:
                    # Add to group
                    new_groups = current_groups + [target_group]
                    result = await self.api_client.modify_user(username, {"group_ids": new_groups})
                    if result:
                        added_count += 1
                        logger.info(f"Added user {username} to group {target_group} (expires in {days_left} days)")
                    else:
                        errors += 1
                        logger.error(f"Failed to add user {username} to group {target_group}")

                elif days_left > threshold and has_group and remove_enabled == "true":
                    # Remove from group
                    new_groups = [g for g in current_groups if g != target_group]
                    result = await self.api_client.modify_user(username, {"group_ids": new_groups})
                    if result:
                        removed_count += 1
                        logger.info(f"Removed user {username} from group {target_group} (expires in {days_left} days)")
                    else:
                        errors += 1
                        logger.error(f"Failed to remove user {username} from group {target_group}")

            # Update last check time
            await self.db.set_sync_status("expiry_last_check", datetime.now().isoformat())

            result_text = f"""✅ <b>Expiry Group Check Complete</b>

<b>Settings:</b>
📅 Threshold: {threshold} days
🏷 Group: #{target_group}
🗑 Auto-remove: {'Yes' if remove_enabled == "true" else 'No'}

<b>Results:</b>
📥 Total users checked: {len(all_users)}
➕ Added to group: {added_count}
➖ Removed from group: {removed_count}
⏭ Skipped: {skipped}
⚠️ Errors: {errors}

🕐 <b>Time:</b> {format_persian_datetime(datetime.now().isoformat())}"""

            if callback:
                await callback.message.edit_text(
                    result_text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⏰ Expiry Settings", callback_data=f"{MENU_PREFIX}expiry_groups")],
                        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data=f"{MENU_PREFIX}main")]
                    ])
                )
            else:
                # Log results when running from scheduler
                logger.info(f"Expiry check: +{added_count} / -{removed_count} / {errors} errors / {skipped} skipped")

        except Exception as e:
            logger.error(f"Expiry group check error: {str(e)}")
            if callback:
                await callback.message.edit_text(
                    f"❌ <b>Error:</b> {str(e)}",
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

    async def show_my_settlement(self, callback: CallbackQuery):
        """Show settlement list for the current admin"""
        admin_telegram_id = str(callback.from_user.id)
        
        # Get admin's settlement list
        settlement_items = await self.db.get_admin_settlement_list(admin_telegram_id, checked_out=False)
        totals = await self.db.get_settlement_total(admin_telegram_id)
        
        if not settlement_items:
            text = """📋 <b>My Settlement List</b>

📝 No pending items in your settlement list.

<i>Add users to settlement using the "➕ Add to Settlement" button on user notifications.</i>"""
        else:
            text = f"""📋 <b>My Settlement List</b>

<b>Pending Items:</b> {totals['count']}
<b>With Price:</b> {totals['items_with_price']}
<b>Without Price:</b> {totals['items_without_price']}

━━━━━━━━━━━━━━━━━━
"""
            for i, item in enumerate(settlement_items[:20], 1):  # Limit to 20 items
                price = item.get('price') or item.get('user_price') or '-'
                if price and price != '-':
                    try:
                        price_int = int(price)
                        price = f"{price_int:,}" if price_int >= 1000 else price
                    except:
                        pass
                text += f"{i}. <code>{item['username']}</code> - {price}\n"
            
            if len(settlement_items) > 20:
                text += f"\n... and {len(settlement_items) - 20} more items"
            
            text += f"""
━━━━━━━━━━━━━━━━━━
💰 <b>Total:</b> {totals['total']:,} Toman

<i>Press "💳 Checkout" to mark all as checked out.</i>"""
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer()

    async def handle_checkout(self, callback: CallbackQuery):
        """Show checkout confirmation"""
        admin_telegram_id = str(callback.from_user.id)
        
        # Get totals
        totals = await self.db.get_settlement_total(admin_telegram_id)
        
        if totals['count'] == 0:
            await callback.answer("No items to checkout", show_alert=True)
            return
        
        text = f"""💳 <b>Checkout Confirmation</b>

You are about to checkout:
• <b>Items:</b> {totals['count']}
• <b>Total Amount:</b> {totals['total']:,} Toman

⚠️ This will mark all items as checked out with ✅
They will no longer appear in your settlement list.

<b>Are you sure?</b>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm Checkout", callback_data=f"{MENU_PREFIX}confirm_checkout"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"{MENU_PREFIX}main")
            ]
        ])
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()

    async def confirm_checkout(self, callback: CallbackQuery):
        """Process the checkout"""
        admin_telegram_id = str(callback.from_user.id)
        admin_name = callback.from_user.full_name or callback.from_user.username or "Unknown"
        
        # Get totals before checkout
        totals = await self.db.get_settlement_total(admin_telegram_id)
        
        # Perform checkout
        checked_out_count = await self.db.checkout_settlement(admin_telegram_id, admin_telegram_id)
        
        # Log the checkout
        await self.db.log_audit(
            log_type="checkout",
            admin_telegram_id=admin_telegram_id,
            actor_telegram_id=admin_telegram_id,
            payload={
                "count": checked_out_count,
                "total": totals['total']
            }
        )
        
        text = f"""✅ <b>Checkout Complete!</b>

<b>Admin:</b> {admin_name}
<b>Items Checked Out:</b> {checked_out_count}
<b>Total Amount:</b> {totals['total']:,} Toman
<b>Time:</b> {format_persian_datetime(datetime.now().isoformat())}

All items have been marked as ✅ checked out."""
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=self.get_back_keyboard()
        )
        await callback.answer("Checkout complete ✅", show_alert=True)

    async def show_settings(self, callback: CallbackQuery):
        """Show settings menu"""
        # Get current settings
        sync_status = await self.db.get_sync_status("initial_sync_complete")
        sync_emoji = "✅" if sync_status == "true" else "❌"
        
        api_status = "✅ Connected" if self.api_client else "❌ Not configured"
        chat_status = f"✅ {self.fallback_chat_id}" if self.fallback_chat_id else "❌ Not set"
        main_bot_admin = await self.db.get_sync_status("main_bot_admin_id")
        admin_status = f"✅ {main_bot_admin}" if main_bot_admin else "❌ Not set"
        
        text = f"""⚙️ <b>Settings</b>

<b>Current Configuration:</b>

<b>🔄 Sync Status:</b> {sync_emoji} {"Enabled" if sync_status == "true" else "Disabled"}
<b>📡 Panel API:</b> {api_status}
<b>💬 Forum Chat:</b> {chat_status}
<b>👤 Main Bot Admin:</b> {admin_status}

<i>Main Bot Admin manages topics for admins without telegram_id</i>

<b>Actions:</b>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Disable Sync" if sync_status == "true" else "🟢 Enable Sync",
                    callback_data=f"{MENU_PREFIX}set_toggle_sync"
                )
            ],
            [
                InlineKeyboardButton(text="� Set Main Bot Admin", callback_data=f"{MENU_PREFIX}set_main_admin")
            ],
            [
                InlineKeyboardButton(text="�🗑 Clear All Admins", callback_data=f"{MENU_PREFIX}set_clear_admins")
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
                
            elif action == "set_main_admin":
                # Show instruction to set main bot admin
                main_admin = await self.db.get_sync_status("main_bot_admin_id")
                current_text = f"Current: {main_admin}" if main_admin else "Not set"
                
                await callback.message.edit_text(
                    f"""👤 <b>Set Main Bot Admin</b>

{current_text}

To set the main bot admin:
1. Send <code>/setadmin YOUR_TELEGRAM_ID</code> to the bot
2. Or click the button below to use your ID

<i>This admin will manage topics for panel admins without telegram_id.</i>""",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Use My ID",
                                callback_data=f"{MENU_PREFIX}set_admin_me_{callback.from_user.id}"
                            )
                        ],
                        [
                            InlineKeyboardButton(text="🔙 Back", callback_data=f"{MENU_PREFIX}settings")
                        ]
                    ])
                )
                await callback.answer()
                
            elif action.startswith("set_admin_me_"):
                admin_id = action.replace("set_admin_me_", "")
                await self.db.set_sync_status("main_bot_admin_id", admin_id)
                await callback.answer(f"Main bot admin set to {admin_id} ✅", show_alert=True)
                await self.show_settings(callback)
                
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
                # Check permission - only the admin who owns the user can mark as paid
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                await self.handle_payment_status(callback, username, "Paid", clicker_id, clicker_name, current_time)
            
            elif action_type == "unpaid":
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                await self.handle_payment_status(callback, username, "Unpaid", clicker_id, clicker_name, current_time)
            
            elif action_type == "add_settlement":
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                await self.handle_add_settlement(callback, username, admin_telegram_id, clicker_id, clicker_name, current_time)
            
            elif action_type == "set_price":
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                await self.handle_set_price(callback, username, admin_telegram_id, event_key)
            
            elif action_type == "dismiss":
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                await self.handle_dismiss(callback, username, clicker_id, clicker_name, current_time)
            
            elif action_type.startswith("price_"):
                if not await self.check_admin_permission(clicker_id, admin_telegram_id, callback):
                    return
                # Handle price selection (price_50, price_100, etc.)
                price = action_type.replace("price_", "")
                await self.handle_price_selected(callback, username, price, admin_telegram_id, clicker_id, clicker_name, current_time)
            
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

    async def check_admin_permission(self, clicker_id: str, admin_telegram_id: str, callback: CallbackQuery) -> bool:
        """Check if the clicker is allowed to edit this user's data"""
        # Admin can only edit their own users
        if clicker_id != admin_telegram_id:
            await callback.answer("⛔ You can only manage your own users", show_alert=True)
            return False
        return True

    async def handle_add_settlement(self, callback: CallbackQuery, username: str, admin_telegram_id: str,
                                   clicker_id: str, clicker_name: str, current_time: str):
        """Handle add to settlement callbacks"""
        
        # Get user price if exists
        user_price = await self.db.get_user_price(username)
        price = user_price['price'] if user_price else None
        
        # Add to settlement list with admin info
        await self.db.add_to_settlement(username, admin_telegram_id, price, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Check if already added
        if "➕ Added to settlement list" in original_text:
            await callback.answer("Already added to settlement list", show_alert=False)
            return
        
        # Add settlement line
        price_text = f" ({price} Toman)" if price else ""
        settlement_line = f"\n➕ Added to settlement list{price_text} by {clicker_name} at {current_time}"
        new_text = original_text + settlement_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer("Added to settlement list ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("Added but error updating message")

    async def handle_set_price(self, callback: CallbackQuery, username: str, 
                              admin_telegram_id: str, event_key: str):
        """Handle set price button - show price options"""
        
        # Create price selection keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="50K",
                    callback_data=create_callback_data("price_50000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="100K",
                    callback_data=create_callback_data("price_100000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="150K",
                    callback_data=create_callback_data("price_150000", username, admin_telegram_id, event_key)
                )
            ],
            [
                InlineKeyboardButton(
                    text="200K",
                    callback_data=create_callback_data("price_200000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="250K",
                    callback_data=create_callback_data("price_250000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="300K",
                    callback_data=create_callback_data("price_300000", username, admin_telegram_id, event_key)
                )
            ],
            [
                InlineKeyboardButton(
                    text="400K",
                    callback_data=create_callback_data("price_400000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="500K",
                    callback_data=create_callback_data("price_500000", username, admin_telegram_id, event_key)
                ),
                InlineKeyboardButton(
                    text="Custom",
                    callback_data=create_callback_data("price_custom", username, admin_telegram_id, event_key)
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Cancel",
                    callback_data=create_callback_data("price_cancel", username, admin_telegram_id, event_key)
                )
            ]
        ])
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("Select price")

    async def handle_price_selected(self, callback: CallbackQuery, username: str, 
                                   price: str, admin_telegram_id: str, clicker_id: str, 
                                   clicker_name: str, current_time: str):
        """Handle price selection"""
        
        if price == "cancel":
            # Restore original keyboard
            original_keyboard = create_accounting_keyboard(
                username, 
                callback.data.split(":")[2] if ":" in callback.data else "",
                callback.data.split(":")[3] if ":" in callback.data else ""
            )
            await callback.message.edit_reply_markup(reply_markup=original_keyboard)
            await callback.answer("Cancelled")
            return
        
        if price == "custom":
            await callback.answer("Reply to this message with the custom price", show_alert=True)
            return
        
        # Format price for display
        price_int = int(price)
        if price_int >= 1000:
            price_display = f"{price_int // 1000}K"
        else:
            price_display = price
        
        # Save price to database
        await self.db.set_user_price(username, price, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Remove any existing price line
        lines = original_text.split('\n')
        filtered_lines = [line for line in lines if not line.startswith('💰 Price:')]
        
        # Add price line
        price_line = f"\n💰 Price: {price_display} Toman set by {clicker_name}"
        new_text = '\n'.join(filtered_lines) + price_line
        new_text = truncate_text(new_text)
        
        # Restore original keyboard
        callback_parts = parse_callback_data(callback.data)
        original_keyboard = create_accounting_keyboard(
            username,
            callback_parts.get('admin_telegram_id', ''),
            callback_parts.get('event_key', '')
        )
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=original_keyboard)
            await callback.answer(f"Price set: {price_display} ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("Price set but error updating message")

    async def handle_dismiss(self, callback: CallbackQuery, username: str, 
                            clicker_id: str, clicker_name: str, current_time: str):
        """Handle dismiss button - mark user as no payment needed"""
        
        # Check if already dismissed
        current_payment = await self.db.get_payment_status(username)
        if current_payment and current_payment['payment_status'] == 'Dismissed':
            await callback.answer("Already dismissed", show_alert=False)
            return
        
        # Dismiss payment
        await self.db.dismiss_payment(username, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Remove any existing payment/dismiss status line
        lines = original_text.split('\n')
        filtered_lines = [line for line in lines if not any(marker in line for marker in ['✅ Paid', '❌ Unpaid', '🚫 Dismissed'])]
        
        # Add dismiss line
        dismiss_line = f"\n🚫 Dismissed by {clicker_name} at {current_time}"
        new_text = '\n'.join(filtered_lines) + dismiss_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer("Dismissed - no payment needed ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("Dismissed but error updating message")


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
                text="💰 Set Price",
                callback_data=create_callback_data("set_price", username, admin_telegram_id, event_key)
            ),
            InlineKeyboardButton(
                text="🚫 Dismiss",
                callback_data=create_callback_data("dismiss", username, admin_telegram_id, event_key)
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
    
    # Check if admin already exists (by username)
    existing = await db.get_admin_topic(admin_username)
    if existing:
        # Update telegram_id if changed
        admin_telegram_id_str = str(admin_telegram_id) if admin_telegram_id else None
        if existing.get('admin_telegram_id') != admin_telegram_id_str:
            await db.set_admin_topic(
                admin_username=admin_username,
                admin_telegram_id=admin_telegram_id_str,
                chat_id=existing['chat_id'],
                topic_id=existing['topic_id'],
                managed_by=existing.get('managed_by')
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
    admin_telegram_id_str = str(admin_telegram_id) if admin_telegram_id else None
    await db.set_admin_topic(
        admin_username=admin_username,
        admin_telegram_id=admin_telegram_id_str,
        chat_id=target_chat_id or "",
        topic_id=topic_id,
        managed_by=None  # Webhook events always have admin_telegram_id
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
    
    # Get fallback values
    final_fallback_chat = fallback_chat_id or telegram_bot.fallback_chat_id
    final_fallback_topic = fallback_topic_id or telegram_bot.fallback_topic_id
    
    # Validate fallback chat ID format
    if final_fallback_chat and not final_fallback_chat.lstrip('-').isdigit():
        logger.error(f"Invalid FALLBACK_CHAT_ID: '{final_fallback_chat}' - must be a number like -1001234567890")
        return
    
    try:
        # Auto-register admin if new (creates topic automatically)
        chat_id, topic_id = await auto_register_admin(
            admin_telegram_id=admin_telegram_id,
            admin_username=admin_username,
            db=db,
            bot=telegram_bot.bot,
            target_chat_id=final_fallback_chat
        )
        
        # Use the returned values, fall back only if empty
        if not chat_id:
            chat_id = final_fallback_chat
        if not topic_id:
            topic_id = final_fallback_topic
        
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
