from fastapi import FastAPI, Request, HTTPException, Header
from typing import List, Dict, Optional
import asyncio
import logging
from datetime import datetime, timezone

from database import Database
from telegram_bot import TelegramBot, send_to_admin_topic
from utils import (
    calculate_days_difference, 
    parse_datetime, 
    format_persian_datetime,
    generate_event_key,
    safe_get_nested
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
app = FastAPI(title="Accounting Bot Webhook Receiver")
db = Database()
telegram_bot = TelegramBot()


@app.on_event("startup")
async def startup():
    """Initialize database and telegram bot on startup"""
    await db.init_db()
    await telegram_bot.init()
    logger.info("Webhook receiver started successfully")


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="x-webhook-secret")
):
    """Receive webhook notifications from PasarGuard panel"""
    
    # Log incoming request
    logger.info(f"📥 Webhook received from {request.client.host if request.client else 'unknown'}")
    
    # Optional: Verify webhook secret
    # expected_secret = "your-webhook-secret"
    # if expected_secret and x_webhook_secret != expected_secret:
    #     raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    try:
        # Parse webhook data (should be a list of events)
        raw_body = await request.body()
        logger.info(f"📦 Raw webhook body: {raw_body.decode('utf-8')[:500]}")
        
        events = await request.json()
        
        if not isinstance(events, list):
            logger.warning(f"Webhook data is not a list, wrapping: {type(events)}")
            events = [events]  # Wrap single event in list
        
        logger.info(f"📋 Processing {len(events)} webhook events")
        
        # Process each event
        processed_count = 0
        for event in events:
            try:
                action = event.get('action', 'unknown')
                username = event.get('username', 'unknown')
                logger.info(f"🔄 Processing event: {action} for user {username}")
                await process_webhook_event(event)
                processed_count += 1
            except Exception as e:
                logger.error(f"❌ Error processing event {event.get('username', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"✅ Processed {processed_count}/{len(events)} webhook events")
        
        return {"status": "ok", "processed": processed_count, "total": len(events)}
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Webhook processing failed: {str(e)}")


async def process_webhook_event(event: Dict):
    """Process individual webhook event"""
    
    # Extract basic event data
    action = event.get('action')
    username = event.get('username')
    user_data = event.get('user', {})
    by_data = event.get('by', {})
    send_at = event.get('send_at', 0)
    
    # Validate required fields
    if not action or not username or not user_data:
        logger.warning(f"Invalid event data: missing required fields")
        return
    
    # Log the event
    await db.log_audit(
        log_type="webhook_received",
        username=username,
        admin_telegram_id=by_data.get('telegram_id'),
        payload=event
    )
    
    # Check if sync is complete
    sync_status = await db.get_sync_status("initial_sync_complete")
    if sync_status != "true" and action == "user_updated":
        logger.info(f"Skipping user_updated for {username} - initial sync not complete")
        return
    
    # Process based on action type
    if action == "user_created":
        await handle_user_created(event)
    elif action == "user_updated":
        await handle_user_updated(event)
    else:
        logger.info(f"Ignoring unsupported action: {action}")


async def handle_user_created(event: Dict):
    """Handle user_created event - always send message"""
    
    username = event.get('username')
    user_data = event.get('user', {})
    by_data = event.get('by', {})
    send_at = event.get('send_at', 0)
    
    # Save user snapshot
    await db.save_user_snapshot(
        username=username,
        status=user_data.get('status'),
        expire=user_data.get('expire')
    )
    
    # Create message
    message = create_user_created_message(event)
    
    # Generate unique event key
    event_key = generate_event_key("created", username, send_at)
    
    # Send to admin topic
    admin_telegram_id = by_data.get('telegram_id')
    if admin_telegram_id:
        await send_to_admin_topic(
            admin_telegram_id=str(admin_telegram_id),
            admin_username=by_data.get('username', 'unknown'),
            message=message,
            username=username,
            event_key=event_key,
            db=db
        )
    
    logger.info(f"Processed user_created for {username} by admin {admin_telegram_id}")


async def handle_user_updated(event: Dict):
    """Handle user_updated event - send only in specific conditions"""
    
    username = event.get('username')
    user_data = event.get('user', {})
    by_data = event.get('by', {})
    send_at = event.get('send_at', 0)
    
    # Get old snapshot
    old_snapshot = await db.get_user_snapshot(username)
    
    if not old_snapshot:
        logger.info(f"No snapshot found for {username}, saving current state and skipping")
        await db.save_user_snapshot(
            username=username,
            status=user_data.get('status'),
            expire=user_data.get('expire')
        )
        return
    
    # Check conditions for sending message
    should_send = False
    trigger_reason = ""
    
    # Condition A: Expire increased by at least 7 days
    old_expire = old_snapshot.get('expire')
    new_expire = user_data.get('expire')
    
    if old_expire and new_expire:
        days_diff = calculate_days_difference(old_expire, new_expire)
        if days_diff and days_diff >= 7:
            should_send = True
            trigger_reason = f"expire_extended_{days_diff}_days"
    
    # Condition B: Status changed to on_hold
    old_status = old_snapshot.get('status')
    new_status = user_data.get('status')
    
    if old_status != "on_hold" and new_status == "on_hold":
        should_send = True
        trigger_reason = f"status_to_on_hold"
    
    # Update snapshot regardless
    await db.save_user_snapshot(
        username=username,
        status=new_status,
        expire=new_expire
    )
    
    # Send message if conditions met
    if should_send:
        message = create_user_updated_message(event, old_snapshot, trigger_reason)
        event_key = generate_event_key("updated", username, send_at)
        
        admin_telegram_id = by_data.get('telegram_id')
        if admin_telegram_id:
            await send_to_admin_topic(
                admin_telegram_id=str(admin_telegram_id),
                admin_username=by_data.get('username', 'unknown'),
                message=message,
                username=username,
                event_key=event_key,
                db=db
            )
        
        logger.info(f"Processed user_updated for {username} - trigger: {trigger_reason}")
    else:
        logger.info(f"Skipped user_updated for {username} - no trigger conditions met")


def create_user_created_message(event: Dict) -> str:
    """Create formatted message for user_created event"""
    
    username = event.get('username')
    user_data = event.get('user', {})
    by_data = event.get('by', {})
    send_at = event.get('send_at', 0)
    
    user_id = user_data.get('id', 'Unknown')
    status = user_data.get('status', 'unknown')
    expire = user_data.get('expire')
    data_limit = user_data.get('data_limit', 0)
    
    admin_username = by_data.get('username', 'Unknown')
    admin_tg_id = by_data.get('telegram_id', 'Unknown')
    
    expire_str = format_persian_datetime(expire) if expire else 'Unlimited'
    data_limit_str = f"{data_limit // (1024**3):.1f} GB" if data_limit > 0 else 'Unlimited'
    
    send_time = datetime.fromtimestamp(send_at, tz=timezone.utc)
    send_time_str = format_persian_datetime(send_time.isoformat())
    
    message = f"""🧾 <b>Accounting | user_created</b>

👤 <b>User:</b> <code>{username}</code> (id: {user_id})
👮 <b>Admin:</b> {admin_username} (tg_id: {admin_tg_id})

<b>Details:</b>
⚡ Status: {status}
📊 Data Limit: {data_limit_str}
📅 Expire: {expire_str}
🕐 Created: {send_time_str}"""

    return message


def create_user_updated_message(event: Dict, old_snapshot: Dict, trigger_reason: str) -> str:
    """Create formatted message for user_updated event"""
    
    username = event.get('username')
    user_data = event.get('user', {})
    by_data = event.get('by', {})
    send_at = event.get('send_at', 0)
    
    user_id = user_data.get('id', 'Unknown')
    new_status = user_data.get('status', 'unknown')
    new_expire = user_data.get('expire')
    
    old_status = old_snapshot.get('status', 'unknown')
    old_expire = old_snapshot.get('expire')
    
    admin_username = by_data.get('username', 'Unknown')
    admin_tg_id = by_data.get('telegram_id', 'Unknown')
    
    send_time = datetime.fromtimestamp(send_at, tz=timezone.utc)
    send_time_str = format_persian_datetime(send_time.isoformat())
    
    message = f"""🧾 <b>Accounting | user_updated</b>

👤 <b>User:</b> <code>{username}</code> (id: {user_id})
👮 <b>Admin:</b> {admin_username} (tg_id: {admin_tg_id})

<b>Details:</b>
⚡ Status: {new_status}
📅 Expire: {format_persian_datetime(new_expire) if new_expire else 'Unlimited'}
🕐 Updated: {send_time_str}"""

    # Add trigger-specific information
    if "expire_extended" in trigger_reason:
        days_diff = trigger_reason.split('_')[2]
        old_expire_str = format_persian_datetime(old_expire) if old_expire else 'Unlimited'
        new_expire_str = format_persian_datetime(new_expire) if new_expire else 'Unlimited'
        message += f"""

🔄 <b>Expiry Change:</b>
📅 Before: {old_expire_str}
📅 After: {new_expire_str}
⬆️ Extended: +{days_diff} days"""
    
    elif "status_to_on_hold" in trigger_reason:
        message += f"""

🔄 <b>Status Change:</b>
⚡ Before: {old_status}
⚡ After: {new_status}"""

    return message


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/webhook/test")
async def webhook_test():
    """Test endpoint to verify webhook URL is accessible"""
    sync_status = await db.get_sync_status("initial_sync_complete")
    admin_count = len(await db.get_all_admin_topics())
    
    return {
        "status": "ok",
        "message": "Webhook endpoint is accessible",
        "sync_enabled": sync_status == "true",
        "registered_admins": admin_count,
        "webhook_url": "/webhook (POST)",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/webhook/simulate")
async def simulate_webhook(request: Request):
    """Simulate a webhook event for testing (use only in development)"""
    try:
        data = await request.json()
        
        # Create a test event if not provided
        if not data:
            data = [{
                "action": "user_created",
                "username": "test_user",
                "send_at": int(datetime.now().timestamp()),
                "user": {
                    "id": 999,
                    "username": "test_user",
                    "status": "active",
                    "expire": datetime.now(timezone.utc).isoformat(),
                    "data_limit": 10737418240
                },
                "by": {
                    "id": 1,
                    "username": "test_admin",
                    "telegram_id": None  # Will use fallback
                }
            }]
        
        logger.info(f"Simulating webhook with data: {data}")
        
        # Process like a real webhook
        if not isinstance(data, list):
            data = [data]
        
        processed = 0
        for event in data:
            try:
                await process_webhook_event(event)
                processed += 1
            except Exception as e:
                logger.error(f"Simulation error: {e}")
        
        return {
            "status": "simulated",
            "processed": processed,
            "total": len(data)
        }
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/stats")
async def get_stats():
    """Get bot statistics"""
    try:
        # Get some basic stats from database
        # This is a simple implementation - you can expand it
        return {
            "status": "operational",
            "database": "connected",
            "telegram_bot": "active"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}