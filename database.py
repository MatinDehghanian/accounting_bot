import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict
import json
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "accounting_bot.db"):
        self.db_path = db_path

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
                    payment_status TEXT CHECK(payment_status IN ('Paid', 'Unpaid', 'Unknown')) DEFAULT 'Unknown',
                    last_set_by TEXT,
                    last_set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Settlement list table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settlement_list (
                    username TEXT PRIMARY KEY,
                    added_by TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
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

    async def add_to_settlement(self, username: str, added_by: str):
        """Add user to settlement list"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO settlement_list (username, added_by, added_at, is_active)
                VALUES (?, ?, ?, 1)
            """, (username, added_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()

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