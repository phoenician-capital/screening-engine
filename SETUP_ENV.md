# Setting Up Environment Variables for Production

## Why Companies Aren't Being Discovered

The screening system needs **LLM API keys** to:
- Fetch and analyze company data from SEC EDGAR
- Use Claude/OpenAI to pre-screen candidates
- Score companies with the multi-agent system

Without these keys, the discovery phase can't run, so no companies get saved to the database.

## Required API Keys

Get these from their respective services:

1. **Anthropic (Claude)**
   - Get from: https://console.anthropic.com/
   - Key starts with: `sk-ant-...`
   - Used for: Main LLM reasoning

2. **OpenAI (GPT-4)**
   - Get from: https://platform.openai.com/api-keys
   - Key starts with: `sk-...`
   - Used for: Extraction and specialized tasks

3. **Perplexity (Optional)**
   - Get from: https://www.perplexity.ai/settings/api
   - Used for: Deep research searches

4. **Google (Optional)**
   - Get from: https://console.cloud.google.com/
   - Used for: Gemini models

## Setting Up on EC2

### Option 1: Create `.env` file (Recommended)

```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145
cd /home/ubuntu/screening-engine

# Create .env with your API keys
cat > .env << 'EOF'
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

# LLM API Keys — ADD YOUR KEYS HERE
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
PERPLEXITY_API_KEY=pplx-your-key-here
GOOGLE_API_KEY=AIza-your-key-here

PRIMARY_LLM=claude-sonnet-4-6
MEMO_LLM=claude-opus-4-6

MIN_MARKET_CAP=250000000
MAX_MARKET_CAP=5000000000
EOF

# Restart services to load new env
docker compose -f docker-compose.prod.yml restart mcp-server
```

### Option 2: Update docker-compose.prod.yml

Add environment variables directly to the `mcp-server` section:

```yaml
mcp-server:
  environment:
    ANTHROPIC_API_KEY: sk-ant-your-key
    OPENAI_API_KEY: sk-your-key
    PERPLEXITY_API_KEY: pplx-your-key
    # ... other vars
```

Then restart:
```bash
docker compose -f docker-compose.prod.yml restart mcp-server
```

## Testing the Setup

Once API keys are configured:

```bash
# Run a screening to discover companies
curl -X POST http://13.49.7.145:8000/api/v1/screening/run \
  -H "Content-Type: application/json" \
  -d '{"max_companies": 10}'

# Check logs for discovery progress
docker compose -f docker-compose.prod.yml logs mcp-server -f

# Verify companies were saved
docker compose -f docker-compose.prod.yml exec db psql -U phoenician -d phoenician \
  -c "SELECT COUNT(*) FROM companies;"
```

## What Happens After API Keys Are Set

1. **Discovery Phase**: Fetches companies from SEC EDGAR, filters by market cap
2. **Claude Pre-screen**: Claude narrows 1000+ candidates down to top 100
3. **Selection Team**: 5 agents analyze and pre-filter to top 50
4. **Scoring Team**: 3 agents deep-score the top 50
5. **Results**: Top recommendations saved to database + portfolio holdings

This is a resource-intensive process (calls multiple APIs), so it may take 5-10 minutes for initial run.

## Cost Estimates

Rough API costs per screening run:
- **Anthropic (Claude)**: $0.50-2.00
- **OpenAI (GPT-4)**: $1.00-3.00
- **Perplexity**: $0.10-0.50
- **Total per run**: ~$2-5

Budget accordingly based on how frequently you run screenings.
