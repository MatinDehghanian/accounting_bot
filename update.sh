#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 PasarGuard Accounting Bot Update${NC}"
echo "====================================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ Error: main.py not found. Run this script from the project directory.${NC}"
    exit 1
fi

# Backup .env file
if [ -f ".env" ]; then
    echo -e "${YELLOW}📦 Backing up .env file...${NC}"
    cp .env .env.backup
    echo -e "${GREEN}✅ Backup created: .env.backup${NC}"
fi

# Backup database
if [ -f "accounting_bot.db" ]; then
    echo -e "${YELLOW}💾 Backing up database...${NC}"
    cp accounting_bot.db "accounting_bot.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✅ Database backup created${NC}"
fi

# Pull latest changes
echo -e "${YELLOW}📥 Pulling latest changes from git...${NC}"
git fetch origin

# Check if there are updates
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✅ Already up to date!${NC}"
    exit 0
fi

# Show what's new
echo -e "${BLUE}📋 Changes to be applied:${NC}"
git log --oneline HEAD..origin/main

# Pull changes
echo ""
echo -e "${YELLOW}🔄 Applying updates...${NC}"
git pull origin main

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Git pull failed. Please resolve conflicts manually.${NC}"
    exit 1
fi

# Detect deployment method and restart
if [ -f "docker-compose.yml" ] && (command -v docker &> /dev/null); then
    echo -e "${YELLOW}🐳 Docker detected. Rebuilding container...${NC}"
    docker compose down
    docker compose up -d --build
    
    echo -e "${YELLOW}⏳ Waiting for container to start...${NC}"
    sleep 5
    
    # Check if container is running
    if docker compose ps | grep -q "Up\|running"; then
        echo -e "${GREEN}✅ Container is running${NC}"
        echo -e "${BLUE}📋 Recent logs:${NC}"
        docker compose logs --tail=20 accounting-bot
    else
        echo -e "${RED}❌ Container failed to start. Check logs:${NC}"
        docker compose logs --tail=50 accounting-bot
        exit 1
    fi

elif [ -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}🐍 Virtual environment detected. Updating dependencies...${NC}"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    
    # Check if systemd service exists
    if systemctl is-active --quiet accounting-bot 2>/dev/null; then
        echo -e "${YELLOW}🔄 Restarting systemd service...${NC}"
        sudo systemctl restart accounting-bot
        sleep 3
        
        if systemctl is-active --quiet accounting-bot; then
            echo -e "${GREEN}✅ Service restarted successfully${NC}"
            sudo systemctl status accounting-bot --no-pager
        else
            echo -e "${RED}❌ Service failed to start${NC}"
            sudo journalctl -u accounting-bot --no-pager -n 30
            exit 1
        fi
    else
        echo -e "${YELLOW}ℹ️ No systemd service found.${NC}"
        echo -e "${BLUE}To restart manually:${NC}"
        echo "  1. Stop the current process (Ctrl+C or kill)"
        echo "  2. Run: source venv/bin/activate && python main.py"
    fi

else
    echo -e "${YELLOW}ℹ️ No deployment method detected.${NC}"
    echo -e "${BLUE}Please restart the bot manually:${NC}"
    echo "  Docker:  docker compose up -d --build"
    echo "  Venv:    source venv/bin/activate && python main.py"
fi

echo ""
echo -e "${GREEN}🎉 Update complete!${NC}"
echo -e "${BLUE}Check the CHANGELOG.md for what's new.${NC}"
