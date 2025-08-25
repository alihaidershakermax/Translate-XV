# 🔧 Deployment Troubleshooting Guide

## Common Deployment Issues and Solutions

### 🐳 Docker Build Issues

#### Issue: `uv.lock not found`
**Error**: `failed to compute cache key: "/uv.lock": not found`

**Solution**: ✅ **FIXED** - Updated Dockerfile to use `requirements.txt` instead of `uv.lock`

**What was done**:
- Modified [Dockerfile](./Dockerfile) to use standard pip installation
- Updated [render.yaml](./render.yaml) build command
- Added `uv.lock` to [.dockerignore](./.dockerignore)

#### Issue: `azure-cognitiveservices-language-translator` not found
**Error**: `ERROR: No matching distribution found for azure-cognitiveservices-language-translator>=3.0.0`

**Solution**: ✅ **FIXED** - Removed problematic Azure dependency since it's optional

**What was done**:
- Removed incorrect Azure package from [requirements.txt](./requirements.txt)
- Azure is now optional (use [requirements-azure.txt](./requirements-azure.txt) if needed)
- Groq is the primary service, Gemini and OpenAI are sufficient fallbacks

#### Issue: Missing dependencies
**Error**: `ModuleNotFoundError: No module named 'xxx'`

**Solution**:
1. Check that all dependencies are in [requirements.txt](./requirements.txt)
2. Verify the dependency versions are compatible
3. Rebuild the Docker image:
   ```bash
   docker build -t translation-bot .
   ```

#### Issue: Python version compatibility
**Error**: `This package requires Python >=3.11`

**Solution**: ✅ **Already configured** - Dockerfile uses Python 3.11

---

### 🌐 Render.com Deployment Issues

#### Issue: Build fails on Render
**Error**: Various build errors

**Solutions**:
1. **Check build logs** in Render dashboard
2. **Verify environment variables** are set correctly:
   ```
   BOT_TOKEN=your_bot_token
   GROQ_KEYS=your_groq_keys
   ENVIRONMENT=production
   ```
3. **Check resource limits** - upgrade plan if needed

#### Issue: Service health check fails
**Error**: Service marked as unhealthy

**Solutions**:
1. **Check health endpoint**: Visit `https://your-app.onrender.com/health`
2. **Verify port configuration**: Should be `8080` (automatic on Render)
3. **Check application logs** for startup errors

#### Issue: Webhook not working
**Error**: Bot doesn't respond to messages

**Solutions**:
1. **Set webhook URL** after deployment:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://your-app.onrender.com/webhook"
   ```
2. **Verify webhook secret** if configured
3. **Check webhook status**:
   ```bash
   curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
   ```

---

### ⚙️ Configuration Issues

#### Issue: Missing API keys
**Error**: `GROQ_KEYS is required as the primary AI translation service`

**Solution**:
1. Get Groq API keys from [Groq Console](https://console.groq.com/)
2. Add to environment variables:
   ```
   GROQ_KEYS=key1,key2,key3
   ```

#### Issue: Database connection fails
**Error**: Database health check fails

**Solutions**:
1. **Check DATABASE_URL** in environment variables
2. **Verify PostgreSQL service** is running (auto-created by render.yaml)
3. **Check database logs** in Render dashboard

#### Issue: Redis connection fails
**Error**: Cache health check fails

**Solutions**:
1. **Check REDIS_URL** in environment variables
2. **Verify Redis service** is running (auto-created by render.yaml)
3. **Bot will fallback** to memory cache automatically

---

### 🚨 Runtime Issues

#### Issue: High memory usage
**Error**: Service restarts due to memory limits

**Solutions**:
1. **Upgrade Render plan** to higher memory limit
2. **Monitor memory usage** via `/stats` endpoint
3. **Check for memory leaks** in logs

#### Issue: Rate limiting
**Error**: Too many requests errors

**Solutions**:
1. **Add more API keys** for higher limits
2. **Configure rate limiting** in security settings
3. **Monitor usage** via `/metrics` endpoint

#### Issue: Translation failures
**Error**: Translations return errors

**Solutions**:
1. **Check API key validity** and quotas
2. **Verify file formats** are supported
3. **Check file size limits** (max 20MB)
4. **Test with smaller files** first

---

### 🔍 Debugging Steps

#### 1. Check Health Endpoints
```bash
# Overall health
curl https://your-app.onrender.com/health

# Individual components
curl https://your-app.onrender.com/health/database
curl https://your-app.onrender.com/health/cache
curl https://your-app.onrender.com/health/bot
```

#### 2. Check System Status
```bash
# Detailed status
curl https://your-app.onrender.com/status

# System metrics
curl https://your-app.onrender.com/stats

# Recent logs
curl https://your-app.onrender.com/logs?limit=50
```

#### 3. Test Webhook
```bash
# Test webhook endpoint
curl -X POST https://your-app.onrender.com/webhook \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"text": "/start"}}'
```

#### 4. Local Testing
```bash
# Test locally before deployment
export BOT_TOKEN=your_token
export GROQ_KEYS=your_keys
python start_bot.py
```

---

### 📋 Pre-Deployment Checklist

Before deploying, ensure:

- [ ] **BOT_TOKEN** is set and valid
- [ ] **GROQ_KEYS** is set with working API keys
- [ ] **WEBHOOK_URL** points to your Render app
- [ ] All required files are in the repository:
  - [ ] `start_bot.py`
  - [ ] `requirements.txt`
  - [ ] `render.yaml`
  - [ ] `Dockerfile`
  - [ ] All Python modules (config.py, etc.)
- [ ] **Environment** is set to `production`
- [ ] **Database and Redis** services are enabled in render.yaml

---

### 🆘 Getting Help

#### Check Documentation
- [README.md](./README.md) - Complete project overview
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Step-by-step deployment

#### Monitor Your Deployment
- **Render Dashboard**: Monitor logs and metrics
- **Health Endpoints**: Regular health checks
- **Telegram Bot**: Test with simple commands

#### Common Success Indicators
- ✅ Health endpoint returns `"status": "healthy"`
- ✅ Webhook info shows correct URL
- ✅ Bot responds to `/start` command
- ✅ File translation works
- ✅ No error logs in Render dashboard

---

### 🎯 Quick Fix Summary

**Most Common Issue**: Missing or incorrect environment variables
**Quick Fix**: Double-check `BOT_TOKEN` and `GROQ_KEYS` in Render settings

**Second Most Common**: Webhook not set
**Quick Fix**: Set webhook URL after first successful deployment

**Third Most Common**: File size limits
**Quick Fix**: Test with smaller files first (< 1MB)

---

*This guide covers the most common deployment issues. If you encounter other problems, check the health endpoints and logs first.*