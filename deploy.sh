#!/bin/bash

# Deploy script for PasarGuard Accounting Bot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 PasarGuard Accounting Bot Deployment${NC}"
echo "========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please create .env file from .env.example and configure it"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found!${NC}"
    echo "Please install Docker first"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found!${NC}"
    echo "Please install Docker Compose first"
    exit 1
fi

# Create data directory if it doesn't exist
echo -e "${YELLOW}📁 Creating data directory...${NC}"
mkdir -p data

# Set proper permissions
echo -e "${YELLOW}🔐 Setting permissions...${NC}"
chmod 755 data

# Build and start containers
echo -e "${YELLOW}🔨 Building and starting containers...${NC}"
if command -v docker-compose &> /dev/null; then
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
else
    docker compose down
    docker compose build --no-cache
    docker compose up -d
fi

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 10

# Check health
echo -e "${YELLOW}🏥 Checking service health...${NC}"
if curl -f http://localhost:8080/health &> /dev/null; then
    echo -e "${GREEN}✅ Bot is running successfully!${NC}"
    echo -e "${GREEN}🌐 Webhook endpoint: http://localhost:8080/webhook${NC}"
    echo -e "${GREEN}📊 Health check: http://localhost:8080/health${NC}"
    echo -e "${GREEN}📈 Stats endpoint: http://localhost:8080/stats${NC}"
else
    echo -e "${RED}❌ Bot health check failed!${NC}"
    echo "Check logs with: docker-compose logs accounting-bot"
    exit 1
fi

echo ""
echo -e "${BLUE}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure your admin topics with the bot: /set_admin_topic"
echo "2. Run initial sync: /sync"
echo "3. Set up webhook URL in your PasarGuard panel"
echo "4. Test with: python test_webhook.py"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "• View logs: docker-compose logs -f accounting-bot"
echo "• Stop: docker-compose down"
echo "• Restart: docker-compose restart"
echo "• Update: git pull && docker-compose up -d --build"