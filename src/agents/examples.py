"""
Healthcare AI V2 Agent System Examples
====================================

Comprehensive examples demonstrating the usage of the Healthcare AI V2 agent system,
including agent orchestration, context management, and various healthcare scenarios.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from ..ai.ai_service import HealthcareAIService
from .orchestrator import AgentOrchestrator
from .context_manager import ConversationContextManager


# Configure logging for examples
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthcareAIV2Demo:
    """
    Demonstration class for Healthcare AI V2 agent system.
    
    Shows how to integrate all components for real-world healthcare
    AI conversations with intelligent agent routing and context management.
    """
    
    def __init__(self):
        """Initialize the demo system."""
        # Initialize core services
        self.ai_service = HealthcareAIService()
        self.orchestrator = AgentOrchestrator(self.ai_service)
        self.context_manager = ConversationContextManager()
        
        logger.info("Healthcare AI V2 Demo System initialized")
    
    async def process_conversation(
        self, 
        user_id: str,
        session_id: str,
        user_input: str,
        preferred_agent: str = None
    ) -> Dict[str, Any]:
        """
        Process a complete conversation turn with agent orchestration.
        
        Args:
            user_id: User identifier
            session_id: Session identifier  
            user_input: User's message
            preferred_agent: Optional agent preference
            
        Returns:
            Complete conversation result
        """
        logger.info(f"Processing conversation for user {user_id}: {user_input[:50]}...")
        
        try:
            # Create conversation context
            context = self.context_manager.create_context(
                user_id=user_id,
                session_id=session_id,
                user_input=user_input
            )
            
            # Route to appropriate agent
            selected_agent, orchestration_result = await self.orchestrator.route_request(
                user_input=user_input,
                context=context,
                preferred_agent=preferred_agent
            )
            
            # Track agent transition
            memory = self.context_manager.get_or_create_conversation_memory(user_id, session_id)
            previous_agent = memory.active_agent
            
            if previous_agent != selected_agent.agent_id:
                self.context_manager.track_agent_transition(
                    memory=memory,
                    from_agent=previous_agent,
                    to_agent=selected_agent.agent_id,
                    reason=f"Routing confidence: {orchestration_result.confidence:.2f}"
                )
            
            # Generate agent response
            agent_response = await selected_agent.generate_response(user_input, context)
            
            # Update conversation history
            self.context_manager.update_conversation_history(
                memory=memory,
                content=agent_response.content,
                role="assistant",
                agent_id=selected_agent.agent_id,
                metadata={
                    "confidence": agent_response.confidence,
                    "urgency": agent_response.urgency_level.value,
                    "requires_followup": agent_response.requires_followup
                }
            )
            
            # Handle professional alerts
            if agent_response.professional_alert_needed:
                self.context_manager.record_professional_alert(
                    memory=memory,
                    alert_details=agent_response.alert_details
                )
            
            # Return comprehensive result
            return {
                "response": agent_response.content,
                "agent_used": selected_agent.agent_id,
                "confidence": agent_response.confidence,
                "urgency": agent_response.urgency_level.value,
                "suggested_actions": agent_response.suggested_actions,
                "requires_followup": agent_response.requires_followup,
                "professional_alert": agent_response.professional_alert_needed,
                "orchestration": {
                    "strategy": orchestration_result.selection_strategy.value,
                    "confidence": orchestration_result.confidence,
                    "reasons": orchestration_result.reasons,
                    "emergency_override": orchestration_result.emergency_override
                },
                "context_summary": self.context_manager.get_conversation_summary(memory)
            }
            
        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
            return {
                "error": str(e),
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again or seek professional help if this is urgent.",
                "agent_used": "error_handler",
                "confidence": 0.0
            }
    
    async def run_healthcare_scenarios(self):
        """Run various healthcare scenarios to demonstrate the system."""
        
        scenarios = [
            # Elderly health monitoring scenario
            {
                "user_id": "elderly_user_001",
                "session_id": "session_001",
                "messages": [
                    "我今年75歲，最近經常頭暈，血壓藥也在食緊",
                    "頭暈主要係起身嘅時候，有時候行路都唔穩",
                    "血壓藥係早上食，但有時會忘記"
                ]
            },
            
            # Teen mental health scenario
            {
                "user_id": "teen_user_001", 
                "session_id": "session_002",
                "messages": [
                    "I'm 16 and really stressed about DSE. Can't sleep and feel anxious all the time",
                    "My parents don't understand the pressure. They just tell me to study harder",
                    "Sometimes I feel like giving up. Everything seems too difficult"
                ]
            },
            
            # Emergency scenario
            {
                "user_id": "emergency_user_001",
                "session_id": "session_003", 
                "messages": [
                    "My grandpa is having chest pain and difficulty breathing. What should I do?",
                    "He's 82 years old and conscious but looks very pale"
                ]
            },
            
            # Wellness coaching scenario
            {
                "user_id": "wellness_user_001",
                "session_id": "session_004",
                "messages": [
                    "I want to start exercising but don't know where to begin",
                    "I work long hours in Central and live in a small flat in Mong Kok",
                    "What kind of exercise can I do at home?"
                ]
            }
        ]
        
        logger.info("=" * 60)
        logger.info("HEALTHCARE AI V2 SCENARIO DEMONSTRATIONS")
        logger.info("=" * 60)
        
        for i, scenario in enumerate(scenarios, 1):
            logger.info(f"\n🏥 SCENARIO {i}: {scenario['user_id']}")
            logger.info("-" * 40)
            
            for j, message in enumerate(scenario["messages"], 1):
                logger.info(f"\n💬 Message {j}: {message}")
                
                result = await self.process_conversation(
                    user_id=scenario["user_id"],
                    session_id=scenario["session_id"],
                    user_input=message
                )
                
                if "error" in result:
                    logger.error(f"❌ Error: {result['error']}")
                    continue
                
                logger.info(f"🤖 Agent: {result['agent_used']}")
                logger.info(f"🎯 Confidence: {result['confidence']:.2f}")
                logger.info(f"🚨 Urgency: {result['urgency']}")
                logger.info(f"💡 Response: {result['response'][:200]}...")
                
                if result['professional_alert']:
                    logger.warning("⚠️  Professional alert generated!")
                
                if result['suggested_actions']:
                    logger.info(f"📋 Actions: {', '.join(result['suggested_actions'][:3])}...")
                
                # Small delay for readability
                await asyncio.sleep(0.5)
        
        logger.info("\n" + "=" * 60)
        logger.info("DEMONSTRATION COMPLETE")
        logger.info("=" * 60)
    
    async def test_agent_capabilities(self):
        """Test individual agent capabilities."""
        
        test_cases = [
            # Illness Monitor Agent Tests
            {
                "agent": "illness_monitor",
                "inputs": [
                    "我血壓高，醫生開咗藥但有副作用",
                    "My diabetes medication makes me feel nauseous",
                    "關節痛得厲害，特別係落雨天"
                ]
            },
            
            # Mental Health Agent Tests  
            {
                "agent": "mental_health",
                "inputs": [
                    "I'm feeling really anxious about school exams",
                    "我好擔心，唔知點解成日都好緊張",
                    "My friends don't understand me and I feel so alone"
                ]
            },
            
            # Safety Guardian Tests
            {
                "agent": "safety_guardian", 
                "inputs": [
                    "I think I'm having a heart attack",
                    "我想死，生活太痛苦了",
                    "Emergency! My child fell and won't wake up"
                ]
            },
            
            # Wellness Coach Tests
            {
                "agent": "wellness_coach",
                "inputs": [
                    "How can I improve my diet and exercise routine?",
                    "我想減肥但唔知從何開始",
                    "What are some stress management techniques for busy professionals?"
                ]
            }
        ]
        
        logger.info("\n🧪 TESTING INDIVIDUAL AGENT CAPABILITIES")
        logger.info("=" * 50)
        
        for test_case in test_cases:
            agent_id = test_case["agent"]
            logger.info(f"\n🤖 Testing {agent_id.upper()}")
            logger.info("-" * 30)
            
            for i, test_input in enumerate(test_case["inputs"], 1):
                logger.info(f"\n📝 Test {i}: {test_input}")
                
                result = await self.process_conversation(
                    user_id="test_user",
                    session_id=f"test_{agent_id}_{i}",
                    user_input=test_input,
                    preferred_agent=agent_id
                )
                
                logger.info(f"✅ Agent: {result.get('agent_used', 'unknown')}")
                logger.info(f"📊 Confidence: {result.get('confidence', 0):.2f}")
                logger.info(f"🎯 Response Preview: {result.get('response', '')[:150]}...")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            "ai_service_initialized": self.ai_service is not None,
            "available_agents": self.orchestrator.get_available_agents(),
            "agent_capabilities": self.orchestrator.get_agent_capabilities(),
            "active_sessions": len(self.context_manager.conversation_memories),
            "user_profiles": len(self.context_manager.user_profiles),
            "system_timestamp": datetime.now().isoformat()
        }


async def main():
    """Main demo function."""
    
    # Initialize demo system
    demo = HealthcareAIV2Demo()
    
    # Show system status
    status = demo.get_system_status()
    logger.info("🏥 Healthcare AI V2 System Status:")
    for key, value in status.items():
        logger.info(f"  {key}: {value}")
    
    # Run capability tests
    await demo.test_agent_capabilities()
    
    # Run healthcare scenarios
    await demo.run_healthcare_scenarios()
    
    # Final system status
    final_status = demo.get_system_status()
    logger.info(f"\n📊 Final Status - Active Sessions: {final_status['active_sessions']}, Users: {final_status['user_profiles']}")


# Example usage patterns for integration
class IntegrationExamples:
    """Examples of how to integrate the agent system into applications."""
    
    @staticmethod
    async def fastapi_endpoint_example():
        """Example of FastAPI endpoint integration."""
        
        # This would be in your FastAPI route handler
        async def chat_endpoint(
            user_id: str,
            message: str,
            session_id: str = None,
            preferred_agent: str = None
        ):
            """Chat endpoint using Healthcare AI V2 agents."""
            
            # Initialize system (usually done once at startup)
            ai_service = HealthcareAIService()
            orchestrator = AgentOrchestrator(ai_service)
            context_manager = ConversationContextManager()
            
            # Create context
            context = context_manager.create_context(
                user_id=user_id,
                session_id=session_id or f"session_{user_id}_{datetime.now().timestamp()}",
                user_input=message
            )
            
            # Route and process
            agent, orchestration = await orchestrator.route_request(
                user_input=message,
                context=context,
                preferred_agent=preferred_agent
            )
            
            # Generate response
            response = await agent.generate_response(message, context)
            
            return {
                "response": response.content,
                "agent": agent.agent_id,
                "confidence": response.confidence,
                "urgency": response.urgency_level.value,
                "suggested_actions": response.suggested_actions,
                "professional_alert": response.professional_alert_needed
            }
    
    @staticmethod
    async def websocket_example():
        """Example of WebSocket integration for real-time chat."""
        
        # This would be in your WebSocket handler
        async def websocket_chat_handler(websocket, user_id: str):
            """WebSocket handler for real-time healthcare chat."""
            
            # Initialize once per connection
            ai_service = HealthcareAIService()
            orchestrator = AgentOrchestrator(ai_service)
            context_manager = ConversationContextManager()
            session_id = f"ws_{user_id}_{datetime.now().timestamp()}"
            
            try:
                await websocket.accept()
                
                while True:
                    # Receive message
                    data = await websocket.receive_json()
                    message = data.get("message", "")
                    
                    if not message:
                        continue
                    
                    # Process with agents
                    context = context_manager.create_context(
                        user_id=user_id,
                        session_id=session_id,
                        user_input=message
                    )
                    
                    agent, _ = await orchestrator.route_request(
                        user_input=message,
                        context=context
                    )
                    
                    response = await agent.generate_response(message, context)
                    
                    # Send response
                    await websocket.send_json({
                        "type": "agent_response",
                        "content": response.content,
                        "agent": agent.agent_id,
                        "urgency": response.urgency_level.value,
                        "requires_followup": response.requires_followup,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Send professional alert if needed
                    if response.professional_alert_needed:
                        await websocket.send_json({
                            "type": "professional_alert",
                            "alert_details": response.alert_details,
                            "timestamp": datetime.now().isoformat()
                        })
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.close()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
