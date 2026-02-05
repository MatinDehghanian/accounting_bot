# Contributing to Accounting Bot

We welcome your contributions to this project!

## 🚀 Quick Start

### Fork the Project
1. Click the "Fork" button on GitHub
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/accounting-bot.git
cd accounting-bot
```

### Setup Development Environment
```bash
# Install dependencies
./setup.sh

# Copy settings
cp .env.example .env
# Edit the .env file

# Run the project
python main.py
```

## 📋 Contribution Guide

### Types of Contributions

**🐛 Bug Reports**
- Create a new issue with the `bug` label
- Provide a detailed description of the problem
- Include steps to reproduce the issue

**✨ New Feature Suggestions**
- Create a new issue with the `feature request` label
- Explain why this feature would be useful

**📖 Documentation Improvements**
- Update README or Comments
- Add new examples

**🔧 Code Improvements**
- Refactor existing code
- Improve performance
- Add tests

### Development Process

1. **Create a new branch:**
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

2. **Commit your changes:**
```bash
git add .
git commit -m "feat: add new webhook processing feature"
```

3. **Test your code:**
```bash
# Run tests
pytest

# Test webhook
python test_webhook.py
```

4. **Create a Pull Request:**
- Provide a complete description of the changes
- Add screenshots or examples
- Reference related issues

## 📏 Code Standards

### Python Style
- Follow PEP 8
- Use type hints where possible
- Add docstrings to functions and classes

### Commit Messages
Use conventional commits format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

### Code Example
```python
async def process_webhook(event: Dict) -> bool:
    """
    Process a webhook event.
    
    Args:
        event: The webhook event dictionary
        
    Returns:
        True if processed successfully, False otherwise
    """
    try:
        # Implementation
        return True
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return False
```

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test
pytest test_webhook.py -v
```

### Write Tests
- Add tests for new features
- Ensure tests are isolated
- Use meaningful test names

## 📁 Project Structure

```
accounting_bot/
├── main.py              # Entry point
├── telegram_bot.py      # Bot logic & handlers
├── webhook_receiver.py  # FastAPI webhook endpoint
├── database.py          # Database operations
├── utils.py             # Utility functions
├── requirements.txt     # Dependencies
└── test_webhook.py      # Tests
```

## 🔍 Code Review

All pull requests will be reviewed:

1. **Functionality**: Does it work correctly?
2. **Code Quality**: Is it clean and maintainable?
3. **Tests**: Are there adequate tests?
4. **Documentation**: Is it well documented?

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You

Thank you for taking the time to contribute! Your help makes this project better for everyone.

---

If you have any questions, feel free to open an issue or start a discussion.
