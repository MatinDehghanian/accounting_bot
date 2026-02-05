from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jdatetime
from dateutil import parser
import re


def format_bytes(bytes_value: int) -> str:
    """تبدیل بایت به فرمت قابل خواندن"""
    if not bytes_value:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def parse_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """Parse datetime string to datetime object"""
    if not date_string:
        return None
    
    try:
        # Try parsing ISO format first
        return parser.isoparse(date_string)
    except:
        try:
            # Fallback to standard formats
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            return None


def format_persian_datetime(dt_string: Optional[str]) -> str:
    """Format datetime to Persian readable format"""
    if not dt_string:
        return "نامشخص"
    
    dt = parse_datetime(dt_string)
    if not dt:
        return "نامشخص"
    
    # Convert to Tehran timezone (UTC+3:30)
    tehran_dt = dt.astimezone(timezone(timedelta(hours=3, minutes=30)))
    
    # Convert to Jalali
    j_date = jdatetime.datetime.fromgregorian(datetime=tehran_dt)
    
    return j_date.strftime("%Y/%m/%d - %H:%M")


def calculate_days_difference(date1_str: Optional[str], date2_str: Optional[str]) -> Optional[int]:
    """Calculate days difference between two dates"""
    if not date1_str or not date2_str:
        return None
    
    dt1 = parse_datetime(date1_str)
    dt2 = parse_datetime(date2_str)
    
    if not dt1 or not dt2:
        return None
    
    return (dt2 - dt1).days


def calculate_days_left(expire_str: Optional[str]) -> Optional[int]:
    """Calculate days left until expiration"""
    if not expire_str:
        return None
    
    expire_dt = parse_datetime(expire_str)
    if not expire_dt:
        return None
    
    now = datetime.now(timezone.utc)
    return (expire_dt - now).days


def get_status_emoji(status: str) -> str:
    """Get emoji for user status"""
    status_emojis = {
        "active": "✅ فعال",
        "disabled": "❌ غیرفعال", 
        "limited": "🪫 محدود",
        "expired": "📅 منقضی",
        "on_hold": "🕔 در انتظار"
    }
    return status_emojis.get(status, f"❓ {status}")


def generate_event_key(action: str, username: str, send_at: float) -> str:
    """Generate unique event key for callback data"""
    return f"{action}_{username}_{int(send_at)}"


def create_callback_data(action_type: str, username: str, admin_telegram_id: str, event_key: str) -> str:
    """Create callback data string (max 64 chars)"""
    # Truncate if too long
    callback = f"{action_type}:{username}:{admin_telegram_id}:{event_key}"
    return callback[:64] if len(callback) > 64 else callback


def parse_callback_data(callback_data: str) -> Dict[str, str]:
    """Parse callback data string"""
    parts = callback_data.split(':', 3)
    if len(parts) != 4:
        raise ValueError("Invalid callback data format")
    
    return {
        'action_type': parts[0],
        'username': parts[1], 
        'admin_telegram_id': parts[2],
        'event_key': parts[3]
    }


def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def safe_get_nested(data: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary values"""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def format_user_info(user_data: Dict) -> str:
    """Format user information for display"""
    username = user_data.get('username', 'نامشخص')
    user_id = user_data.get('id', 'نامشخص')
    status = get_status_emoji(user_data.get('status', 'unknown'))
    
    expire = user_data.get('expire')
    expire_str = format_persian_datetime(expire) if expire else 'نامحدود'
    
    data_limit = user_data.get('data_limit', 0)
    used_traffic = user_data.get('used_traffic', 0)
    
    data_limit_str = format_bytes(data_limit) if data_limit else 'نامحدود'
    used_traffic_str = format_bytes(used_traffic)
    
    usage_percent = (used_traffic / data_limit * 100) if data_limit > 0 else 0
    
    return f"""👤 User: {username} (id: {user_id})
⚡ Status: {status}
📊 Usage: {used_traffic_str} / {data_limit_str} ({usage_percent:.1f}%)
📅 Expire: {expire_str}"""


def truncate_text(text: str, max_length: int = 4000) -> str:
    """Truncate text to fit Telegram message limits"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."