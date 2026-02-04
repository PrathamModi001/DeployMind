# LLM API Alternatives for DeployMind

This guide covers **100% FREE** LLM options for DeployMind, replacing the original Claude API requirement.

## Why the Change?

Claude Code subscription does **NOT** include Claude API access. Claude API requires separate billing (~$15 for this project). We've switched to **Groq's free tier** which provides 1,000 requests/day at zero cost.

---

## 🏆 RECOMMENDED: Groq (Current Implementation)

### Overview
- **Cost**: $0 (FREE forever)
- **Limits**: 1,000 requests/day, 6,000 tokens/minute
- **Speed**: Fastest LLM inference in the industry (LPU-based)
- **Setup Time**: 2 minutes

### Best Models for DeployMind

| Model | Use Case | Speed | Quality |
|-------|----------|-------|---------|
| `llama-3.1-70b-versatile` | Security analysis, deployment decisions | Fast | Excellent |
| `llama-3.1-8b-instant` | Log parsing, health checks | Ultra-fast | Good |
| `mixtral-8x7b-32768` | Long context tasks | Fast | Excellent |
| `gemma2-9b-it` | General tasks | Fast | Good |

### Setup Instructions

1. **Get free API key** (no credit card needed):
   ```
   https://console.groq.com/keys
   ```

2. **Add to `.env` file**:
   ```bash
   GROQ_API_KEY=gsk_your_key_here
   DEFAULT_LLM=llama-3.1-70b-versatile
   COST_SAVING_LLM=llama-3.1-8b-instant
   ```

3. **Install SDK**:
   ```bash
   pip install groq>=0.4.0
   ```

4. **CrewAI Integration** (automatic):
   CrewAI automatically detects Groq via the `GROQ_API_KEY` environment variable.

### Why Groq?
✅ Completely free (1000 req/day for MVP)
✅ Fastest inference speed (10x faster than OpenAI)
✅ No credit card required
✅ Full CrewAI support
✅ Production-ready quality

---

## Alternative 1: Ollama (Local, 100% Free)

### Overview
- **Cost**: $0 (runs on your machine)
- **Limits**: None (hardware-dependent)
- **Speed**: Depends on your GPU/CPU
- **Privacy**: All data stays local

### Best Models

| Model | Size | RAM Needed | Use Case |
|-------|------|------------|----------|
| `llama3.1:8b` | 4.7GB | 8GB | General tasks |
| `llama3.1:70b` | 40GB | 64GB | Complex reasoning (if you have powerful hardware) |
| `qwen2.5-coder:7b` | 4.4GB | 8GB | Code generation |
| `mistral:7b` | 4.1GB | 8GB | Fast general tasks |

### Setup Instructions

1. **Install Ollama**:
   ```bash
   # Windows/Mac/Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   # OR download from: https://ollama.ai
   ```

2. **Download a model**:
   ```bash
   ollama pull llama3.1:8b
   ```

3. **Update DeployMind config**:
   ```bash
   # In .env file, leave GROQ_API_KEY empty
   GROQ_API_KEY=

   # Use Ollama model names
   DEFAULT_LLM=llama3.1:8b
   COST_SAVING_LLM=llama3.1:8b
   ```

4. **CrewAI will auto-detect Ollama** running on `http://localhost:11434`

### Pros & Cons
✅ 100% free, no API costs
✅ Complete privacy (data never leaves your machine)
✅ No rate limits
✅ Works offline
❌ Requires 8GB+ RAM
❌ Slower than cloud APIs (unless you have a good GPU)

---

## Alternative 2: OpenRouter

### Overview
- **Cost**: $0 for free tier
- **Limits**: 200 requests/day, 20/minute
- **Models**: Access to multiple LLMs (Llama, Mixtral, etc.)

### Setup Instructions

1. **Get free API key**:
   ```
   https://openrouter.ai/keys
   ```

2. **Update `.env`**:
   ```bash
   OPENROUTER_API_KEY=sk-or-your-key-here
   DEFAULT_LLM=meta-llama/llama-3.1-70b-instruct
   ```

3. **Install SDK**:
   ```bash
   pip install openai>=1.0.0  # OpenRouter uses OpenAI SDK
   ```

### Pros & Cons
✅ Free tier available
✅ Multiple model choices
✅ OpenAI-compatible API
❌ Lower rate limits (200/day vs Groq's 1000/day)
❌ Slower than Groq

---

## Alternative 3: Cloudflare Workers AI

### Overview
- **Cost**: $0 for free tier
- **Limits**: 10,000 requests/day
- **Models**: Llama 3, Gemma 2

### Setup Instructions

1. **Get Cloudflare API token**:
   ```
   https://dash.cloudflare.com/
   ```

2. **Update config** (requires custom CrewAI integration):
   ```python
   # Custom LLM provider setup needed
   from crewai import LLM

   llm = LLM(
       model="cloudflare/@cf/meta/llama-3-8b-instruct",
       api_key="your-cf-token"
   )
   ```

### Pros & Cons
✅ Very high rate limits (10k/day)
✅ Free tier
❌ Requires custom integration
❌ Limited model selection

---

## Alternative 4: Hugging Face Inference API

### Overview
- **Cost**: $0 for free tier
- **Limits**: Varies by model
- **Models**: Thousands of open-source models

### Setup Instructions

1. **Get free API key**:
   ```
   https://huggingface.co/settings/tokens
   ```

2. **Install SDK**:
   ```bash
   pip install huggingface-hub>=0.20.0
   ```

3. **Update config**:
   ```bash
   HUGGINGFACE_API_KEY=hf_your_key_here
   DEFAULT_LLM=meta-llama/Meta-Llama-3.1-70B-Instruct
   ```

### Pros & Cons
✅ Free tier
✅ Access to thousands of models
✅ Good for experimentation
❌ Slower inference
❌ Rate limits vary by model
❌ Requires custom CrewAI integration

---

## Alternative 5: GitHub Models (New!)

### Overview
- **Cost**: $0 (free with GitHub account)
- **Limits**: Tied to Copilot subscription (generous for free accounts)
- **Models**: GPT-4o, Claude, Llama, Mistral

### Setup Instructions

1. **Access GitHub Models**:
   ```
   https://github.com/marketplace/models
   ```

2. **Get API token**:
   ```bash
   # Use GitHub personal access token
   # Settings → Developer settings → Personal access tokens
   ```

3. **Update config** (OpenAI-compatible):
   ```bash
   GITHUB_TOKEN=ghp_your_token_here
   DEFAULT_LLM=gpt-4o  # or Meta-Llama-3.1-70B-Instruct
   ```

### Pros & Cons
✅ Free with GitHub account
✅ Multiple model options (GPT, Claude, Llama)
✅ Integrated with developer workflow
❌ New service, limits may change
❌ Requires GitHub account

---

## Cost Comparison for DeployMind MVP (2 weeks)

| Provider | Cost | Requests/Day | Est. Total Requests | Notes |
|----------|------|--------------|---------------------|-------|
| **Groq** | **$0** | **1,000** | **14,000** | **RECOMMENDED** |
| Ollama | $0 | Unlimited | Unlimited | Local only |
| OpenRouter | $0 | 200 | 2,800 | May be tight for MVP |
| Cloudflare | $0 | 10,000 | 140,000 | Requires custom code |
| Claude API | ~$15 | ~500 | ~7,000 | NOT included with Claude Code |

**Verdict**: Groq offers the best balance of cost ($0), limits (1000/day), and ease of setup for DeployMind.

---

## Model Performance Comparison

### For Security Analysis (Detecting CVEs, analyzing Dockerfiles)
1. **Best**: `llama-3.1-70b-versatile` (Groq) - Excellent reasoning
2. **Good**: `mixtral-8x7b-32768` (Groq) - Good for long context
3. **Fast**: `llama3.1:8b` (Ollama) - If running locally

### For Deployment Decisions (Rolling deploy, rollback logic)
1. **Best**: `llama-3.1-70b-versatile` (Groq) - Complex decision-making
2. **Good**: `gpt-4o` (GitHub Models) - If you have access
3. **Fast**: `llama-3.1-8b-instant` (Groq) - Simple decisions

### For Simple Tasks (Log parsing, health check validation)
1. **Best**: `llama-3.1-8b-instant` (Groq) - Ultra-fast
2. **Good**: `gemma2-9b-it` (Groq) - Also very fast
3. **Local**: `mistral:7b` (Ollama) - If running locally

---

## How to Switch Providers

### From Groq to Ollama (Local)

1. **Install Ollama**:
   ```bash
   ollama pull llama3.1:8b
   ```

2. **Update `.env`**:
   ```bash
   GROQ_API_KEY=  # Leave empty
   DEFAULT_LLM=llama3.1:8b
   COST_SAVING_LLM=llama3.1:8b
   ```

3. **CrewAI will auto-detect** Ollama on localhost:11434

### From Groq to OpenRouter

1. **Get OpenRouter key**: https://openrouter.ai/keys

2. **Update `.env`**:
   ```bash
   OPENROUTER_API_KEY=sk-or-your-key
   DEFAULT_LLM=meta-llama/llama-3.1-70b-instruct
   ```

3. **Update `requirements.txt`**:
   ```python
   openai>=1.0.0  # OpenRouter uses OpenAI SDK
   ```

### From Groq back to Claude (if you get API access)

1. **Get Claude API key**: https://console.anthropic.com

2. **Update `.env`**:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key
   DEFAULT_LLM=claude-3-5-sonnet-20241022
   ```

3. **Update `requirements.txt`**:
   ```python
   anthropic>=0.18.0
   ```

---

## Recommended Setup for Different Use Cases

### 1. **MVP Development** (What we're doing)
- **Provider**: Groq
- **Model**: `llama-3.1-70b-versatile`
- **Cost**: $0
- **Why**: Free, fast, plenty of requests for 2-week MVP

### 2. **Production Deployment** (Post-MVP)
- **Provider**: Groq + Paid tier OR self-hosted Ollama
- **Model**: `llama-3.1-70b-versatile` or local `llama3.1:70b`
- **Cost**: $0.27/million tokens (Groq paid) or hardware cost (Ollama)
- **Why**: Scalable, cost-effective

### 3. **Experimentation/Learning**
- **Provider**: Ollama (local)
- **Model**: `llama3.1:8b`, `qwen2.5-coder:7b`
- **Cost**: $0
- **Why**: No rate limits, complete privacy

### 4. **If You Already Have Claude/GPT Access**
- **Provider**: Anthropic or OpenAI
- **Model**: `claude-3-5-sonnet-20241022` or `gpt-4o`
- **Cost**: ~$3-15 per million tokens
- **Why**: Highest quality, but not necessary for DeployMind

---

## FAQ

### Q: Why not use OpenAI's free tier?
**A**: OpenAI requires credit card for API access. Groq does not.

### Q: Is Groq really free forever?
**A**: Yes, the free tier is permanent. Paid tiers exist for higher usage.

### Q: Can I mix providers (e.g., Groq for complex tasks, Ollama for simple ones)?
**A**: Yes! DeployMind supports this via `DEFAULT_LLM` and `COST_SAVING_LLM` environment variables.

### Q: Which is faster: Groq or Ollama?
**A**: Groq is faster unless you have a high-end GPU (RTX 4090, A100, etc.).

### Q: Will the free tier be enough for the 2-week MVP?
**A**: Yes. Groq's 1,000 requests/day = 14,000 total. MVP needs ~500-1000 requests.

### Q: What if I hit rate limits during development?
**A**: Switch to Ollama temporarily (unlimited local requests) or use a second Groq account.

---

## Support

- **Groq Docs**: https://console.groq.com/docs
- **Ollama Docs**: https://github.com/ollama/ollama
- **CrewAI LLM Integration**: https://docs.crewai.com/core-concepts/llms/

---

## Summary

**For DeployMind MVP, we recommend:**

1. **Primary**: Groq (`llama-3.1-70b-versatile`) - FREE, fast, 1000 req/day
2. **Backup**: Ollama (local) - FREE, unlimited, requires 8GB+ RAM
3. **Future**: Self-hosted Ollama for production or Groq paid tier

**Total cost: $0** (vs original $15 for Claude API)
