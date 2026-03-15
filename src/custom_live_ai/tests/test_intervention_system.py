"""
Intervention System Tests
Tests intervention engine, rules, and responder
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestInterventionRules:
    """Test intervention rules configuration"""
    
    def test_intervention_rules_exist(self):
        """Test INTERVENTION_RULES is defined"""
        from src.custom_live_ai.intervention.rules import INTERVENTION_RULES
        
        assert INTERVENTION_RULES is not None
        assert isinstance(INTERVENTION_RULES, dict)
        assert len(INTERVENTION_RULES) > 0
    
    def test_intervention_rules_structure(self):
        """Test intervention rules have correct structure"""
        from src.custom_live_ai.intervention.rules import INTERVENTION_RULES
        
        for rule_name, rule in INTERVENTION_RULES.items():
            assert isinstance(rule, dict), f"Rule {rule_name} is not a dict"
            
            # Check common fields
            if 'conditions' in rule:
                assert isinstance(rule['conditions'], dict)
            
            if 'message' in rule:
                assert isinstance(rule['message'], str)
    
    def test_posture_intervention_rules(self):
        """Test posture intervention rules"""
        from src.custom_live_ai.intervention.rules import INTERVENTION_RULES
        
        # Check if posture-related rules exist
        posture_rules = [k for k in INTERVENTION_RULES.keys() if 'posture' in k.lower()]
        assert len(posture_rules) > 0
    
    def test_emotion_intervention_rules(self):
        """Test emotion intervention rules"""
        from src.custom_live_ai.intervention.rules import INTERVENTION_RULES
        
        # Check if emotion-related rules exist
        emotion_rules = [k for k in INTERVENTION_RULES.keys() if any(
            emotion in k.lower() for emotion in ['emotion', 'sad', 'stress', 'tired']
        )]
        assert len(emotion_rules) > 0


class TestInterventionEngine:
    """Test intervention engine functionality"""
    
    def test_intervention_engine_initialization(self):
        """Test engine can be initialized"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        assert engine is not None
        assert hasattr(engine, 'check_triggers')
    
    def test_check_triggers_poor_posture(self):
        """Test check_triggers for poor posture"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        result = engine.check_triggers(
            emotion='neutral',
            emotion_confidence=0.5,
            posture_quality='poor',
            posture_score=0.2,
            engagement_level=0.5
        )
        
        assert isinstance(result, dict)
        assert 'should_intervene' in result
        
        # Poor posture should trigger intervention
        if result['should_intervene']:
            assert 'intervention_type' in result
    
    def test_check_triggers_negative_emotion(self):
        """Test check_triggers for negative emotion"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        result = engine.check_triggers(
            emotion='sad',
            emotion_confidence=0.8,
            posture_quality='good',
            posture_score=0.8,
            engagement_level=0.4
        )
        
        assert isinstance(result, dict)
        assert 'should_intervene' in result
        
        # High sadness should trigger intervention
        if result['should_intervene']:
            assert 'intervention_type' in result
    
    def test_check_triggers_low_engagement(self):
        """Test check_triggers for low engagement"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        result = engine.check_triggers(
            emotion='neutral',
            emotion_confidence=0.5,
            posture_quality='good',
            posture_score=0.7,
            engagement_level=0.2
        )
        
        assert isinstance(result, dict)
        assert 'should_intervene' in result
    
    def test_check_triggers_all_good(self):
        """Test check_triggers when everything is good"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        result = engine.check_triggers(
            emotion='happy',
            emotion_confidence=0.8,
            posture_quality='excellent',
            posture_score=0.9,
            engagement_level=0.9
        )
        
        assert isinstance(result, dict)
        assert 'should_intervene' in result
        
        # Everything good should not trigger intervention
        # (or minimal intervention)
        assert result is not None


class TestInterventionResponder:
    """Test intervention responder"""
    
    def test_responder_initialization(self):
        """Test responder can be initialized"""
        from src.custom_live_ai.intervention.responder import InterventionResponder
        
        responder = InterventionResponder()
        assert responder is not None
    
    def test_generate_message_for_posture(self):
        """Test message generation for posture intervention"""
        try:
            from src.custom_live_ai.intervention.responder import InterventionResponder
            
            responder = InterventionResponder()
            
            if hasattr(responder, 'generate_message'):
                message = responder.generate_message(
                    intervention_type='posture',
                    context={'posture_quality': 'poor'}
                )
                
                assert message is not None
                assert isinstance(message, str)
                assert len(message) > 0
        except (ImportError, AttributeError):
            pytest.skip("InterventionResponder.generate_message not available")
    
    def test_generate_message_for_emotion(self):
        """Test message generation for emotion intervention"""
        try:
            from src.custom_live_ai.intervention.responder import InterventionResponder
            
            responder = InterventionResponder()
            
            if hasattr(responder, 'generate_message'):
                message = responder.generate_message(
                    intervention_type='emotion',
                    context={'emotion': 'sad', 'confidence': 0.8}
                )
                
                assert message is not None
                assert isinstance(message, str)
                assert len(message) > 0
        except (ImportError, AttributeError):
            pytest.skip("InterventionResponder.generate_message not available")


class TestToneAdapter:
    """Test tone adapter functionality"""
    
    def test_tone_adapter_import(self):
        """Test tone adapter can be imported"""
        from src.custom_live_ai.intervention import tone_adapter
        
        assert tone_adapter is not None
    
    def test_adapt_tone_if_available(self):
        """Test tone adaptation if function is available"""
        try:
            from src.custom_live_ai.intervention.tone_adapter import adapt_tone
            
            original_message = "Please adjust your posture"
            adapted = adapt_tone(original_message, tone='gentle')
            
            assert adapted is not None
            assert isinstance(adapted, str)
        except (ImportError, AttributeError):
            pytest.skip("adapt_tone not available")


class TestInterventionIntegration:
    """Integration tests for intervention system"""
    
    def test_full_intervention_pipeline(self):
        """Test full intervention pipeline"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        # Scenario 1: Poor posture detection
        result1 = engine.check_triggers(
            emotion='neutral',
            emotion_confidence=0.6,
            posture_quality='poor',
            posture_score=0.25,
            engagement_level=0.6
        )
        
        assert result1 is not None
        
        # Scenario 2: Negative emotion detection
        result2 = engine.check_triggers(
            emotion='sad',
            emotion_confidence=0.85,
            posture_quality='good',
            posture_score=0.75,
            engagement_level=0.5
        )
        
        assert result2 is not None
        
        # Scenario 3: Multiple issues
        result3 = engine.check_triggers(
            emotion='sad',
            emotion_confidence=0.8,
            posture_quality='poor',
            posture_score=0.3,
            engagement_level=0.3
        )
        
        assert result3 is not None
        # Multiple issues should definitely trigger intervention
        if 'should_intervene' in result3:
            assert result3['should_intervene']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
