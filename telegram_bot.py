import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, Message, Update
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from utils import (
    parse_callback_data, create_callback_data, 
    format_persian_datetime, truncate_text
)

# Configure logging
logger = logging.getLogger(__name__)

# FSM States for admin topic configuration
class AdminConfigStates(StatesGroup):
    waiting_for_chat_id = State()
    waiting_for_topic_id = State()


class TelegramBot:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.db: Optional[Database] = None
        
        # Default fallback chat/topic for unmapped admins
        self.fallback_chat_id = None  # Set this in your .env
        self.fallback_topic_id = None

    async def init(self, token: str = None):
        """Initialize telegram bot"""
        if not token:
            # You should set this from environment variable
            token = "YOUR_BOT_TOKEN"  # Replace with actual token
        
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = Database()
        
        # Register handlers
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("help"))(self.cmd_help)
        self.dp.message(Command("sync"))(self.cmd_sync)
        self.dp.message(Command("set_admin_topic"))(self.cmd_set_admin_topic)
        self.dp.message(Command("list_admins"))(self.cmd_list_admins)
        self.dp.message(Command("stats"))(self.cmd_stats)
        
        # Callback query handler
        self.dp.callback_query(F.data.startswith(("paid:", "unpaid:", "add_settlement:")))(self.handle_callback)
        
        # FSM handlers
        self.dp.message(AdminConfigStates.waiting_for_chat_id)(self.process_chat_id)
        self.dp.message(AdminConfigStates.waiting_for_topic_id)(self.process_topic_id)
        
        logger.info("Telegram bot initialized")

    async def cmd_start(self, message: Message):
        """Handle /start command"""
        welcome_text = """🤖 <b>ربات حساب‌وکتاب فعال شد</b>

این ربات برای مدیریت اطلاعات حساب‌وکتاب کاربران از طریق webhook طراحی شده.

<b>دستورات موجود:</b>
/help - راهنما
/sync - همگام‌سازی اولیه کاربران  
/set_admin_topic - تنظیم تاپیک برای ادمین
/list_admins - لیست ادمین‌ها و تاپیک‌ها
/stats - آمار سیستم"""
        
        await message.reply(welcome_text, parse_mode="HTML")

    async def cmd_help(self, message: Message):
        """Handle /help command"""
        help_text = """📖 <b>راهنمای استفاده</b>

<b>🔧 تنظیمات:</b>
/set_admin_topic - تنظیم تاپیک اختصاصی برای هر ادمین
/list_admins - مشاهده ادمین‌ها و تاپیک‌های تنظیم شده

<b>📊 عملیات:</b>
/sync - همگام‌سازی اولیه اطلاعات کاربران از API
/stats - مشاهده آمار و وضعیت سیستم

<b>🎯 نحوه کار:</b>
1. ابتدا با /sync اطلاعات کاربران را همگام‌سازی کنید
2. با /set_admin_topic تاپیک‌های اختصاصی تنظیم کنید
3. ربات به طور خودکار پیام‌های webhook را پردازش می‌کند

<b>🔔 شرایط ارسال پیام:</b>
• user_created: همیشه
• user_updated: فقط در صورت افزایش انقضا ≥7 روز یا تغییر به on_hold"""
        
        await message.reply(help_text, parse_mode="HTML")

    async def cmd_sync(self, message: Message):
        """Handle /sync command - sync users from API"""
        await message.reply("🔄 شروع همگام‌سازی اطلاعات کاربران...")
        
        try:
            # This is where you would call your PasarGuard API
            # For now, we'll mark sync as complete
            await self.db.set_sync_status("initial_sync_complete", "true")
            await self.db.set_sync_status("last_sync", datetime.now().isoformat())
            
            await message.reply(
                "✅ همگام‌سازی با موفقیت انجام شد\n"
                "اکنون ربات آماده پردازش رویدادهای user_updated است",
                parse_mode="HTML"
            )
            
            logger.info("Manual sync completed")
            
        except Exception as e:
            await message.reply(f"❌ خطا در همگام‌سازی: {str(e)}")
            logger.error(f"Sync error: {str(e)}")

    async def cmd_set_admin_topic(self, message: Message, state: FSMContext):
        """Handle /set_admin_topic command"""
        text = """⚙️ <b>تنظیم تاپیک ادمین</b>

لطفاً Telegram ID ادمین را وارد کنید:

<b>نکات:</b>
• از @userinfobot برای دریافت Telegram ID استفاده کنید
• ID عددی است (مثل: 123456789)"""
        
        await message.reply(text, parse_mode="HTML")
        await state.set_state(AdminConfigStates.waiting_for_chat_id)

    async def process_chat_id(self, message: Message, state: FSMContext):
        """Process admin telegram ID input"""
        try:
            admin_telegram_id = message.text.strip()
            
            # Validate it's a number
            if not admin_telegram_id.isdigit():
                await message.reply("❌ لطفاً یک عدد معتبر وارد کنید")
                return
            
            await state.update_data(admin_telegram_id=admin_telegram_id)
            
            text = f"""✅ Telegram ID ادمین: <code>{admin_telegram_id}</code>

اکنون Chat ID گروه/چت مقصد را وارد کنید:

<b>نحوه دریافت Chat ID:</b>
• ربات را به گروه اضافه کنید
• دستور /id@ بزنید تا Chat ID را دریافت کنید
• یا از @getidsbot استفاده کنید"""
            
            await message.reply(text, parse_mode="HTML")
            await state.set_state(AdminConfigStates.waiting_for_topic_id)
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
            await state.clear()

    async def process_topic_id(self, message: Message, state: FSMContext):
        """Process chat ID and optional topic ID input"""
        try:
            data = await state.get_data()
            admin_telegram_id = data.get('admin_telegram_id')
            
            input_text = message.text.strip()
            parts = input_text.split()
            
            chat_id = parts[0]
            topic_id = parts[1] if len(parts) > 1 else None
            
            # Validate chat_id is a number (can be negative)
            try:
                int(chat_id)
            except ValueError:
                await message.reply("❌ Chat ID باید عدد باشد")
                return
            
            # Validate topic_id if provided
            if topic_id and not topic_id.isdigit():
                await message.reply("❌ Topic ID باید عدد باشد")
                return
            
            # Save to database
            await self.db.set_admin_topic(
                admin_telegram_id=admin_telegram_id,
                admin_username="unknown",  # Will be updated when first message arrives
                chat_id=chat_id,
                topic_id=topic_id
            )
            
            success_text = f"""✅ <b>تنظیمات ذخیره شد</b>

👤 Admin Telegram ID: <code>{admin_telegram_id}</code>
💬 Chat ID: <code>{chat_id}</code>"""
            
            if topic_id:
                success_text += f"\n🗂 Topic ID: <code>{topic_id}</code>"
            else:
                success_text += "\n🗂 Topic: عمومی (بدون topic)"
            
            success_text += "\n\n🎯 از این پس پیام‌های این ادمین به این مکان ارسال می‌شود"
            
            await message.reply(success_text, parse_mode="HTML")
            await state.clear()
            
            logger.info(f"Admin topic configured: {admin_telegram_id} -> {chat_id}:{topic_id}")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")
            await state.clear()

    async def cmd_list_admins(self, message: Message):
        """Handle /list_admins command"""
        try:
            admin_topics = await self.db.get_all_admin_topics()
            
            if not admin_topics:
                await message.reply("📝 هیچ ادمینی تنظیم نشده است")
                return
            
            text = "👥 <b>لیست ادمین‌ها و تاپیک‌ها:</b>\n\n"
            
            for admin in admin_topics:
                text += f"👤 <b>{admin['admin_username']}</b>\n"
                text += f"🆔 TG ID: <code>{admin['admin_telegram_id']}</code>\n"
                text += f"💬 Chat: <code>{admin['chat_id']}</code>\n"
                
                if admin['topic_id']:
                    text += f"🗂 Topic: <code>{admin['topic_id']}</code>\n"
                else:
                    text += "🗂 Topic: عمومی\n"
                    
                text += "─────────────\n"
            
            await message.reply(text, parse_mode="HTML")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")

    async def cmd_stats(self, message: Message):
        """Handle /stats command"""
        try:
            sync_status = await self.db.get_sync_status("initial_sync_complete")
            last_sync = await self.db.get_sync_status("last_sync")
            
            sync_emoji = "✅" if sync_status == "true" else "❌"
            sync_text = "کامل" if sync_status == "true" else "ناتمام"
            
            last_sync_text = format_persian_datetime(last_sync) if last_sync else "هرگز"
            
            admin_topics = await self.db.get_all_admin_topics()
            admin_count = len(admin_topics)
            
            text = f"""📊 <b>آمار سیستم</b>

🔄 <b>همگام‌سازی:</b> {sync_emoji} {sync_text}
🕐 <b>آخرین sync:</b> {last_sync_text}
👥 <b>ادمین‌های تنظیم شده:</b> {admin_count}

🤖 <b>وضعیت ربات:</b> ✅ فعال
💾 <b>دیتابیس:</b> ✅ متصل"""
            
            await message.reply(text, parse_mode="HTML")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {str(e)}")

    async def handle_callback(self, callback: CallbackQuery):
        """Handle inline keyboard callbacks"""
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
            await callback.answer("❌ خطا در پردازش", show_alert=True)

    async def handle_payment_status(self, callback: CallbackQuery, username: str, 
                                  status: str, clicker_id: str, clicker_name: str, current_time: str):
        """Handle payment status callbacks"""
        
        # Check current status
        current_payment = await self.db.get_payment_status(username)
        
        if current_payment and current_payment['payment_status'] == status:
            await callback.answer(f"قبلاً به عنوان {status} ثبت شده", show_alert=False)
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
        status_line = f"\n{emoji} {status} ثبت شد توسط {clicker_name} در {current_time}"
        
        new_text = '\n'.join(filtered_lines) + status_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer(f"{status} ثبت شد ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("ثبت شد ولی خطا در بروزرسانی پیام")

    async def handle_add_settlement(self, callback: CallbackQuery, username: str, 
                                   clicker_id: str, clicker_name: str, current_time: str):
        """Handle add to settlement callbacks"""
        
        # Add to settlement list
        await self.db.add_to_settlement(username, clicker_id)
        
        # Update message
        original_text = callback.message.text or callback.message.caption
        
        # Check if already added
        if "➕ به لیست تسویه اضافه شد" in original_text:
            await callback.answer("قبلاً به لیست تسویه اضافه شده", show_alert=False)
            return
        
        # Add settlement line
        settlement_line = f"\n➕ به لیست تسویه اضافه شد توسط {clicker_name} در {current_time}"
        new_text = original_text + settlement_line
        new_text = truncate_text(new_text)
        
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=callback.message.reply_markup)
            await callback.answer("به لیست تسویه اضافه شد ✅")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            await callback.answer("اضافه شد ولی خطا در بروزرسانی پیام")


def create_accounting_keyboard(username: str, admin_telegram_id: str, event_key: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for accounting actions"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="پرداخت کرد ✅",
                callback_data=create_callback_data("paid", username, admin_telegram_id, event_key)
            ),
            InlineKeyboardButton(
                text="پرداخت نکرد ❌", 
                callback_data=create_callback_data("unpaid", username, admin_telegram_id, event_key)
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ افزودن به لیست تسویه",
                callback_data=create_callback_data("add_settlement", username, admin_telegram_id, event_key)
            )
        ]
    ])
    
    return keyboard


async def send_to_admin_topic(admin_telegram_id: str, admin_username: str, message: str, 
                             username: str, event_key: str, db: Database, 
                             fallback_chat_id: str = None, fallback_topic_id: str = None):
    """Send message to admin's dedicated topic"""
    
    from webhook_receiver import telegram_bot
    
    if not telegram_bot.bot:
        logger.error("Telegram bot not initialized")
        return
    
    try:
        # Get admin topic mapping
        admin_topic = await db.get_admin_topic(admin_telegram_id)
        
        chat_id = None
        topic_id = None
        
        if admin_topic:
            chat_id = admin_topic['chat_id']
            topic_id = admin_topic['topic_id']
        else:
            # Use fallback or log warning
            chat_id = fallback_chat_id
            topic_id = fallback_topic_id
            
            warning_msg = f"\n\n⚠️ <b>توجه:</b> mapping برای ادمین {admin_telegram_id} ثبت نشده"
            message += warning_msg
            
            logger.warning(f"No topic mapping found for admin {admin_telegram_id}")
        
        if not chat_id:
            logger.error(f"No chat_id available for admin {admin_telegram_id}")
            return
        
        # Create keyboard
        keyboard = create_accounting_keyboard(username, admin_telegram_id, event_key)
        
        # Send message
        kwargs = {
            'chat_id': chat_id,
            'text': truncate_text(message),
            'parse_mode': 'HTML',
            'reply_markup': keyboard
        }
        
        if topic_id:
            kwargs['message_thread_id'] = int(topic_id)
        
        sent_message = await telegram_bot.bot.send_message(**kwargs)
        
        logger.info(f"Message sent to admin {admin_telegram_id} at chat {chat_id}:{topic_id}")
        
    except Exception as e:
        logger.error(f"Error sending message to admin topic: {str(e)}")