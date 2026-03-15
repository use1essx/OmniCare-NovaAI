"""
Centralized Prompt Composition for Healthcare AI V2
Assembles system prompts in consistent layer order for all agents
"""

from typing import Any, List, Optional
from src.agents.base_agent import AgentContext
from src.core.prompt_loader import get_prompt_loader, PromptLoader
from src.core.language_manager import get_language_manager, LanguageManager
from src.core.tone_profile import ToneProfileManager, ToneProfile
from src.core.logging import get_logger

logger = get_logger(__name__)


class PromptComposer:
    """
    Central prompt composition system that assembles full system prompts in consistent layer order.
    
    Layer order (top → bottom):
    1) Language Instruction (from LanguageManager)
    2) Global Base System (prompts/system/base_system.txt)
    3) Agent Persona (prompts/agents/{agent_name}/{language}.txt, fallback EN)
    4) Active Skills (prompts/skills/{skill}/*.txt, if any)
    5) Context Section (age group, relevant tags)
    
    Used by: wellness_coach, mental_health, illness_monitor, safety_guardian, unified_agent
    """
    
    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        language_manager: Optional[LanguageManager] = None
    ):
        """
        Initialize PromptComposer with optional custom loader/manager (for testing).
        
        Args:
            prompt_loader: PromptLoader instance (defaults to singleton)
            language_manager: LanguageManager instance (defaults to singleton)
        """
        self.prompt_loader = prompt_loader or get_prompt_loader()
        self.language_manager = language_manager or get_language_manager()
    
    def compose_system_prompt(
        self,
        agent_name: str,
        context: AgentContext,
        active_skills: Optional[List[str]] = None
    ) -> str:
        """
        Build the full SYSTEM prompt for the LLM for a given agent.
        
        Args:
            agent_name: Agent identifier (e.g., "wellness_coach", "mental_health")
            context: AgentContext with user profile, language preference, etc.
            active_skills: Optional list of skill names to include (e.g., ["mental_health", "sleep_support"])
        
        Returns:
            Fully composed system prompt string
        """
        parts = []
        
        # Layer 1: Language Instruction
        language_instruction = self._get_language_instruction(context)
        if language_instruction:
            parts.append(language_instruction)
        
        # Layer 2: Global Base System
        base_system = self._get_base_system()
        if base_system:
            parts.append(base_system)
        
        # Layer 3: Agent Persona
        agent_persona = self._get_agent_persona(agent_name, context)
        if agent_persona:
            parts.append(agent_persona)
        
        # Layer 4: Tone & Style (from user profile)
        tone_section = self._build_tone_section(context)
        if tone_section:
            parts.append(tone_section)
        
        # Layer 5: Interaction Pattern (age-aware)
        interaction_pattern = self._build_interaction_pattern_section(context)
        if interaction_pattern:
            parts.append(interaction_pattern)
        
        # Layer 6: Tool Usage (agent + skills aware)
        tool_usage = self._build_tool_usage_section(agent_name, active_skills)
        if tool_usage:
            parts.append(tool_usage)
        
        # Layer 7: Active Skills
        if active_skills:
            skills_section = self._get_skills_section(active_skills)
            if skills_section:
                parts.append(skills_section)
        
        # Layer 8: Context Section
        context_section = self._build_context_section(context)
        if context_section:
            parts.append(context_section)
        
        # Layer 9: Conversation Memory (for AI memory across sessions)
        memory_section = self._build_conversation_memory_section(context)
        if memory_section:
            parts.append(memory_section)
        
        # Layer 10: Final Enforcement (critical rules reminder)
        final_enforcement = self._build_final_enforcement_section(context)
        if final_enforcement:
            parts.append(final_enforcement)
        
        # Join all parts with clear separators
        return "\n\n---\n\n".join(parts)
    
    def _get_language_instruction(self, context: AgentContext) -> str:
        """
        Get language instruction from LanguageManager.
        
        Args:
            context: AgentContext with language_preference
        
        Returns:
            Language instruction text (empty if not needed)
        """
        language_preference = getattr(context, 'language_preference', 'en')
        normalized_lang = self.language_manager.normalize_language(language_preference)
        
        # Get language instruction (e.g., "Please respond in English" or "請用繁體中文（香港）回覆")
        instruction = self.language_manager.get_language_instruction(normalized_lang)
        return instruction if instruction else ""
    
    def _get_base_system(self) -> str:
        """
        Load global base system prompt.
        
        Returns:
            Base system prompt content
        """
        base_system = self.prompt_loader.load_system_prompt("base_system", default="")
        if not base_system:
            logger.warning("base_system.txt is empty or missing")
        return base_system
    
    def _get_agent_persona(self, agent_name: str, context: AgentContext) -> str:
        """
        Load agent-specific persona prompt in appropriate language.
        
        Args:
            agent_name: Agent identifier (e.g., "wellness_coach")
            context: AgentContext with language preference
        
        Returns:
            Agent persona prompt content
        """
        language_preference = getattr(context, 'language_preference', 'en')
        normalized_lang = self.language_manager.normalize_language(language_preference)
        
        # Try to load agent prompt in user's language
        agent_prompt = self.prompt_loader.load_agent_prompt(
            agent_name=agent_name,
            prompt_type=normalized_lang,
            default=""
        )
        
        # Fallback to English if language-specific prompt not found
        if not agent_prompt and normalized_lang != "en":
            logger.info(f"Agent '{agent_name}' prompt not found for language '{normalized_lang}', falling back to English")
            agent_prompt = self.prompt_loader.load_agent_prompt(
                agent_name=agent_name,
                prompt_type="en",
                default=""
            )
        
        # Last resort: minimal fallback
        if not agent_prompt:
            logger.warning(f"No prompt found for agent '{agent_name}', using minimal fallback")
            agent_prompt = f"You are a {agent_name.replace('_', ' ')} agent providing healthcare support."
        
        return agent_prompt
    
    def _get_skills_section(self, active_skills: List[str]) -> str:
        """
        Build skills section from active skill names.
        
        Args:
            active_skills: List of skill names (e.g., ["mental_health", "sleep_support"])
        
        Returns:
            Formatted skills section with all active skills
        """
        if not active_skills:
            return ""
        
        skill_parts = ["=== Active Skills ==="]
        
        for skill_name in active_skills:
            # Load system_prompt.txt for this skill
            system_prompt = self.prompt_loader.load_skill_prompt(
                skill_name=skill_name,
                prompt_type="system_prompt",
                default=""
            )
            
            # Load response_guidelines.txt for this skill
            response_guidelines = self.prompt_loader.load_skill_prompt(
                skill_name=skill_name,
                prompt_type="response_guidelines",
                default=""
            )
            
            if system_prompt or response_guidelines:
                skill_parts.append(f"\n### Skill: {skill_name}")
                if system_prompt:
                    skill_parts.append(system_prompt)
                if response_guidelines:
                    skill_parts.append(response_guidelines)
        
        # Only return skills section if we added any skills
        return "\n\n".join(skill_parts) if len(skill_parts) > 1 else ""
    
    def _build_tone_section(self, context: AgentContext) -> str:
        """
        Build Tone & Style section from user profile for personalization.
        
        Enhanced with distinct personality archetypes, unique opening styles,
        and hard constraints for each age group.
        
        Args:
            context: AgentContext with user profile
        
        Returns:
            Formatted tone section with age-aware guidance
        """
        # Get user_profile from context (may be dict or None)
        user_profile = getattr(context, 'user_profile', None)
        
        # Get ToneProfile from user profile
        tone_profile = ToneProfileManager.from_user_profile(user_profile)
        
        # Build tone section lines
        tone_section_lines = []
        
        tone_section_lines.append("### Tone & Style (auto-generated from user profile)")
        tone_section_lines.append(f"- Age group: {tone_profile.age_group or 'unknown'}")
        
        # Age-specific personality and constraints
        if tone_profile.age_group == "child":
            tone_section_lines.extend([
                "",
                "**PERSONALITY: Excited, caring friend (like a fun older sibling)**",
                "",
                "🚨 CRITICAL RULES FOR CHILDREN (6-10yo) - MUST OBEY:",
                "- ⚠️ MAXIMUM 2 SENTENCES ONLY! No more!",
                "- BANNED opening words: 嘩 噢 唉 嗯 💪 - NEVER start with these!",
                "- BANNED words: 壓力 焦慮 認知 情緒管理",
                "- USE instead: 擔心 辛苦 難受",
                "- For math problems: ASK what specific topic, don't assume!",
                "  - If user says specific topic (幾何), use their word",
                "  - If user just says 'math hard', ask: '係咪加減乘除、九因歌、定係應用題呀？'",
                "- Emojis at END only, never at start",
                "",
                "✅ CORRECT: '數學難係好正常㗎！係咪加減乘除定係應用題呀？'",
                "❌ WRONG: '嘩，小明！聽你講數學好難。係咪幾何嗰啲？' (don't assume topic)",
            ])
        
        elif tone_profile.age_group == "teen":
            tone_section_lines.extend([
                "",
                "**PERSONALITY: Chill, relatable peer (not a teacher or parent)**",
                "",
                "HARD CONSTRAINTS (you MUST follow these):",
                "- Maximum 4-5 sentences. Be concise.",
                "- Use casual language: 'totally', 'honestly', 'like', 'kinda', 'ngl'",
                "- 0-1 emoji only. Too many looks cringe.",
                "- NO lecturing or listing '5 tips'. Max 1-2 suggestions.",
                "- NO phrases like 'It sounds like...' or 'Many teens feel...'",
                "",
                "OPENING STYLE:",
                "- Start directly with validation.",
                "- NO filler words like 'Ugh', 'Oh', 'So'.",
                "- Validate without being preachy: 'Yeah, [problem] sucks.'",
                "",
                "VOICE EXAMPLES:",
                "✓ GOOD: 'Ugh, exam stress is the worst. Your brain just won't cooperate, right? Wanna try a quick focus trick?'",
                "✗ BAD: 'I understand you're struggling with concentration. Here are some evidence-based study techniques...'",
                "",
                "- Offer help casually: 'Wanna try...?' / 'No pressure, but...'",
            ])
        
        elif tone_profile.age_group == "adult":
            tone_section_lines.extend([
                "",
                "**PERSONALITY: Professional wellness coach (warm but structured)**",
                "",
                "CONSTRAINTS:",
                f"- Maximum {tone_profile.max_sentences} sentences, {tone_profile.max_bullets} bullet points.",
                "- Use clear, action-oriented language.",
                "- Maximum 1 emoji (optional, at end only).",
                "- Bullet points are appropriate for listing options.",
                "",
                "OPENING STYLE (vary these):",
                "- Start with brief reflection, then move to practical advice",
                "- Avoid: 'It sounds like...' - instead use 'I hear that...' / 'So...' / direct acknowledgment",
                "",
                "STRUCTURE:",
                "1) Brief reflection (1-2 sentences)",
                "2) Simple explanation if relevant (1-2 sentences)",
                "3) 1-3 concrete options or next steps",
                "4) Optional check-in question",
            ])
        
        elif tone_profile.age_group == "elder":
            tone_section_lines.extend([
                "",
                "**PERSONALITY: Respectful, patient companion (like a caring neighbor)**",
                "",
                "HARD CONSTRAINTS (you MUST follow these):",
                f"- Maximum {tone_profile.max_sentences} sentences. Be clear, not wordy.",
                "- NO slang, jargon, or abbreviations.",
                "- NO trendy phrases or idioms they might not know.",
                "- Use respectful, slightly formal tone.",
                "- Maximum 1 emoji (hearts or simple ones only: 💙 ✨).",
                "",
                "OPENING STYLE:",
                "- Warm, respectful: '你好！' / 'Hello!' + direct acknowledgment",
                "- Avoid casual openers like 'Hey there!'",
                "",
                "VOICE EXAMPLES:",
                "✓ GOOD: '聽到你膝頭唔舒服，真係辛苦。我哋一齊諗下有咩方法可以幫到你。'",
                "✗ BAD: 'OMG that sounds tough! Here are some hacks...'",
                "",
                "- Give clear, numbered steps when offering advice.",
                "- Always include reassurance and offer to explain more.",
            ])
        
        else:
            # Unknown/default - use neutral adult-like guidance
            tone_section_lines.extend([
                f"- Write at a {tone_profile.formality} level with {tone_profile.explanation_depth} explanations.",
                f"- Maximum {tone_profile.max_sentences} sentences and {tone_profile.max_bullets} bullet points.",
            ])
        
        # Add display name if available
        user_name = None
        if user_profile:
            if hasattr(user_profile, 'display_name'):
                user_name = user_profile.display_name
            elif isinstance(user_profile, dict):
                user_name = user_profile.get('display_name') or user_profile.get('name')
        
        if user_name:
            tone_section_lines.append(
                f"\n- The user's name is '{user_name}'. Use it naturally (1-2 times max)."
            )
        
        return "\n".join(tone_section_lines)
    
    def _build_interaction_pattern_section(self, context: AgentContext) -> str:
        """
        Build age-aware interaction pattern section.
        
        Provides micro conversation flow guidance based on user age group.
        Complements the Tone & Style section with structural guidance.
        
        Args:
            context: AgentContext with user profile
        
        Returns:
            Formatted interaction pattern section
        """
        user_profile = getattr(context, 'user_profile', None)
        tone_profile = ToneProfileManager.from_user_profile(user_profile)
        age_group = tone_profile.age_group or "adult"  # Default to adult
        
        lines = ["### Interaction Flow"]
        lines.append("")
        
        if age_group == "child":
            lines.append("Flow for CHILD (6-10yo):")
            lines.append("1) Direct response to feeling (NO filler words like 嘩/噢)")
            lines.append("2) ONE simple question")
            lines.append("")
            lines.append("⚠️ TOTAL: 2 sentences MAXIMUM. Delete extra sentences!")
        
        elif age_group == "teen":
            lines.append("Flow for TEEN:")
            lines.append("1) Quick validation (no 'many people feel...' - just acknowledge)")
            lines.append("2) ONE practical idea, offered casually")
            lines.append("3) Optional: 'Wanna try?' / 'No pressure'")
            lines.append("")
            lines.append("⚠️ Be their peer, not their teacher. Max 4-5 sentences.")
        
        elif age_group == "adult":
            lines.append("Flow for ADULT:")
            lines.append("1) Brief acknowledgment (1 sentence)")
            lines.append("2) Context/explanation if helpful (1-2 sentences)")
            lines.append("3) Options as bullet points (1-3 items)")
            lines.append("4) Check-in question (optional)")
        
        elif age_group == "elder":
            lines.append("Flow for ELDER:")
            lines.append("1) Respectful acknowledgment")
            lines.append("2) Clear, numbered steps if giving advice")
            lines.append("3) Reassurance and offer to explain more")
            lines.append("")
            lines.append("⚠️ Be patient and clear. Avoid slang.")
        
        else:
            lines.append("1) Acknowledge what they shared")
            lines.append("2) Provide helpful information")
            lines.append("3) Offer next steps")
        
        lines.append("")
        lines.append("Use only information from THIS conversation session.")
        
        return "\n".join(lines)
    
    def _build_tool_usage_section(
        self,
        agent_name: str,
        active_skills: Optional[List[str]],
    ) -> str:
        """
        Build tool usage guidance based on agent and active skills.
        
        Explains how to use and talk about tool/skill outputs.
        
        Args:
            agent_name: Agent identifier (e.g., "smartkidpath_screener")
            active_skills: List of active skill names
        
        Returns:
            Formatted tool usage section, or empty string if not applicable
        """
        if not active_skills:
            return ""
        
        lines = ["### Tool usage"]
        lines.append("")
        
        # OmniCare + motor_screening specific guidance
        if agent_name == "smartkidpath_screener" and "motor_screening" in active_skills:
            lines.append("**Motor screening tool guidance:**")
            lines.append("- If a video or description is provided, consider using the movement analysis tool.")
            lines.append("- If the information is too vague (e.g. video too short, lighting poor, child's body not fully visible), explain what kind of description or video would help before giving conclusions.")
            lines.append("- When presenting results, use non-diagnostic language:")
            lines.append("  - Say 'screening observations' or 'areas to monitor', NOT 'diagnosis' or 'condition'.")
            lines.append("  - Suggest 'watch at home and note changes' or 'consider asking a professional' as appropriate.")
            lines.append("- Never treat tool outputs as a diagnosis. Always frame them as screening observations and suggestions for what to pay attention to.")
            lines.append("")
        
        # Live2D + mental_health skill
        if "mental_health" in active_skills:
            lines.append("**Mental health skill guidance:**")
            lines.append("- Structure emotional support suggestions clearly.")
            lines.append("- Validate feelings before offering coping strategies.")
            lines.append("- If distress seems severe, gently suggest professional support.")
            lines.append("")
        
        # Live2D + sleep_support skill
        if "sleep_support" in active_skills:
            lines.append("**Sleep support skill guidance:**")
            lines.append("- Present sleep hygiene tips in a clear, actionable list.")
            lines.append("- Ask about their current sleep routine before suggesting changes.")
            lines.append("- If sleep issues seem severe or persistent, suggest consulting a doctor.")
            lines.append("")
        
        # Only return if we added skill-specific content
        if len(lines) <= 2:
            return ""
        
        return "\n".join(lines)
    
    def _build_context_section(self, context: AgentContext) -> str:
        """
        Build context section from AgentContext (high-level, no PII).
        
        Includes both user profile context and age-aware conversation summary.
        
        Args:
            context: AgentContext with user profile and cultural context
        
        Returns:
            Formatted context section
        """
        from src.core.context_packager import build_session_context_summary
        
        context_parts = ["=== User Context ==="]
        
        # Check for health_profile (new teen/kids profile system)
        health_profile = getattr(context, 'health_profile', None)
        if health_profile:
            context_parts.append(self._build_health_profile_context(health_profile, context))
        
        # Age group
        user_profile = getattr(context, 'user_profile', {})
        if user_profile:
            age_group = user_profile.get('age_group') if isinstance(user_profile, dict) else getattr(user_profile, 'age_group', None)
            if age_group:
                context_parts.append(f"Age Group: {age_group}")
            
            # Chronic conditions (if any, high-level only)
            if isinstance(user_profile, dict):
                health_conditions = user_profile.get('health_conditions', [])
            else:
                health_conditions = getattr(user_profile, 'health_conditions', [])
            if health_conditions and isinstance(health_conditions, list):
                conditions_str = ", ".join(health_conditions[:3])  # Limit to first 3
                context_parts.append(f"Health Considerations: {conditions_str}")
        
        # Cultural context (region)
        cultural_context = getattr(context, 'cultural_context', {})
        if cultural_context:
            region = cultural_context.get('region')
            if region:
                context_parts.append(f"Region: {region}")
        
        # Add conversation context summary if history is available
        conversation_history = getattr(context, 'conversation_history', [])
        if conversation_history:
            user_profile_dict = user_profile if isinstance(user_profile, dict) else None
            if user_profile_dict is None and user_profile:
                # Convert UserProfile to dict for context packager
                user_profile_dict = {
                    'display_name': getattr(user_profile, 'display_name', None),
                    'age': getattr(user_profile, 'age', None),
                    'age_group': getattr(user_profile, 'age_group', None),
                }
            
            context_summary = build_session_context_summary(
                conversation_history=conversation_history,
                user_profile=user_profile_dict,
            )
            if context_summary:
                context_parts.append("")  # Blank line before summary
                context_parts.append(context_summary)
        
        # Only return context section if we added any context
        return "\n".join(context_parts) if len(context_parts) > 1 else ""
    
    def _build_conversation_memory_section(self, context: AgentContext) -> str:
        """
        Build conversation memory section from persistent history.
        
        This enables the AI to "remember" past conversations with the user.
        
        Args:
            context: AgentContext containing persistent_conversation_history from database
        
        Returns:
            Formatted memory section for the AI prompt
        """
        # Check for persistent conversation history (distinct from in-session history)
        conversation_history = getattr(context, 'persistent_conversation_history', None)
        
        # Fallback: check if it was passed as conversation_history
        if not conversation_history:
            # Get in-session history only if it has meaningful content
            in_session = getattr(context, 'conversation_history', [])
            # Don't use in-session if it only has the current message
            if in_session and len(in_session) > 1:
                conversation_history = in_session
        
        if not conversation_history:
            return ""
        
        # Build memory section
        memory_lines = [
            "## CONVERSATION MEMORY",
            "You have had previous conversations with this user. Here is a summary of your recent discussions:",
            ""
        ]
        
        # Format each past message (limit to last 10 for token efficiency)
        for msg in conversation_history[-10:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            
            # Truncate very long messages
            if len(content) > 200:
                content = content[:200] + "..."
            
            if role == 'user':
                memory_lines.append(f"- **User said**: \"{content}\"")
            elif role == 'assistant':
                memory_lines.append(f"- **You replied**: \"{content}\"")
        
        memory_lines.extend([
            "",
            "**Important**: Use this context to maintain continuity. Reference previous topics when relevant.",
            "If the user asks about something you discussed before, acknowledge it and build on that conversation."
        ])
        
        logger.info(f"🧠 Added {len(conversation_history)} messages to AI memory section")
        
        return "\n".join(memory_lines)
    
    def _build_final_enforcement_section(self, context: AgentContext) -> str:
        """
        Build final enforcement section with critical rules reminder.
        
        This section appears at the END of the prompt to ensure the AI
        follows critical rules (LLMs tend to follow later instructions more).
        
        Args:
            context: AgentContext with user profile
        
        Returns:
            Formatted final enforcement section
        """
        user_profile = getattr(context, 'user_profile', None)
        tone_profile = ToneProfileManager.from_user_profile(user_profile)
        age_group = tone_profile.age_group
        
        lines = []
        
        # Add response variety rules for ALL age groups
        lines.extend([
            "=" * 60,
            "🔄 RESPONSE VARIETY RULES (ALL AGES) 🔄",
            "=" * 60,
            "",
            "RULE: NO CONSECUTIVE SAME OPENINGS!",
            "",
            "🚫 BANNED consecutive patterns:",
            "- Do NOT start 2 responses in a row with '聽到你...'",
            "- Do NOT start 2 responses in a row with '✨'",
            "- Do NOT start 2 responses in a row with '💪'",
            "- Do NOT use the same sentence structure twice in a row",
            "",
            "✅ ROTATE between these opening styles:",
            "1. Direct response: '真係辛苦...' '明白你...' '咁樣好難受...'",
            "2. Follow-up question: '發生咩事呀？' '點解會咁？' '然後點呀？'",
            "3. Empathy: '換著係我都會咁覺得' '呢種感覺好正常'",
            "4. Short acknowledgment: '係呀' '嗯嗯' '原來係咁'",
            "",
            "ASK YOURSELF: 'What did I start with last time?' → Use DIFFERENT style this time!",
            "",
        ])
        
        # Add child-specific enforcement
        if age_group == "child":
            lines.extend([
                "=" * 60,
                "🚨🚨🚨 MANDATORY RULES FOR CHILD (6-10yo) - MUST OBEY 🚨🚨🚨",
                "=" * 60,
                "",
                "RULE 1 - SENTENCE LIMIT (MOST IMPORTANT!):",
                "Your response MUST have EXACTLY 2 sentences or less.",
                "Count: How many 。？！ are there? If more than 2, DELETE until only 2 remain!",
                "",
                "RULE 2 - BANNED FIRST CHARACTERS:",
                "Your response MUST NOT start with: 嘩 噢 唉 嗯 💪",
                "If your first character is any of these, DELETE IT and rewrite!",
                "",
                "RULE 3 - BANNED WORDS:",
                "NEVER use: 壓力 焦慮 認知 情緒管理",
                "USE instead: 擔心 辛苦 難受",
                "",
                "RULE 4 - DON'T ASSUME TOPICS:",
                "If user says 'math is hard' without specifics, ASK what part:",
                "- '係咪加減乘除、九因歌、定係應用題呀？'",
                "If user mentions a specific topic (like 幾何), use THEIR word.",
                "",
                "✅ CORRECT: 「數學難係好正常㗎！係咪加減乘除定係應用題呀？」",
                "(2 sentences, asks specific topic, no assumptions)",
                "",
                "❌ WRONG: 「嘩，小明！聽你講數學好難。係咪幾何嗰啲？我哋一齊睇下！」",
                "(starts with 嘩, assumes topic, 4 sentences)",
                "",
            ])
        
        lines.extend([
            "=" * 60,
            "BEFORE SENDING: Re-read your response and FIX any violations!",
            "=" * 60,
        ])
        
        return "\n".join(lines)


    def _build_health_profile_context(self, health_profile: Any, context: AgentContext) -> str:
        """
        Build context from HealthProfile for AI personalization.
        
        Uses the profile extraction service to assess completeness
        and provide guidance for profile building through conversation.
        
        Args:
            health_profile: HealthProfile instance
            context: AgentContext
            
        Returns:
            Formatted health profile context string
        """
        from src.services.profile_extraction_service import get_profile_extraction_service
        
        profile_service = get_profile_extraction_service()
        completeness = profile_service.assess_profile_completeness(health_profile)
        
        # Build context using the service
        profile_context = profile_service.build_profile_context_for_ai(health_profile, completeness)
        
        return profile_context


# Singleton instance
_prompt_composer: Optional[PromptComposer] = None


def get_prompt_composer() -> PromptComposer:
    """
    Get the singleton PromptComposer instance.
    
    Returns:
        Shared PromptComposer instance
    """
    global _prompt_composer
    if _prompt_composer is None:
        _prompt_composer = PromptComposer()
    return _prompt_composer




