# Healthcare AI V2 - Agent System

## Overview

The Healthcare AI V2 Agent System provides intelligent, specialized healthcare assistance through a sophisticated multi-agent architecture. Built for Hong Kong's healthcare context, it offers comprehensive support for vulnerable populations including elderly health monitoring and child/teen mental health support.

## Architecture

### Core Components

```
Healthcare AI V2 Agent System
├── Base Agent (Abstract)           # Core agent interface and functionality
├── Specialized Agents
│   ├── 慧心助手                      # Physical health monitoring
│   ├── 小星星                        # Emotional support & crisis intervention
│   ├── Safety Guardian             # Emergency response
│   └── Wellness Coach              # Preventive health coaching
├── Orchestrator                    # Intelligent agent routing
└── Context Manager                 # Conversation history & user profiles
```

### Agent Specializations

#### 🏥 慧心助手
- **Purpose**: Comprehensive illness monitoring with elderly focus
- **Specialties**: 
  - Physical symptom assessment
  - Chronic disease management (diabetes, hypertension, arthritis)
  - Medication adherence and side effect monitoring
  - Age-appropriate health guidance
- **Cultural Adaptation**: Hong Kong elderly care context, Traditional Chinese respect
- **Languages**: Primarily Traditional Chinese with medical English terms

#### 🌟 小星星
- **Purpose**: Child/teen mental health support with VTuber personality
- **Specialties**:
  - School stress and academic pressure (DSE system)
  - Social anxiety and peer relationships
  - Crisis detection and intervention
  - Family dynamics and cultural pressures
- **Cultural Adaptation**: Hong Kong education system, generational gaps
- **Languages**: Mixed English/Chinese with youth slang and emojis

#### 🚨 Safety Guardian
- **Purpose**: Emergency response for both populations
- **Specialties**:
  - Medical emergency detection and guidance
  - Mental health crisis intervention
  - Professional service coordination
  - Family notification systems
- **Emergency Resources**: Hong Kong 999, Samaritans, Hospital Authority
- **Languages**: Clear, authoritative communication in user's preferred language

#### 💪 Wellness Coach
- **Purpose**: Preventive health and lifestyle guidance
- **Specialties**:
  - Health habit formation
  - Exercise and nutrition guidance
  - Stress management
  - Age-appropriate prevention strategies
- **Cultural Adaptation**: Hong Kong work culture, small living spaces
- **Languages**: Motivational, encouraging tone in both languages

## Key Features

### 🧠 Intelligent Agent Routing
- **Confidence-based selection**: Agents score their ability to handle requests
- **Emergency override**: Safety Guardian automatically activated for crises
- **Multi-agent support**: Complex issues can involve multiple agents
- **Context-aware routing**: User profile and conversation history inform selection

### 🗣️ Cultural & Language Adaptation
- **Hong Kong Context**: Understanding of local healthcare system, education (DSE), work culture
- **Bilingual Support**: Traditional Chinese, English, and mixed-language conversations
- **Age-appropriate Communication**: Different styles for children, teens, adults, elderly
- **Cultural Sensitivity**: Family dynamics, traditional medicine integration, respect hierarchy

### 📚 Conversation Management
- **Persistent Context**: User profiles, health patterns, conversation history
- **Agent Transitions**: Smooth handoffs between specialized agents
- **Pattern Recognition**: Health trends, medication adherence, symptom progression
- **Professional Integration**: Alert generation, escalation protocols

### 🚨 Safety & Professional Integration
- **Crisis Detection**: Automatic identification of emergency situations
- **Professional Alerts**: Structured notifications for healthcare providers
- **Family Notifications**: Age-appropriate contact of parents/guardians
- **Escalation Protocols**: Clear pathways to professional care

## Usage Examples

### Basic Agent Usage

```python
from src.agents import AgentOrchestrator, ConversationContextManager
from src.ai import HealthcareAIService

# Initialize system
ai_service = HealthcareAIService()
orchestrator = AgentOrchestrator(ai_service)
context_manager = ConversationContextManager()

# Create conversation context
context = context_manager.create_context(
    user_id="user_123",
    session_id="session_456",
    user_input="我最近頭暈，血壓藥食緊但有副作用"
)

# Route to appropriate agent
agent, orchestration_result = await orchestrator.route_request(
    user_input="我最近頭暈，血壓藥食緊但有副作用",
    context=context
)

# Generate response
response = await agent.generate_response(
    "我最近頭暈，血壓藥食緊但有副作用", 
    context
)

print(f"Agent: {agent.agent_id}")
print(f"Response: {response.content}")
print(f"Urgency: {response.urgency_level}")
print(f"Professional Alert: {response.professional_alert_needed}")
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from src.agents import AgentOrchestrator, ConversationContextManager
from src.ai import HealthcareAIService

app = FastAPI()

# Initialize at startup
ai_service = HealthcareAIService()
orchestrator = AgentOrchestrator(ai_service)
context_manager = ConversationContextManager()

@app.post("/chat")
async def chat_endpoint(
    user_id: str,
    message: str,
    session_id: str = None
):
    try:
        # Create context
        context = context_manager.create_context(
            user_id=user_id,
            session_id=session_id or f"session_{user_id}",
            user_input=message
        )
        
        # Route and process
        agent, _ = await orchestrator.route_request(
            user_input=message,
            context=context
        )
        
        response = await agent.generate_response(message, context)
        
        return {
            "response": response.content,
            "agent": agent.agent_id,
            "urgency": response.urgency_level.value,
            "suggested_actions": response.suggested_actions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Agent Selection Logic

### Confidence Scoring
Each agent evaluates its ability to handle a request based on:
- **Keyword Matching**: Relevant terms for agent specialization
- **User Profile**: Age group, health history, cultural context
- **Conversation History**: Previous topics, agent performance
- **Urgency Factors**: Emergency keywords, severity indicators

### Emergency Override
Safety Guardian automatically activates when detecting:
- **Medical Emergencies**: "chest pain", "can't breathe", "unconscious"
- **Mental Health Crises**: "suicide", "self-harm", "want to die"
- **Critical Keywords**: "emergency", "help", "urgent", "救命"

### Multi-Agent Scenarios
When multiple agents score highly:
1. **Primary Agent**: Highest confidence score handles main response
2. **Secondary Consultation**: Other agents provide supplementary input
3. **Handoff Protocol**: Smooth transitions with context preservation

## Professional Integration

### Alert System
Agents generate structured alerts for:

```python
{
    "alert_type": "health_concern",
    "urgency": "medium",
    "reason": "Medication compliance issue detected",
    "user_input_summary": "Patient reports stopping medication due to side effects",
    "recommended_action": "Pharmacist consultation recommended",
    "age_group": "elderly",
    "timestamp": "2025-01-15T10:30:00Z"
}
```

### Hong Kong Resources Integration
- **Emergency Services**: 999 integration
- **Mental Health**: Samaritans (2896 0000), Suicide Prevention (2382 0000)
- **Healthcare**: Hospital Authority, government clinics
- **Child Protection**: Child Protection Hotline (2755 1122)

## Configuration

### Agent Capabilities
```python
# Each agent defines its capabilities
illness_monitor_capabilities = [
    AgentCapability.ILLNESS_MONITORING,
    AgentCapability.MEDICATION_GUIDANCE,
    AgentCapability.CHRONIC_DISEASE_MANAGEMENT
]

mental_health_capabilities = [
    AgentCapability.MENTAL_HEALTH_SUPPORT,
    AgentCapability.CRISIS_INTERVENTION,
    AgentCapability.EDUCATIONAL_SUPPORT
]
```

### Cultural Adaptations
```python
# Hong Kong specific adaptations
hk_cultural_context = {
    "education_system": "DSE pressure awareness",
    "family_dynamics": "Filial piety, face-saving",
    "healthcare_system": "Public/private integration",
    "living_conditions": "Small space, high density"
}
```

## Testing

### Running Examples
```bash
# Run comprehensive demo
cd healthcare_ai_v2/src/agents
python examples.py

# Test specific agent
python -c "
import asyncio
from examples import HealthcareAIV2Demo

async def test():
    demo = HealthcareAIV2Demo()
    result = await demo.process_conversation(
        user_id='test_user',
        session_id='test_session',
        user_input='I have a headache and feel dizzy'
    )
    print(result)

asyncio.run(test())
"
```

### Unit Testing
```python
import pytest
from src.agents import IllnessMonitorAgent
from src.ai import HealthcareAIService

@pytest.mark.asyncio
async def test_illness_monitor_agent():
    ai_service = HealthcareAIService()
    agent = IllnessMonitorAgent(ai_service)
    
    # Test capability detection
    can_handle, confidence = agent.can_handle(
        "我血壓高，食藥後有副作用",
        mock_context
    )
    
    assert can_handle == True
    assert confidence > 0.7
```

## Performance Considerations

### Optimization Strategies
1. **Agent Caching**: Reuse agent instances across requests
2. **Context Trimming**: Limit conversation history length
3. **Parallel Evaluation**: Concurrent agent capability assessment
4. **Session Management**: Automatic cleanup of expired sessions

### Monitoring Metrics
- **Agent Selection Accuracy**: Confidence scores vs. user satisfaction
- **Response Times**: End-to-end processing latency
- **Professional Alert Rate**: Emergency detection effectiveness
- **User Engagement**: Session length, follow-up rates

## Security & Privacy

### Data Protection
- **Conversation Encryption**: All messages encrypted in transit and at rest
- **User Anonymization**: Personal identifiers separated from conversation data
- **Professional Alerts**: HIPAA-compliant structured notifications
- **Session Isolation**: No cross-user data leakage

### Access Controls
- **Agent Permissions**: Role-based access to different agent capabilities
- **Professional Alerts**: Restricted to authorized healthcare providers
- **Emergency Overrides**: Special protocols for crisis situations

## Future Enhancements

### Planned Features
1. **Advanced Pattern Recognition**: ML-based health trend analysis
2. **Multilingual Expansion**: Support for additional Hong Kong languages
3. **Professional Dashboard**: Real-time monitoring for healthcare providers
4. **Mobile Integration**: Native iOS/Android SDK
5. **Voice Interface**: Speech-to-text integration for accessibility

### Integration Roadmap
- **EHR Integration**: Direct connection to Electronic Health Records
- **Telehealth Platforms**: Video consultation integration
- **Wearable Devices**: Real-time health data integration
- **Government Services**: Hong Kong eHealth platform connectivity

## Support & Documentation

### Additional Resources
- **API Documentation**: `/docs` endpoint with interactive examples
- **Configuration Guide**: Environment setup and customization
- **Deployment Guide**: Production deployment best practices
- **Troubleshooting**: Common issues and solutions

### Community & Support
- **Issue Tracking**: GitHub issues for bug reports and feature requests
- **Development Guide**: Contributing to the agent system
- **Professional Training**: Healthcare provider onboarding materials

---

**Healthcare AI V2 Agent System** - Bridging technology and compassionate healthcare for Hong Kong's vulnerable populations. 🏥💙
