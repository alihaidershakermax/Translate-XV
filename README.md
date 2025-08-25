# 🤖 Advanced Translation Bot

> **Production-ready Telegram bot with AI-powered translation, advanced caching, monitoring, and security features**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deploy on Render](https://img.shields.io/badge/Deploy-Render-blueviolet)](https://render.com)

## ✨ Features

### 🚀 **Core Translation Features**
- **Multi-API Support**: Groq (Primary), Gemini, OpenAI (Fallbacks), Azure (Optional)
- **Document Processing**: PDF, DOCX, PPTX, Images (OCR)
- **Smart Text Detection**: Automatic text type detection (technical, academic, general)
- **Context-Aware Translation**: Maintains context across document sections
- **Format Preservation**: Original document formatting maintained

### ⚡ **Performance & Scalability**
- **Async Processing**: Non-blocking operations with connection pooling
- **Advanced Caching**: Redis + in-memory with intelligent fallback
- **Queue System**: Smart request prioritization and load balancing
- **Connection Pooling**: Optimized database and HTTP connections
- **Horizontal Scaling**: Ready for multi-instance deployment

### 🛡️ **Security & Reliability**
- **Rate Limiting**: Per-user and IP-based with burst allowance
- **Input Validation**: Malware scanning and content filtering
- **User Authentication**: Secure access control and admin features
- **Abuse Prevention**: Automatic blocking and security monitoring
- **Error Recovery**: Graceful error handling and retry mechanisms

### 📊 **Monitoring & Analytics**
- **Health Checks**: Kubernetes-style readiness and liveness probes
- **Prometheus Metrics**: Comprehensive performance monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Real-time Alerts**: Security events and performance thresholds
- **Usage Analytics**: User behavior and system performance insights

### 🗄️ **Data Management**
- **PostgreSQL Integration**: User profiles, translation history, analytics
- **Redis Caching**: Fast translation results and session management
- **Automatic Cleanup**: Configurable data retention policies
- **Backup Ready**: Database-agnostic design for easy backups

## 🏗️ **Architecture Overview**

```mermaid
graph TB
    A[Telegram API] <--> B[Translation Bot]
    B <--> C[AI Translation APIs]
    B --> D[Health/Metrics Server]
    B --> E[Security Manager]
    B --> F[Cache System]
    B --> G[Database]
    B --> H[Monitoring System]
    
    C --> C1[Groq - Primary]
    C --> C2[Gemini - Fallback]
    C --> C3[OpenAI - Fallback] 
    C --> C4[Azure - Fallback]
    
    F --> F1[Redis]
    F --> F2[Memory Cache]
    
    G --> G1[PostgreSQL]
    
    D --> D1[/health]
    D --> D2[/metrics]
    D --> D3[/status]
```

## 🚀 **Quick Start**

### Prerequisites
- Python 3.11+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- **Groq API key** (Primary AI service) from [Groq Console](https://console.groq.com/)
- Optional: Additional AI API keys for fallback (Gemini, OpenAI)
- Optional: Azure Translator (see [requirements-azure.txt](./requirements-azure.txt))
- PostgreSQL database (optional, uses in-memory if not available)
- Redis server (optional, uses memory cache if not available)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd translation-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   # or with uv (recommended)
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

4. **Run the bot**
   ```bash
   python start_bot.py
   ```

### Production Deployment (Render.com)

1. **Deploy with one click**
   - Fork this repository
   - Connect to Render.com
   - Configure environment variables
   - Deploy using the included `render.yaml`

2. **Detailed deployment guide**: See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

## 📋 **Configuration**

### Environment Variables

#### Required
```bash
BOT_TOKEN=your_telegram_bot_token
GROQ_KEYS=key1,key2,key3  # Primary AI service
```

#### Optional (with defaults)
```bash
# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false

# Performance
MAX_WORKERS=4
MAX_CONCURRENT_TRANSLATIONS=10
MAX_FILE_SIZE_MB=20

# User Limits
DAILY_LIMIT_PER_USER=50
CONCURRENT_LIMIT_PER_USER=3

# Caching
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=1000

# Database & Cache
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=8090
HEALTH_CHECK_INTERVAL=30

# Webhook (for production)
WEBHOOK_URL=https://yourapp.onrender.com/webhook
WEBHOOK_SECRET=your_secret_token
```

## 📖 **Usage Guide**

### Basic Commands
- `/start` - Welcome message and bot introduction
- `/help` - Complete usage guide
- `/status` - User statistics and queue position
- `/stats` - Personal usage statistics

### File Translation
1. **Send any supported file** (PDF, DOCX, PPTX, Image)
2. **Choose target language** (if prompted)
3. **Wait for processing** - you'll receive updates
4. **Download translated file** - maintains original formatting

### Text Translation
- **Send text message** - automatically detected and translated
- **Smart detection** - technical, academic, or general content
- **Context preservation** - maintains meaning and style

## 🛠️ **API Endpoints**

### Health Checks
- `GET /health` - Overall system health
- `GET /health/ready` - Readiness probe (Kubernetes)
- `GET /health/live` - Liveness probe (Kubernetes)
- `GET /health/database` - Database connectivity
- `GET /health/cache` - Cache system status

### Monitoring
- `GET /metrics` - Prometheus metrics
- `GET /status` - Comprehensive system status
- `GET /stats` - Detailed performance statistics
- `GET /logs` - Recent application logs

### Information
- `GET /info` - System information
- `GET /` - Basic service info

### Webhook
- `POST /webhook` - Telegram webhook endpoint

## 📊 **Monitoring**

### Health Check Example
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "uptime": 3600,
  "components": {
    "database": {"status": "healthy", "response_time": 0.05},
    "cache": {"status": "healthy", "redis_available": true},
    "bot": {"status": "healthy", "request_count": 1500},
    "system": {"status": "healthy", "memory_percent": 45.2}
  }
}
```

### Metrics Available
- Request rates and response times
- Error rates by type and user
- Cache hit/miss ratios
- Database connection pool usage
- System resource utilization
- User activity patterns
- API usage by service

## 🔒 **Security Features**

### Rate Limiting
- **User Requests**: 50/day with 5 burst allowance
- **File Uploads**: 20/day with 2 burst allowance  
- **IP-based**: 100/hour with 10 burst allowance
- **Global API**: 1000/hour with 50 burst allowance

### Input Validation
- File type and size validation
- Malware pattern detection
- Content sanitization
- XSS and injection prevention

### Access Control
- User authentication and authorization
- Admin user privileges
- Automatic blocking for abuse
- Security event logging

## 🧪 **Testing**

### Health Check Test
```bash
curl https://your-app.onrender.com/health
```

### Webhook Test
```bash
curl -X POST https://your-app.onrender.com/webhook \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: your_secret" \
  -d '{"update_id": 1, "message": {"text": "/start"}}'
```

### Load Testing
```bash
# Example with Apache Bench
ab -n 100 -c 10 https://your-app.onrender.com/health
```

## 📈 **Performance Benchmarks**

### Response Times
- **Health Check**: < 50ms
- **Simple Translation**: < 2s
- **PDF Processing**: < 30s (depends on size)
- **Cache Hit**: < 100ms

### Throughput
- **Concurrent Users**: 100+ (with proper scaling)
- **Requests/Second**: 50+ (with caching)
- **File Processing**: 10+ parallel

### Resource Usage
- **Memory**: ~200MB base + ~50MB per concurrent translation
- **CPU**: Low usage with efficient async processing
- **Database**: Minimal queries with smart caching

## 🔧 **Development**

### Project Structure
```
translation-bot/
├── start_bot.py           # Production startup script
├── main_optimized.py      # Optimized bot core
├── config.py              # Configuration management
├── cache_system.py        # Advanced caching
├── database.py           # Database integration
├── security.py           # Security & rate limiting
├── monitoring.py         # Logging & monitoring
├── health_server.py      # Health check endpoints
├── translator.py         # AI translation engine
├── queue_system.py       # Request queue management
├── user_manager.py       # User management
├── notification_system.py # User notifications
├── pdf_builder.py        # PDF generation
├── api_manager.py        # API key management
├── render.yaml           # Render.com configuration
├── Dockerfile           # Container configuration
└── pyproject.toml       # Python dependencies
```

### Adding New Features
1. **Create feature module** in appropriate location
2. **Add configuration** to `config.py` if needed
3. **Integrate with monitoring** for observability
4. **Add health checks** if external dependencies
5. **Update documentation** and deployment guide

### Code Quality
- **Type hints** throughout codebase
- **Async/await** for I/O operations
- **Error handling** with proper logging
- **Security validation** for all inputs
- **Performance monitoring** for all operations

## 🚨 **Troubleshooting**

### Common Issues

#### Bot Not Responding
1. Check `/health` endpoint
2. Verify webhook configuration
3. Check application logs
4. Validate BOT_TOKEN

#### Performance Issues
1. Monitor `/metrics` endpoint
2. Check cache hit rates
3. Review database performance
4. Analyze queue sizes

#### Security Alerts
1. Check security event logs
2. Review rate limit violations
3. Validate user access patterns
4. Monitor failed attempts

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG=true
python start_bot.py
```

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## 📞 **Support**

- **Documentation**: See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- **Issues**: Use GitHub Issues for bug reports
- **Health Checks**: Monitor via `/health` endpoints
- **Logs**: Access via `/logs` endpoint or Render dashboard

## 🎯 **Roadmap**

### Upcoming Features
- [ ] **Multi-language UI** - Support for more interface languages
- [ ] **Voice Translation** - Audio file processing
- [ ] **Batch Processing** - Multiple file upload support
- [ ] **Custom Models** - Fine-tuned translation models
- [ ] **Analytics Dashboard** - Web-based monitoring interface
- [ ] **API Gateway** - RESTful API for external integrations

### Performance Improvements
- [ ] **CDN Integration** - Faster file delivery
- [ ] **Edge Computing** - Regional deployment optimization
- [ ] **ML Optimization** - Smarter caching and prediction
- [ ] **Database Sharding** - Horizontal database scaling

---

**🎉 Ready to deploy your advanced translation bot? Follow the [deployment guide](./DEPLOYMENT_GUIDE.md) to get started!**