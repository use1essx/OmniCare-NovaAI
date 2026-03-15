# 🏥 OmniCare Healthcare AI Platform

> AI-powered healthcare platform for elderly care featuring Live2D avatars, multi-agent AI assistance, mental health support, and movement analysis

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![AWS](https://img.shields.io/badge/AWS-Bedrock%20Nova-orange.svg)](https://aws.amazon.com/bedrock/)

## 🌟 Overview

OmniCare is a comprehensive healthcare AI platform designed for elderly care providers in Hong Kong. It combines cutting-edge AI technology with an intuitive interface to deliver personalized healthcare support through interactive Live2D avatars.

### ✨ Key Features

- **🤖 Multi-Agent AI System** - Specialized agents for wellness coaching and mental health support
- **🎭 Interactive Live2D Avatars** - Engaging visual interface with emotional expressions
- **📹 Movement Analysis** - AI-powered video-based motor screening using AWS Nova Pro
- **🧠 Knowledge Base (RAG)** - Semantic search with AWS Titan Embeddings
- **🛡️ Safety Validation** - Crisis detection and intervention system
- **💰 Budget Protection** - Built-in cost tracking with $50 limit
- **🌍 Bilingual Support** - Cantonese (zh-HK) and English
- **🔒 Enterprise Security** - JWT authentication, RBAC, audit logging

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- AWS Account with Bedrock access (Nova Lite, Nova Pro, Titan Embeddings)
- Python 3.11+ (for local development)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/omnicare-healthcare-ai.git
cd omnicare-healthcare-ai
```

2. **Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and add your AWS credentials:

```bash
# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
USE_BEDROCK=true

# Database
DATABASE_PASSWORD=your_secure_password

# Security
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=production
```

3. **Start the application**

```bash
# Using the start script (recommended)
./start.sh

# Or using Docker Compose directly
docker-compose up -d
```

4. **Access the application**

- Main Application: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Admin Dashboard: http://localhost:8000/admin
- Database Admin (pgAdmin): http://localhost:5050

### First-Time Setup

Create a super admin user:

```bash
docker-compose exec healthcare_ai python scripts/create_super_admin.py
```

## 📁 Project Structure

```
omnicare-healthcare-ai/
├── src/                      # Source code
│   ├── agents/               # AI agents (wellness, mental health)
│   ├── ai/                   # Nova client, budget protection
│   ├── movement_analysis/    # Video analysis system
│   ├── knowledge_base/       # RAG system with embeddings
│   ├── safety_validation_layer/  # Crisis detection
│   ├── web/                  # FastAPI routes and frontend
│   ├── database/             # Models and repositories
│   ├── security/             # Authentication and authorization
│   └── services/             # Core services
├── tests/                    # Test suite
├── docs/                     # Documentation
├── docker/                   # Docker configurations
├── scripts/                  # Utility scripts
├── alembic/                  # Database migrations
├── docker-compose.yml        # Container orchestration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Admin Panel  │  │  Live2D UI   │  │  WebSocket   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Application                        │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│  │  REST  │  │   WS   │  │ Admin  │  │ Live2D │           │
│  │  API   │  │ Server │  │  API   │  │  API   │           │
│  └────────┘  └────────┘  └────────┘  └────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   AI Agent   │  │   Movement   │  │  Knowledge   │      │
│  │ Orchestrator │  │   Analysis   │  │     Base     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │   ChromaDB   │  │    Redis     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ AWS Bedrock  │  │    Whisper   │  │   Edge TTS   │      │
│  │    Nova      │  │     STT      │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## 🤖 AI Agents

### Wellness Coach (慧心助手)
- General health guidance and wellness support
- Physical health monitoring
- Preventive care recommendations
- Uses AWS Nova Lite for cost-effective responses

### Mental Health Support (小星星)
- Mental health counseling and support
- Crisis detection and intervention
- Emotional support and empathy
- Integrated with safety validation layer

### Safety Guardian
- Emergency response coordination
- Risk assessment and escalation
- 24/7 monitoring and alerts

## 🎯 Core Features

### Movement Analysis
- Upload exercise or movement videos
- AI-powered motor screening using AWS Nova Pro
- Age-appropriate assessment criteria
- Detailed health reports with recommendations

### Knowledge Base (RAG)
- Semantic search with AWS Titan Embeddings (1536-dimensional vectors)
- Hybrid retrieval combining vector search (ChromaDB) and BM25
- Context-aware responses
- Support for PDF, DOCX, TXT, MD documents

### Safety Validation
- Input validation for crisis signals
- Output humanization for empathetic responses
- Risk level assessment (low, medium, high, critical)
- Automatic escalation for high-risk situations

### Budget Protection
- Real-time cost tracking for all AI operations
- Configurable spending limits ($50 default)
- Pre-request budget validation
- Usage analytics and reporting
- Cost breakdown by model and operation

## 🔒 Security

- **Authentication**: JWT-based with access and refresh tokens
- **Authorization**: Role-based access control (admin, caregiver, patient)
- **Data Isolation**: Organization-level data separation
- **Input Validation**: Pydantic models for all API inputs
- **Audit Logging**: Comprehensive logging of sensitive operations
- **Privacy**: No PII/PHI in logs, GDPR-compliant data handling
- **Rate Limiting**: Protection against abuse

## 📊 API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

```
Authentication
POST   /api/v1/auth/login          # User authentication
POST   /api/v1/auth/refresh         # Refresh token
POST   /api/v1/auth/logout          # Logout

Chat
WS     /ws/chat                     # WebSocket chat
GET    /api/v1/conversations        # List conversations
POST   /api/v1/conversations/{id}/messages  # Send message

Knowledge Base
POST   /api/v1/knowledge/upload     # Upload document
GET    /api/v1/knowledge/search     # Semantic search
GET    /api/v1/knowledge/documents  # List documents

Movement Analysis
POST   /api/v1/assessments/upload   # Upload movement video
GET    /api/v1/assessments/{id}     # Get assessment results

Budget
GET    /api/v1/budget/status        # Check budget status
GET    /api/v1/budget/history       # Usage history
```

## 🛠️ Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test types
pytest -m smoke      # Smoke tests
pytest -m unit       # Unit tests
pytest -m integration # Integration tests
pytest -m security   # Security tests
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ --fix

# Type checking
pyright src/
```

## 🌐 Deployment

### Docker Deployment

```bash
# Production build
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Health Checks

```bash
# Check application health
curl http://localhost:8000/health

# Check database connectivity
curl http://localhost:8000/health/db

# Check budget status
curl http://localhost:8000/api/v1/budget/status
```

## 💻 Technology Stack

### Backend
- **Python 3.11+** - Primary language
- **FastAPI** - Modern web framework
- **SQLAlchemy 2.0** - ORM
- **PostgreSQL 15** - Main database
- **ChromaDB** - Vector database
- **Redis** - Caching and sessions
- **Alembic** - Database migrations

### AI & ML
- **AWS Bedrock Nova Lite** - Fast, cost-effective chat ($0.00006/1K input tokens)
- **AWS Bedrock Nova Pro** - Video analysis, complex tasks ($0.0008/1K input tokens)
- **AWS Titan Embeddings** - Semantic search vectors
- **Whisper** - Speech-to-text
- **Edge TTS** - Text-to-speech

### Frontend
- **Alpine.js** - Reactive UI framework
- **Tailwind CSS** - Utility-first CSS
- **Chart.js** - Data visualization
- **Live2D SDK** - Avatar animation

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy (production)
- **Uvicorn** - ASGI server

## 📈 Performance

- **Response Time**: < 2s for chat responses
- **Video Processing**: < 30s for 30-second videos
- **Concurrent Users**: Supports 100+ simultaneous connections
- **Database**: Optimized queries with proper indexing
- **Caching**: Redis for session and frequently accessed data

## 🧪 Testing Strategy

- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint and workflow testing
- **Security Tests**: Authentication, authorization, and injection prevention
- **Smoke Tests**: Quick validation of critical functionality

**Coverage Targets**:
- Overall: 80%
- New code: 90%
- Security-critical code: 100%

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- AWS Bedrock Nova for AI capabilities
- Live2D for avatar technology
- FastAPI for the excellent web framework
- The open-source community

## 📧 Support

For questions or support:
- Open an issue on GitHub
- Check the [documentation](docs/)
- Review the [API documentation](http://localhost:8000/docs)

## 🗺️ Roadmap

- [ ] Multi-language support (Cantonese, Mandarin, English)
- [ ] Advanced RAG with re-ranking
- [ ] Voice interface integration
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Custom ML models for health prediction
- [ ] Third-party EHR integrations
- [ ] Telemedicine integration

---

**Built with ❤️ for healthcare providers in Hong Kong** 🇭🇰

**Version**: 2.0 | **Last Updated**: March 2026
