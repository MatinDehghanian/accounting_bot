# Changelog

تمام تغییرات مهم این پروژه در این فایل مستند می‌شود.

فرمت بر اساس [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) است و این پروژه از [Semantic Versioning](https://semver.org/spec/v2.0.0.html) پیروی می‌کند.

## [Unreleased]

### Added
- Initial release of PasarGuard Accounting Bot
- Webhook processing for `user_created` and `user_updated` events
- Smart admin topic routing system
- Interactive inline keyboards for payment tracking
- SQLite database with comprehensive schema
- Persian datetime formatting with Jalali calendar
- Docker deployment configuration
- Comprehensive testing suite
- CI/CD pipeline with GitHub Actions
- Audit logging for all operations
- Health check endpoints
- Bootstrap sync functionality

### Features

#### 🔄 Webhook Processing
- Process webhook arrays from PasarGuard panel
- Filter `user_updated` events (≥7 days expire extension or status change to on_hold)
- Always process `user_created` events
- Snapshot system for tracking user changes

#### 🎯 Admin Topic Routing
- Map admins to dedicated Telegram topics
- Fallback system for unmapped admins
- Dynamic admin username resolution
- Support for both group and direct message routing

#### 🎮 Interactive Features
- Payment status tracking (Paid/Unpaid)
- Settlement list management
- Inline keyboard with callback handling
- Message editing after button interactions
- Idempotent operations

#### 💾 Database System
- `users_snapshot` - User state tracking
- `payments` - Payment status management
- `settlement_list` - Settlement tracking
- `admin_topics` - Admin routing configuration
- `audit_log` - Complete operation logging
- `sync_status` - Synchronization state

#### 🤖 Telegram Bot Commands
- `/start` - Welcome and introduction
- `/help` - Complete usage guide
- `/sync` - Initial user synchronization
- `/set_admin_topic` - Configure admin topic mapping
- `/list_admins` - View all admin configurations  
- `/stats` - System statistics and health

#### 🐳 Deployment
- Docker containerization
- Docker Compose configuration
- GitHub Actions CI/CD pipeline
- Health check endpoints
- Graceful shutdown handling
- SSL/TLS ready with nginx

#### 🧪 Testing & Development
- Comprehensive test suite
- Webhook testing script
- Development environment setup
- Code quality checks with flake8
- Coverage reporting

### Technical Details
- Python 3.8+ support
- Async/await throughout
- Type hints for better code quality
- Proper error handling and logging
- Persian/Jalali date support
- Telegram Bot API v3.x compatibility
- FastAPI for webhook endpoints
- SQLite with aiosqlite for async operations

---

## [1.0.0] - 2026-02-05

### Added
- Initial project setup and migration from PasarGuard panel repository
- Complete feature set as described above

### Notes
- This version represents the initial standalone release
- Migrated from monolithic PasarGuard panel to dedicated microservice
- Full backward compatibility with existing PasarGuard webhook format