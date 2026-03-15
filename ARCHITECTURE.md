# System Architecture

> Comprehensive technical architecture for OmniCare Healthcare AI Platform

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [Security](#security)
- [Deployment](#deployment)

## Overview

OmniCare is a production-ready healthcare AI platform built with a microservices-inspired architecture, combining FastAPI backend, Live2D frontend, and AWS Bedrock Nova for AI capabilities.

### Key Capabilities

- Multi-agent AI system with specialized healthcare agents
- Real-time chat with Live2D avatar integration
- Video-based movement analysis using computer vision
- Knowledge base with RAG (Retrieval-Augmented Generation)
- Multi-stage health assessments
- Role-based access control (RBAC)
- Budget-protected AI usage ($50 limit)

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Admin Panel  │  │  Live2D UI   │  │  WebSocket   │      │
│  │  (Alpine.js) │  │   (WebGL)    │  │   Client     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI Application                      │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │   │
│  │  │  REST  │  │   WS   │  │ Admin  │  │ Live2D │    │   │
│  │  │  API   │  │ Server │  │  API   │  │  API   │    │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   AI Agent   │  │   Movement   │  │  Knowledge   │      │
│  │ Orchestrator │  │   Analysis   │  │     Base     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Assessment  │  │    Safety    │  │    Budget    │      │
│  │   Pipeline   │  │  Validation  │  │  Protection  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │   ChromaDB   │  │    Redis     │      │
│  │  (Main DB)   │  │  (Vectors)   │  │   (Cache)    │      │
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

### Component Interaction

```mermaid
graph LR
    A[User] --> B[FastAPI]
    B --> C[Agent Orchestrator]
    C --> D[AI Service]
    D --> E[AWS Nova]
    C --> F[Knowledge Base]
    F --> G[ChromaDB]
    B --> H[PostgreSQL]
    B --> I[Redis]
```

## Core Components

### 1. AI Agent System

**Location**: `src/agents/`

The multi-agent system provides specialized healthcare assistance:

- **Wellness Coach** - Physical health guidance and monitoring
- **Mental Health Agent (小星星)** - Mental health support with crisis detection
- **Safety Guardian** - Emergency response and escalation
- **Movement Screener** - Motor skill assessment

**Key Features**:
- Dynamic skill activation based on conversation context
- Intelligent intent routing
- Emotion mapping to Live2D expressions
- Crisis detection with automatic escalation

**Architecture**:
```
agents/
├── base_agent.py              # Base agent interface
├── orchestrator.py            # Agent routing and coordination
├── unified_agent.py           # Main conversational agent
├── specialized/               # Domain-specific agents
│   ├── wellness_coach.py
│   ├── mental_health.py
│   └── safety_guardian.py
└── skills/                    # Dynamic skill system
    ├── skill_activator.py
    └── intelligent_router.py
```

### 2. AI Service Layer

**Location**: `src/ai/`

Manages all AI model interactions with budget protection:

- **Nova Bedrock Client** - AWS Bedrock integration
- **Unified AI Client** - Standardized interface for all AI calls
- **Budget Middleware** - Enforces $50 spending limit
- **Cost Tracker** - Real-time cost monitoring

**Model Selection**:
- **Nova Lite** ($0.00006/1K input tokens) - Chat, questionnaires
- **Nova Pro** ($0.0008/1K input tokens) - Video analysis, complex tasks
- **Titan Embeddings** - Semantic search and RAG

### 3. Knowledge Base (RAG)

**Location**: `src/knowledge_base/`, `src/services/`

Semantic search system for healthcare documents:

- **Document Processor** - Extracts and chunks documents
- **Embedding Service** - Generates vectors using Titan Embeddings
- **Hybrid Retriever** - Combines vector search (ChromaDB) with BM25
- **Context Injection** - Augments agent responses with relevant docs

**Supported Formats**: PDF, DOCX, TXT, MD

### 4. Movement Analysis

**Location**: `src/movement_analysis/`

AI-powered video analysis for motor screening:

- **Video Processor** - Extracts frames from uploaded videos
- **Analysis Service** - Uses Nova Pro for movement pattern recognition
- **Rules Engine** - Age-appropriate assessment criteria
- **Report Generator** - Detailed health assessment reports

### 5. Assessment Pipeline

**Location**: `src/questionnaire/`

Multi-stage health assessment system:

- **Questionnaire Generator** - AI-powered question generation
- **Response Collector** - Stores and analyzes user responses
- **Profile Builder** - Builds comprehensive health profiles
- **Adaptive Questioning** - Adjusts questions based on responses

### 6. Web Layer

**Location**: `src/web/`

#### REST API (`src/web/api/v1/`)
- Authentication and authorization
- User and organization management
- Conversation and message handling
- Knowledge base operations
- Budget monitoring

#### WebSocket Server (`src/web/websockets/`)
- Real-time chat communication
- Connection management
- Event broadcasting

#### Admin Dashboard (`src/web/admin/`)
- User management interface
- Data management tools
- System monitoring
- AI questionnaire generator

#### Live2D Integration (`src/web/live2d/`)
- Avatar rendering and animation
- Emotion expression mapping
- Background management

### 7. Security Layer

**Location**: `src/security/`

Comprehensive security implementation:

- **Authentication** - JWT-based with refresh tokens
- **Authorization** - Role-based access control (RBAC)
- **Audit Logging** - All sensitive operations logged
- **Input Validation** - Pydantic models for all inputs
- **Rate Limiting** - Protection against abuse

**Roles**:
- `super_admin` - Full system access
- `admin` - Organization administration
- `caregiver` - Patient management
- `patient` - Standard user access

### 8. Database Layer

**Location**: `src/database/`

Repository pattern with SQLAlchemy ORM:

- **Models** - Comprehensive data models
- **Repositories** - Data access layer
- **Migrations** - Alembic for schema evolution
- **Vector Store** - ChromaDB integration

## Data Flow

### Chat Conversation Flow

```mermaid
sequenceDiagram
    participant User
    participant WS as WebSocket
    participant Orch as Orchestrator
    participant Agent
    participant AI as Nova
    participant KB as Knowledge Base
    
    User->>WS: Send message
    WS->>Orch: Route message
    Orch->>Orch: Classify intent
    Orch->>Agent: Delegate to agent
    Agent->>KB: Retrieve context
    KB-->>Agent: Relevant docs
    Agent->>AI: Generate response
    AI-->>Agent: AI response
    Agent->>Orch: Response + emotion
    Orch->>WS: Send response
    WS->>User: Display message
```

### Document Processing Flow

```mermaid
sequenceDiagram
    participant Admin
    participant API
    participant Processor
    participant Embedding
    participant ChromaDB
    participant PostgreSQL
    
    Admin->>API: Upload document
    API->>Processor: Process file
    Processor->>Processor: Extract & chunk text
    Processor->>Embedding: Generate embeddings
    Embedding-->>Processor: Vectors
    Processor->>ChromaDB: Store vectors
    Processor->>PostgreSQL: Store metadata
    Processor-->>API: Success
    API-->>Admin: Document processed
```

### Movement Analysis Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant VideoProc as Video Processor
    participant Nova
    participant DB
    
    User->>API: Upload video
    API->>VideoProc: Process video
    VideoProc->>VideoProc: Extract 5 frames
    VideoProc->>Nova: Analyze frames
    Nova-->>VideoProc: Analysis results
    VideoProc->>DB: Store results
    VideoProc-->>API: Report
    API-->>User: Assessment report
```

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Primary language |
| FastAPI | 0.104+ | Web framework |
| SQLAlchemy | 2.0+ | ORM |
| PostgreSQL | 15+ | Main database |
| ChromaDB | 0.4+ | Vector database |
| Redis | 7+ | Caching & sessions |
| Alembic | 1.13+ | Database migrations |
| Pydantic | 2.5+ | Data validation |

### AI & ML

| Technology | Purpose |
|------------|---------|
| AWS Bedrock Nova Lite | Fast, cost-effective chat |
| AWS Bedrock Nova Pro | Video analysis, complex tasks |
| AWS Titan Embeddings | Semantic search vectors |
| Whisper | Speech-to-text |
| Edge TTS | Text-to-speech |

### Frontend

| Technology | Purpose |
|------------|---------|
| Alpine.js | Reactive UI |
| Tailwind CSS | Styling |
| Chart.js | Data visualization |
| Live2D SDK | Avatar animation |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Multi-container orchestration |
| Nginx | Reverse proxy (production) |
| Uvicorn | ASGI server |

## Database Schema

### Core Tables

**users**
- User accounts with role-based permissions
- Organization membership
- Authentication credentials (hashed)

**organizations**
- Multi-tenant organization management
- Facility information
- User limits and settings

**conversations**
- Chat conversation history
- Context and metadata
- User associations

**messages**
- Individual chat messages
- Role (user/assistant/system)
- Timestamps and metadata

### Knowledge Base Tables

**knowledge_documents**
- Uploaded document metadata
- Processing status
- Category and tags

**knowledge_chunks**
- Text chunks from documents
- Vector IDs for ChromaDB
- Chunk metadata

### Assessment Tables

**questionnaires**
- Assessment questionnaires
- Questions and categories
- Scoring criteria

**questionnaire_responses**
- User responses
- Timestamps
- Analysis results

### AI Usage Tables

**ai_usage_tracking**
- Model usage logs
- Token counts
- Cost tracking
- Cumulative budget monitoring

## Security

### Authentication

- JWT tokens with access and refresh mechanism
- HTTP-only cookies for web clients
- Token expiration and rotation
- Secure password hashing (bcrypt)

### Authorization

Role-based access control (RBAC) with granular permissions:

```python
Permissions:
- users:read, users:write, users:delete
- organizations:read, organizations:write
- conversations:read, conversations:write
- knowledge:read, knowledge:write
- admin:access
```

### Data Protection

- Organization-level data isolation
- No PII/PHI in logs
- Input validation on all endpoints
- SQL injection prevention (ORM)
- XSS prevention (output escaping)
- CORS configuration
- Rate limiting

### Audit Logging

All sensitive operations logged:
- User authentication
- Data access
- Configuration changes
- Admin actions

## Deployment

### Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Architecture

```
┌─────────────────────────────────────────┐
│          Load Balancer (Nginx)          │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐    ┌────▼───┐    ┌─────▼──┐
│FastAPI │    │FastAPI │    │FastAPI │
│Instance│    │Instance│    │Instance│
└───┬────┘    └────┬───┘    └─────┬──┘
    │              │              │
    └──────────────┼──────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐    ┌───▼────┐    ┌────▼───┐
│Postgres│    │ Redis  │    │ChromaDB│
└────────┘    └────────┘    └────────┘
```

### Environment Variables

Required configuration in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
DATABASE_PASSWORD=secure_password

# Security
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=production

# AWS Bedrock
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
USE_BEDROCK=true

# Budget Protection
BUDGET_LIMIT_USD=50.00
ENABLE_COST_TRACKING=true
```

### Health Checks

- `GET /health` - Basic health status
- `GET /health/db` - Database connectivity
- `GET /health/redis` - Redis connectivity
- `GET /api/v1/budget/status` - Budget status

## Performance Considerations

### Caching Strategy

- **Redis**: Session data, user profiles, frequently accessed data
- **In-Memory**: Agent contexts, conversation state
- **Database**: Query result caching

### Optimization

- Connection pooling for database
- Async/await for I/O operations
- Background jobs for heavy processing
- Pagination for large datasets
- Lazy loading for relationships

### Scalability

- Horizontal scaling with multiple FastAPI instances
- Load balancing with Nginx
- Database read replicas
- Redis cluster for distributed caching
- ChromaDB can be replaced with Pinecone for scale

## Monitoring

### Metrics

- Request/response times
- Error rates
- Database query performance
- AI API usage and costs
- WebSocket connections
- Memory and CPU usage

### Logging

- Structured logging with JSON format
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Separate logs for security events
- Request/response logging
- Error tracking

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

**Authentication**
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - Logout

**Chat**
- `WS /ws/chat` - WebSocket chat
- `GET /api/v1/conversations` - List conversations
- `POST /api/v1/conversations/{id}/messages` - Send message

**Knowledge Base**
- `POST /api/v1/knowledge/upload` - Upload document
- `GET /api/v1/knowledge/search` - Semantic search
- `GET /api/v1/knowledge/documents` - List documents

**Budget**
- `GET /api/v1/budget/status` - Current budget status
- `GET /api/v1/budget/history` - Usage history

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --port 8000
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test types
pytest -m smoke
pytest -m unit
pytest -m integration
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

## Future Enhancements

- Multi-language support (Cantonese, Mandarin, English)
- Advanced RAG with re-ranking
- Voice interface integration
- Mobile app (React Native)
- Advanced analytics dashboard
- Custom ML models for health prediction
- Third-party EHR integrations

---

**Version**: 2.0  
**Last Updated**: March 2026  
**License**: MIT
