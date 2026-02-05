#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🤖 PasarGuard Accounting Bot Setup${NC}"
echo "=================================="

# Check if Python 3.8+ is installed
python_version=$(python3 -V 2>&1 | grep -Po '(?<=Python )(.+)')
if [[ -z "$python_version" ]]; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python version: $python_version${NC}"

# Create virtual environment
echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}⬆️ Upgrading pip...${NC}"
pip install --upgrade pip

# Install requirements
echo -e "${YELLOW}📥 Installing requirements...${NC}"
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚙️ Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${BLUE}ℹ️ Please edit .env file with your configuration${NC}"
fi

# Create systemd service file (optional)
echo -e "${YELLOW}🔧 Creating systemd service file...${NC}"
cat > accounting-bot.service << EOF
[Unit]
Description=PasarGuard Accounting Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✅ Setup completed!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Edit .env file with your bot token and settings"
echo "2. Start the bot: python main.py"
echo "3. (Optional) Install systemd service:"
echo "   sudo cp accounting-bot.service /etc/systemd/system/"
echo "   sudo systemctl enable accounting-bot"
echo "   sudo systemctl start accounting-bot"
echo ""
echo -e "${GREEN}🚀 Happy coding!${NC}"