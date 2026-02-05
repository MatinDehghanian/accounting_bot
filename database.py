import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Get database path from environment variable
DEFAULT_DB_PATH = os.getenv('DB_PATH', 'accounting_bot.db')

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        logger.info(f"Database path: {self.db_path}")
        
        # Ensure parent directory exists
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            logger.info(f"Creating database directory: {db_dir}")
            db_dir.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users snapshot table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users_snapshot (
                    username TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    expire TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Payments tracking table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    username TEXT PRIMARY KEY,
                    payment_status TEXT CHECK(payment_status IN ('Paid', 'Unpaid', 'Dismissed', 'Unknown')) DEFAULT 'Unknown',
                    price TEXT,
                    last_set_by TEXT,
                    last_set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User prices table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_prices (
                    username TEXT PRIMARY KEY,
                    price TEXT NOT NULL,
                    set_by TEXT NOT NULL,
                    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Settlement list table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settlement_list (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    admin_telegram_id TEXT NOT NULL,
                    price TEXT,
                    added_by TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_checked_out BOOLEAN DEFAULT 0,
                    checked_out_at TIMESTAMP,
                    checked_out_by TEXT
                )
            """)
            
            # Create index for faster lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_settlement_admin 
                ON settlement_list(admin_telegram_id, is_checked_out)
            """)

            # Admin topics mapping table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_topics (
                    admin_telegram_id TEXT PRIMARY KEY,
                    admin_username TEXT,
                    chat_id TEXT NOT NULL,
                    topic_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Audit log table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    username TEXT,
                    admin_telegram_id TEXT,
                    actor_telegram_id TEXT,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sync status table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()
            logger.info("Database initialized successfully")

    async def get_user_snapshot(self, username: str) -> Optional[Dict]:
        """Get user snapshot from database"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users_snapshot WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def save_user_snapshot(self, username: str, status: str, expire: Optional[str]):
        """Save or update user snapshot"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users_snapshot (username, status, expire, updated_at)
                VALUES (?, ?, ?, ?)
            """, (username, status, expire, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_admin_topic(self, admin_telegram_id: str) -> Optional[Dict]:
        """Get admin topic mapping"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM admin_topics WHERE admin_telegram_id = ?",
                (admin_telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_admin_topic(self, admin_telegram_id: str, admin_username: str, 
                             chat_id: str, topic_id: Optional[str] = None):
        """Set admin topic mapping"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO admin_topics 
                (admin_telegram_id, admin_username, chat_id, topic_id)
                VALUES (?, ?, ?, ?)
            """, (admin_telegram_id, admin_username, chat_id, topic_id))
            await db.commit()

    async def set_payment_status(self, username: str, status: str, set_by: str):
        """Set payment status for user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO payments (username, payment_status, last_set_by, last_set_at)
                VALUES (?, ?, ?, ?)
            """, (username, status, set_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_payment_status(self, username: str) -> Optional[Dict]:
        """Get payment status for user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM payments WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_to_settlement(self, username: str, admin_telegram_id: str, price: str, added_by: str):
        """Add user to settlement list"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if already in active settlement
            cursor = await db.execute(
                "SELECT id FROM settlement_list WHERE username = ? AND admin_telegram_id = ? AND is_checked_out = 0",
                (username, admin_telegram_id)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # Update price if exists
                await db.execute("""
                    UPDATE settlement_list SET price = ?, added_by = ?, added_at = ?
                    WHERE id = ?
                """, (price, added_by, datetime.now(timezone.utc).isoformat(), existing[0]))
            else:
                # Insert new
                await db.execute("""
                    INSERT INTO settlement_list (username, admin_telegram_id, price, added_by, added_at, is_checked_out)
                    VALUES (?, ?, ?, ?, ?, 0)
                """, (username, admin_telegram_id, price, added_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_admin_settlement_list(self, admin_telegram_id: str, checked_out: bool = False) -> List[Dict]:
        """Get settlement list for an admin"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT s.*, p.price as user_price 
                FROM settlement_list s
                LEFT JOIN user_prices p ON s.username = p.username
                WHERE s.admin_telegram_id = ? AND s.is_checked_out = ?
                ORDER BY s.added_at DESC
            """, (admin_telegram_id, 1 if checked_out else 0))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def checkout_settlement(self, admin_telegram_id: str, checked_out_by: str) -> int:
        """Checkout all active settlement items for an admin"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE settlement_list 
                SET is_checked_out = 1, checked_out_at = ?, checked_out_by = ?
                WHERE admin_telegram_id = ? AND is_checked_out = 0
            """, (datetime.now(timezone.utc).isoformat(), checked_out_by, admin_telegram_id))
            await db.commit()
            return cursor.rowcount

    async def get_settlement_total(self, admin_telegram_id: str) -> Dict:
        """Get total settlement amount for an admin"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get items with prices
            cursor = await db.execute("""
                SELECT s.username, COALESCE(s.price, p.price, '0') as price
                FROM settlement_list s
                LEFT JOIN user_prices p ON s.username = p.username
                WHERE s.admin_telegram_id = ? AND s.is_checked_out = 0
            """, (admin_telegram_id,))
            rows = await cursor.fetchall()
            
            total = 0
            count = len(rows)
            items_with_price = 0
            items_without_price = 0
            
            for row in rows:
                try:
                    price = int(row['price']) if row['price'] else 0
                    if price > 0:
                        total += price
                        items_with_price += 1
                    else:
                        items_without_price += 1
                except (ValueError, TypeError):
                    items_without_price += 1
            
            return {
                'total': total,
                'count': count,
                'items_with_price': items_with_price,
                'items_without_price': items_without_price
            }

    async def log_audit(self, log_type: str, username: Optional[str] = None, 
                       admin_telegram_id: Optional[str] = None, 
                       actor_telegram_id: Optional[str] = None,
                       payload: Optional[Dict] = None):
        """Log audit event"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO audit_log 
                (type, username, admin_telegram_id, actor_telegram_id, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                log_type, username, admin_telegram_id, actor_telegram_id,
                json.dumps(payload) if payload else None,
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()

    async def get_sync_status(self, key: str) -> Optional[str]:
        """Get sync status"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM sync_status WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_sync_status(self, key: str, value: str):
        """Set sync status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO sync_status (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_all_admin_topics(self) -> List[Dict]:
        """Get all admin topic mappings"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM admin_topics")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_admin_topic(self, admin_telegram_id: str):
        """Delete admin topic mapping"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM admin_topics WHERE admin_telegram_id = ?",
                (admin_telegram_id,)
            )
            await db.commit()

    async def set_user_price(self, username: str, price: str, set_by: str):
        """Set price for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_prices (username, price, set_by, set_at)
                VALUES (?, ?, ?, ?)
            """, (username, price, set_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_user_price(self, username: str) -> Optional[Dict]:
        """Get price for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM user_prices WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def dismiss_payment(self, username: str, dismissed_by: str):
        """Mark user as dismissed (no payment needed)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO payments (username, payment_status, last_set_by, last_set_at)
                VALUES (?, 'Dismissed', ?, ?)
            """, (username, dismissed_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()