# Contributing to PasarGuard Accounting Bot

ما از مشارکت شما در توسعه این پروژه استقبال می‌کنیم! 

## 🚀 شروع سریع

### Fork کردن پروژه
1. روی دکمه "Fork" در گیت‌هاب کلیک کنید
2. Clone کردن fork خودتان:
```bash
git clone https://github.com/YOUR_USERNAME/pasarguard-accounting-bot.git
cd pasarguard-accounting-bot
```

### راه‌اندازی محیط توسعه
```bash
# نصب dependencies
./setup.sh

# کپی کردن تنظیمات
cp .env.example .env
# فایل .env را ویرایش کنید

# اجرای پروژه
python main.py
```

## 📋 راهنمای مشارکت

### انواع مشارکت

**🐛 گزارش باگ**
- Issue جدید با برچسب `bug` ایجاد کنید
- شرح دقیق از مشکل ارائه دهید
- مراحل تکرار مشکل را بنویسید

**✨ پیشنهاد ویژگی جدید**
- Issue جدید با برچسب `feature request` ایجاد کنید
- توضیح دهید چرا این ویژگی مفید است

**📖 بهبود مستندات**
- README یا Comments را بروزرسانی کنید
- مثال‌های جدید اضافه کنید

**🔧 بهبود کد**
- Refactoring کد موجود
- بهبود performance
- افزودن تست‌ها

### فرآیند توسعه

1. **Branch جدید ایجاد کنید:**
```bash
git checkout -b feature/your-feature-name
# یا
git checkout -b fix/bug-description
```

2. **تغییرات خود را commit کنید:**
```bash
git add .
git commit -m "feat: add new webhook processing feature"
```

3. **کد را تست کنید:**
```bash
# اجرای تست‌ها
pytest

# تست webhook
python test_webhook.py
```

4. **Pull Request ایجاد کنید:**
- توضیح کاملی از تغییرات ارائه دهید
- Screenshot یا مثال اضافه کنید
- مراجع issue مرتبط را ذکر کنید

## 📏 استانداردهای کد

### Python Style Guide
- از PEP 8 پیروی کنید
- خطوط حداکثر 127 کاراکتر
- از type hints استفاده کنید

### نام‌گذاری
```python
# Functions و variables: snake_case
def process_webhook_event():
    user_data = {}

# Classes: PascalCase  
class DatabaseManager:
    pass

# Constants: UPPER_CASE
MAX_RETRY_COUNT = 3
```

### Docstrings
```python
def format_persian_datetime(dt_string: Optional[str]) -> str:
    """
    Format datetime to Persian readable format
    
    Args:
        dt_string: ISO format datetime string
        
    Returns:
        Formatted Persian date string
        
    Example:
        >>> format_persian_datetime("2026-02-05T10:30:00Z")
        "1404/11/16 - 14:00"
    """
```

### Commit Messages
از [Conventional Commits](https://www.conventionalcommits.org/) استفاده کنید:

```
feat: add payment status tracking
fix: resolve webhook parsing error  
docs: update installation guide
refactor: improve database queries
test: add webhook endpoint tests
```

## 🧪 تست‌ها

### اجرای تست‌ها
```bash
# همه تست‌ها
pytest

# تست‌های مشخص
pytest tests/test_webhook.py

# با coverage
pytest --cov=./
```

### نوشتن تست جدید
```python
# tests/test_new_feature.py
import pytest
from your_module import your_function

def test_your_function():
    result = your_function(test_input)
    assert result == expected_output
```

## 🔒 Security

- هرگز secrets یا tokens را commit نکنید
- از environment variables استفاده کنید
- Input validation را جدی بگیرید

## 📝 Documentation

### README Updates
- ویژگی‌های جدید را مستند کنید
- مثال‌های کاربردی اضافه کنید
- Screenshots و GIF ها مفید هستند

### Code Comments
- کد پیچیده را توضیح دهید
- منطق business را شرح دهید
- TODO ها را مشخص کنید

## 🎯 Priority Areas

ما به دنبال کمک در این زمینه‌ها هستیم:

1. **🧪 Test Coverage** - افزودن unit tests و integration tests
2. **📊 Monitoring** - metrics و logging بهتر  
3. **🌐 Internationalization** - پشتیبانی از زبان‌های بیشتر
4. **📱 Mobile Support** - بهبود UX در موبایل
5. **🚀 Performance** - بهینه‌سازی database queries
6. **🔐 Security** - security audit و improvements

## 💬 ارتباط

- **Issues**: برای باگ‌ها و پیشنهادات
- **Discussions**: برای سوالات و بحث‌های کلی
- **Email**: برای موارد خصوصی و security

## 🏷️ Labels

- `bug` - مشکلات و خرابی‌ها
- `enhancement` - ویژگی‌های جدید
- `documentation` - بهبود مستندات
- `good first issue` - مناسب برای مبتدیان
- `help wanted` - نیاز به کمک
- `question` - سوالات

## 📜 Code of Conduct

لطفاً محترمانه و سازنده باشید. ما یک جامعه باز و دوستانه هستیم.

---

🙏 از مشارکت شما متشکریم!