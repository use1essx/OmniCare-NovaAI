# Healthcare AI V2 - AI System Documentation

## Overview
This document describes the AI system architecture after the migration from OpenRouter to AWS Nova (Amazon Bedrock). The system now uses a unified AI client with budget protection and intelligent model selection.

---

## Architecture Overview

### Unified AI Client Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  (Agents, Services, Tools, Movement Analysis, Reports)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Unified AI Client                               │
│  - Abstract interface for all AI operations                 │
│  - Model selection logic (Lite vs Pro)                      │
│  - Request/response normalization                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Budget Protection Middleware                       │
│  - Real-time cost tracking                                  │
│  - $50 hard limit enforcement                               │
│  - Cost logging to database                                 │
│  - Alert system (80%, 90%, 95%, 100%)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Nova Bedrock Client                             │
│  - Boto3 integration                                        │
│  - Retry logic and error handling                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS Bedrock API                                 │
│  - Nova Lite (amazon.nova-lite-v1:0)                        │
│  - Nova Pro (amazon.nova-pro-v1:0)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## AI Models

### AWS Nova Models

#### Nova Lite (amazon.nova-lite-v1:0)
- **Cost:** $0.00006 per 1K input tokens, $0.00024 per 1K output tokens
- **Use Cases:**
  - Simple chat conversations
  - Routine health queries
  - Emotion analysis
  - Questionnaire generation
  - Daily check-ins
- **Performance:** Fast response times, cost-effective

#### Nova Pro (amazon.nova-pro-v1:0)
- **Cost:** $0.0008 per 1K input tokens, $0.0032 per 1K output tokens
- **Use Cases:**
  - Emergency/critical situations
  - Video analysis
  - Complex medical reasoning
  - Report generation
  - Answer extraction
- **Performance:** Advanced reasoning capabilities

### Intelligent Model Selection

The system automatically selects the appropriate model tier based on task type:

```python
def select_model_tier(task_type: str) -> str:
    """
    Select Nova model tier based on task requirements
    
    Rules:
    - Emergency/critical → Nova Pro
    - Video analysis → Nova Pro
    - Report generation → Nova Pro
    - Simple chat → Nova Lite
    - Questionnaire generation → Nova Lite
    - Emotion analysis → Nova Lite
    """
    
    # High complexity tasks → Nova Pro
    if task_type in ["emergency", "video_analysis", "report_generation", "complex_reasoning"]:
        return "pro"
    
    # Simple tasks → Nova Lite
    if task_type in ["chat", "simple_query", "emotion_analysis", "questionnaire"]:
        return "lite"
    
    # Default to Lite for cost efficiency
    return "lite"
```

---

## Budget Protection System

### Hard Budget Limit: $50 USD

The system enforces a **hard-coded $50 USD budget limit** for all AI costs:

- **Pre-request checks:** Budget verified before every AI request
- **Real-time tracking:** Costs logged to database immediately
- **Automatic blocking:** All requests blocked when limit reached
- **Persistent tracking:** Budget survives application restarts

### Budget Enforcement Flow

```
Request → Budget Check → Cost Calculation → Execute → Log Cost → Update Total
   │            │              │               │          │            │
   │            ▼              │               │          │            │
   │      Get current total    │               │          │            │
   │      from database        │               │          │            │
   │            │              │               │          │            │
   │            ▼              │               │          │            │
   │      If >= $50 → BLOCK    │               │          │            │
   │            │              │               │          │            │
   │            ▼              │               │          │            │
   │      Estimate cost        │               │          │            │
   │      If total + est > $50 │               │          │            │
   │      → BLOCK              │               │          │            │
   │            │              │               │          │            │
   └────────────┴──────────────┴───────────────┴──────────┴────────────┘
```

### Budget Alerts

Alerts are triggered at the following thresholds:

- **80% ($40.00)** - Warning
- **90% ($45.00)** - Critical warning
- **95% ($47.50)** - Final warning
- **100% ($50.00)** - All requests blocked

### Cost Tracking Database

All AI usage is logged to the `ai_usage_tracking` table:

```sql
CREATE TABLE ai_usage_tracking (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    model_tier VARCHAR(10) NOT NULL,  -- 'lite' or 'pro'
    model_id VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    cumulative_cost_usd DECIMAL(10, 2) NOT NULL,
    user_id INTEGER,
    session_id VARCHAR(100),
    task_type VARCHAR(50),
    request_id VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# AWS Bedrock Configuration (REQUIRED)
USE_BEDROCK=true
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Database (REQUIRED)
DATABASE_URL=postgresql://user:password@localhost:5432/healthcare_ai_v2
```

### API Key Management
- AWS credentials loaded from environment variables
- Never logged or exposed in error messages
- Validated on startup

---

## Usage Examples

### Basic AI Request

```python
from src.ai.unified_ai_client import UnifiedAIClient
from src.ai.unified_ai_client import AIRequest

client = UnifiedAIClient(db_session)

request = AIRequest(
    system_prompt="You are a healthcare assistant",
    user_prompt="What are the symptoms of flu?",
    model_tier="lite",  # or "pro", or None for auto-selection
    task_type="chat",
    user_id=123,
    session_id="session_abc"
)

response = await client.make_request(request)

print(f"Response: {response.content}")
print(f"Cost: ${response.cost}")
print(f"Model: {response.model}")
```

### Automatic Model Selection

```python
# Let the system choose the model tier
request = AIRequest(
    system_prompt="You are a healthcare assistant",
    user_prompt="Analyze this emergency situation...",
    task_type="emergency",  # Will automatically use Nova Pro
    user_id=123
)

response = await client.make_request(request)
```

### Check Budget Status

```python
from src.ai.cost_tracker import CostTracker

tracker = CostTracker(db_session)
status = tracker.get_budget_status()

print(f"Current total: ${status['current_total']}")
print(f"Remaining: ${status['remaining']}")
print(f"Percentage used: {status['percentage_used']}%")
print(f"Alert level: {status['alert_level']}")
```

---

## API Endpoints

### Budget Status (Admin Only)

**GET /api/v1/budget/status**

Returns current budget status:

```json
{
  "budget_limit": 50.00,
  "current_total": 35.42,
  "remaining": 14.58,
  "percentage_used": 70.84,
  "total_requests": 1247,
  "alert_level": "warning"
}
```

### Budget History (Admin Only)

**GET /api/v1/budget/history**

Query parameters:
- `start_date` (optional)
- `end_date` (optional)
- `limit` (default: 100)

Returns paginated usage history with cost breakdown by model.

---

## Features by Component

### 1. Main Chat (Unified AI Client)
**Location:** `src/ai/unified_ai_client.py`

**Features:**
- Standardized request/response format
- Automatic model selection
- Budget protection integration
- Cost tracking
- Error handling with retries

### 2. Movement Analysis (Video Analysis)
**Location:** `src/movement_analysis/video_processor.py`

**Model:** Nova Pro (vision-capable)
- Analyzes up to 10 frames per video
- Frame resolution: 512px width (resized for efficiency)
- Structured JSON output for data storage

### 3. Questionnaire Generation
**Location:** `src/tools/ai_questionnaire_generator.py`

**Model:** Nova Lite
- Cost-effective for questionnaire generation
- Maintains quality while reducing costs

### 4. Report Generation
**Location:** `src/custom_live_ai/reports/ai_analyzer.py`

**Model:** Nova Pro
- Advanced reasoning for medical reports
- Comprehensive analysis capabilities

### 5. Emotion Analysis
**Location:** `src/services/emotion_analysis_service.py`

**Model:** Nova Lite
- Fast emotion detection
- Cost-effective for real-time analysis

### 6. Answer Extraction
**Location:** `src/services/answer_extraction_service.py`

**Model:** Nova Pro
- High-quality extraction from documents
- Accurate medical information retrieval

---

## Error Handling

### Budget Exceeded Error

When the budget limit is reached, all AI requests will raise `BudgetExceededError`:

```python
from src.core.exceptions import BudgetExceededError

try:
    response = await client.make_request(request)
except BudgetExceededError as e:
    print(f"Budget limit reached: {e}")
    # Notify admin, log incident, etc.
```

### Retry Logic

The Nova client implements automatic retry logic:
- **3 retry attempts** per request
- **Exponential backoff:** 1s, 2s, 4s
- Handles transient AWS errors

---

## Cost Optimization

### Average Costs

Based on typical usage:

- **Chat message (Nova Lite):** ~$0.0001 - $0.0005
- **Questionnaire generation (Nova Lite):** ~$0.001 - $0.003
- **Video analysis (Nova Pro):** ~$0.01 - $0.05
- **Report generation (Nova Pro):** ~$0.005 - $0.02

### Daily Budget Planning

With a $50 monthly budget:
- **Daily budget:** ~$1.67
- **Estimated capacity:**
  - ~3,000-5,000 chat messages per day (Nova Lite)
  - ~500-1,000 questionnaires per day (Nova Lite)
  - ~30-50 video analyses per day (Nova Pro)
  - ~80-150 reports per day (Nova Pro)

---

## Testing

### Test Files
- `tests/test_unified_ai_client.py` - Unified client tests
- `tests/test_budget_middleware.py` - Budget protection tests
- `tests/test_cost_tracker.py` - Cost tracking tests
- `tests/test_model_selection.py` - Model selection tests
- `tests/test_nova_integration.py` - Nova integration tests

### Run Tests

```bash
# Run all AI tests
pytest tests/test_*nova*.py tests/test_*budget*.py tests/test_*cost*.py -v

# Run with coverage
pytest tests/test_*nova*.py --cov=src/ai --cov-report=term-missing
```

---

## Monitoring

### Health Check

The system includes budget status in health checks:

**GET /health**

```json
{
  "status": "healthy",
  "database": "connected",
  "nova_configured": true,
  "budget_status": {
    "current_total": 35.42,
    "percentage_used": 70.84,
    "alert_level": "warning"
  }
}
```

### Logging

All AI requests are logged with:
- Request ID
- Model tier and ID
- Token counts
- Cost
- User ID and session ID
- Task type
- Processing time

---

## Security Notes

- AWS credentials never logged or exposed
- All API requests use HTTPS
- Budget tracking prevents cost overruns
- Input validation on all user-provided content
- No PII/PHI sent to AI models without proper safeguards
- Admin-only access to budget endpoints

---

## Migration Notes

### Changes from OpenRouter

**Removed:**
- `openrouter_client.py` (700+ lines)
- `multi_model_client.py` (300+ lines)
- All OpenRouter API references
- `OPENROUTER_API_KEY` environment variable

**Added:**
- `unified_ai_client.py` - Unified interface
- `budget_middleware.py` - Budget protection
- `cost_tracker.py` - Cost tracking
- `ai_usage_tracking` database table
- Budget API endpoints

**Benefits:**
- 30-50% cost reduction vs OpenRouter
- AWS hackathon compliance
- Better budget control
- Simplified architecture
- Improved reliability

---

## Troubleshooting

### "Budget limit reached"
- Check current budget: `GET /api/v1/budget/status`
- Review usage history: `GET /api/v1/budget/history`
- Contact admin to reset budget if needed

### "AWS credentials not found"
- Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set in `.env`
- Verify `USE_BEDROCK=true` in `.env`
- Restart the application after adding credentials

### "Model not available"
- Verify AWS Bedrock access in your region
- Check AWS Bedrock model access permissions
- Ensure IAM user has `bedrock:InvokeModel` permission

---

**Last Updated:** 2026-03-13  
**Version:** 3.0.0 (Nova Migration)  
**Migration Status:** ✅ Complete

