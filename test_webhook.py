#!/usr/bin/env python3
"""
Test script for the Accounting Bot webhook endpoint
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta


# Test webhook data
TEST_WEBHOOK_DATA = [
    # Test user_created event
    {
        "action": "user_created",
        "username": "test_user_1",
        "user": {
            "id": 100,
            "username": "test_user_1", 
            "status": "active",
            "data_limit": 10737418240,  # 10GB
            "used_traffic": 0,
            "lifetime_used_traffic": 0,
            "expire": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "edit_at": None,
            "online_at": None,
            "subscription_url": "https://test.com/sub/test123",
            "admin": {
                "username": "test_admin",
                "is_sudo": True,
                "telegram_id": 123456789,
                "discord_webhook": None
            },
            "group_names": ["premium"],
            "note": "Test user",
            "auto_delete_in_days": None
        },
        "by": {
            "username": "test_admin",
            "is_sudo": True,
            "telegram_id": 123456789,
            "discord_webhook": None
        },
        "enqueued_at": datetime.now(timezone.utc).timestamp(),
        "send_at": datetime.now(timezone.utc).timestamp(),
        "tries": 0
    },
    
    # Test user_updated event (expire extension)
    {
        "action": "user_updated",
        "username": "test_user_2",
        "user": {
            "id": 101,
            "username": "test_user_2",
            "status": "active", 
            "data_limit": 21474836480,  # 20GB
            "used_traffic": 5368709120,  # 5GB
            "lifetime_used_traffic": 15728640000,
            "expire": (datetime.now(timezone.utc) + timedelta(days=40)).isoformat(),  # Extended by 10+ days
            "created_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "edit_at": datetime.now(timezone.utc).isoformat(),
            "online_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "subscription_url": "https://test.com/sub/test456",
            "admin": {
                "username": "admin2",
                "is_sudo": False,
                "telegram_id": 987654321,
                "discord_webhook": None
            },
            "group_names": ["vip", "premium"],
            "note": "Extended user",
            "auto_delete_in_days": None
        },
        "by": {
            "username": "admin2",
            "is_sudo": False,
            "telegram_id": 987654321,
            "discord_webhook": None
        },
        "enqueued_at": datetime.now(timezone.utc).timestamp(),
        "send_at": datetime.now(timezone.utc).timestamp(),
        "tries": 0
    },

    # Test user_updated event (status to on_hold)
    {
        "action": "user_updated",
        "username": "test_user_3", 
        "user": {
            "id": 102,
            "username": "test_user_3",
            "status": "on_hold",  # Changed to on_hold
            "data_limit": 5368709120,  # 5GB
            "used_traffic": 1073741824,  # 1GB
            "lifetime_used_traffic": 5368709120,
            "expire": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "edit_at": datetime.now(timezone.utc).isoformat(),
            "online_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "subscription_url": "https://test.com/sub/test789",
            "admin": {
                "username": "test_admin",
                "is_sudo": True,
                "telegram_id": 123456789,
                "discord_webhook": None
            },
            "group_names": ["basic"],
            "note": "On hold user",
            "auto_delete_in_days": None
        },
        "by": {
            "username": "test_admin", 
            "is_sudo": True,
            "telegram_id": 123456789,
            "discord_webhook": None
        },
        "enqueued_at": datetime.now(timezone.utc).timestamp(),
        "send_at": datetime.now(timezone.utc).timestamp(), 
        "tries": 0
    }
]


async def test_webhook(webhook_url: str, secret: str = None):
    """Test the webhook endpoint"""
    
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["x-webhook-secret"] = secret
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"🧪 Testing webhook: {webhook_url}")
            print(f"📦 Sending {len(TEST_WEBHOOK_DATA)} test events...")
            
            async with session.post(
                webhook_url,
                json=TEST_WEBHOOK_DATA,
                headers=headers
            ) as response:
                
                status = response.status
                response_text = await response.text()
                
                if status == 200:
                    print("✅ Webhook test successful!")
                    print(f"📊 Response: {response_text}")
                else:
                    print(f"❌ Webhook test failed with status {status}")
                    print(f"📝 Response: {response_text}")
                
                return status == 200
                
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            return False


async def test_health_endpoint(base_url: str):
    """Test the health endpoint"""
    
    health_url = f"{base_url}/health"
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"🏥 Testing health endpoint: {health_url}")
            
            async with session.get(health_url) as response:
                status = response.status
                response_data = await response.json()
                
                if status == 200:
                    print("✅ Health check passed!")
                    print(f"📊 Status: {response_data}")
                else:
                    print(f"❌ Health check failed with status {status}")
                
                return status == 200
                
        except Exception as e:
            print(f"❌ Health test failed: {str(e)}")
            return False


async def main():
    """Main test function"""
    
    print("🤖 Accounting Bot Webhook Tester")
    print("=" * 40)
    
    # Configuration
    base_url = input("Enter bot server URL (e.g. http://localhost:8080): ").strip()
    if not base_url:
        base_url = "http://localhost:8080"
    
    webhook_secret = input("Enter webhook secret (optional, press Enter to skip): ").strip()
    if not webhook_secret:
        webhook_secret = None
    
    print(f"\n🎯 Testing against: {base_url}")
    print("-" * 40)
    
    # Test health endpoint
    health_ok = await test_health_endpoint(base_url)
    
    if not health_ok:
        print("❌ Health check failed, aborting webhook test")
        return
    
    print("-" * 40)
    
    # Test webhook endpoint
    webhook_url = f"{base_url}/webhook"
    webhook_ok = await test_webhook(webhook_url, webhook_secret)
    
    print("-" * 40)
    
    if webhook_ok:
        print("🎉 All tests passed!")
        print("\n💡 Next steps:")
        print("1. Check your Telegram bot for test messages")
        print("2. Configure admin topic mappings with /set_admin_topic")
        print("3. Set up webhook URL in your PasarGuard panel")
    else:
        print("💥 Some tests failed!")
        print("\n🔍 Troubleshooting:")
        print("1. Make sure the bot server is running")
        print("2. Check the server logs for errors")  
        print("3. Verify webhook secret if configured")


if __name__ == "__main__":
    asyncio.run(main())