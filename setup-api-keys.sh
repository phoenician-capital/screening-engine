#!/bin/bash
set -e

INSTANCE_IP="13.49.7.145"
KEY_PATH="${1:-$HOME/.ssh/phoenician-bastion.pem}"

echo "🔑 Phoenician Capital API Keys Setup"
echo "===================================="
echo ""
echo "This script will help you configure API keys on your EC2 instance."
echo ""
echo "Required API Keys:"
echo "  1. ANTHROPIC_API_KEY - Get from: https://console.anthropic.com/"
echo "  2. OPENAI_API_KEY - Get from: https://platform.openai.com/api-keys"
echo ""
echo "Optional API Keys (for enhanced features):"
echo "  - PERPLEXITY_API_KEY - Get from: https://www.perplexity.ai/settings/api"
echo "  - GOOGLE_API_KEY - Get from: https://console.cloud.google.com/"
echo ""

# Prompt for API keys
read -p "Enter ANTHROPIC_API_KEY (sk-ant-...): " ANTHROPIC_KEY
read -p "Enter OPENAI_API_KEY (sk-...): " OPENAI_KEY
read -p "Enter PERPLEXITY_API_KEY (optional, press Enter to skip): " PERPLEXITY_KEY
read -p "Enter GOOGLE_API_KEY (optional, press Enter to skip): " GOOGLE_KEY

echo ""
echo "🚀 Configuring environment on EC2..."

# Create .env file on EC2
ssh -i "$KEY_PATH" ubuntu@$INSTANCE_IP << SETUP_EOF
cd /home/ubuntu/screening-engine

cat > .env << 'ENVEOF'
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

DB_HOST=db
DB_PORT=5432
DB_NAME=phoenician
DB_USER=phoenician
DB_PASSWORD=change_me_in_production

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# LLM API Keys
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
OPENAI_API_KEY=$OPENAI_KEY
$([ -n "$PERPLEXITY_KEY" ] && echo "PERPLEXITY_API_KEY=$PERPLEXITY_KEY")
$([ -n "$GOOGLE_KEY" ] && echo "GOOGLE_API_KEY=$GOOGLE_KEY")

PRIMARY_LLM=claude-sonnet-4-6
MEMO_LLM=claude-opus-4-6

MIN_MARKET_CAP=250000000
MAX_MARKET_CAP=5000000000

SEC_EDGAR_USER_AGENT=PhoenicianCapital admin@phoenician.capital
SEC_RATE_LIMIT_RPS=10
ENVEOF

echo "✅ .env file created"
echo ""
echo "🔄 Restarting backend service..."
docker compose -f docker-compose.prod.yml restart mcp-server

echo ""
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:8000/api/v1/screening/status > /dev/null 2>&1; then
    echo "✅ Backend is ready!"
    break
  fi
  echo "  Attempt \$i/30..."
  sleep 1
done

echo ""
echo "📊 Current status:"
docker compose -f docker-compose.prod.yml ps
SETUP_EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. SSH into EC2: ssh -i $KEY_PATH ubuntu@$INSTANCE_IP"
echo "  2. Run a screening: curl -X POST http://13.49.7.145:8000/api/v1/screening/run -H 'Content-Type: application/json' -d '{\"max_companies\": 10}'"
echo "  3. Check logs: docker compose -f docker-compose.prod.yml logs mcp-server -f"
echo "  4. Verify companies saved: docker compose -f docker-compose.prod.yml exec db psql -U phoenician -d phoenician -c 'SELECT COUNT(*) FROM companies;'"
echo ""
