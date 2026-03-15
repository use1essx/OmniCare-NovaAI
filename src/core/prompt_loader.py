"""
Prompt Loader Utility

Loads prompt templates from the /prompts directory.
This allows prompts to be managed separately from code for:
- Easier prompt iteration and testing
- Better version control of prompts
- Ability to modify prompts without code changes
- Cleaner, more maintainable code

Usage:
    from src.core.prompt_loader import PromptLoader
    
    loader = PromptLoader()
    prompt = loader.load("skills/mental_health/system_prompt")
    # or
    prompt = loader.load_skill_prompt("mental_health", "system_prompt")
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Loads prompt templates from the prompts directory.
    
    Prompts are cached for performance.
    """
    
    # Base prompts directory (relative to project root)
    DEFAULT_PROMPTS_DIR = "prompts"
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize prompt loader.
        
        Args:
            prompts_dir: Optional custom prompts directory path
        """
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # Find project root (look for prompts directory)
            self.prompts_dir = self._find_prompts_dir()
        
        self._cache: Dict[str, str] = {}
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")
    
    def _find_prompts_dir(self) -> Path:
        """Find the prompts directory relative to this file."""
        # Start from this file's location and go up
        current = Path(__file__).resolve()
        
        # Try common locations
        possible_paths = [
            current.parent.parent.parent / "prompts",  # src/core -> prompts
            current.parent.parent.parent.parent / "prompts",  # deeper nesting
            Path("/workspaces/fyp2526-use1essx/healthcare_ai_live2d_unified/prompts"),
            Path("prompts"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Fallback to relative path
        return Path(self.DEFAULT_PROMPTS_DIR)
    
    def load(self, prompt_path: str, default: str = "") -> str:
        """
        Load a prompt from file.
        
        Args:
            prompt_path: Relative path to prompt file (without extension)
                        e.g., "skills/mental_health/system_prompt"
            default: Default value if prompt not found
            
        Returns:
            Prompt content as string
        """
        # Check cache first
        if prompt_path in self._cache:
            return self._cache[prompt_path]
        
        # Try loading from file
        full_path = self.prompts_dir / f"{prompt_path}.txt"
        
        if not full_path.exists():
            # Try with .md extension
            full_path = self.prompts_dir / f"{prompt_path}.md"
        
        # For language-specific files, try lowercase variant (e.g., zh-HK -> zh-hk)
        if not full_path.exists() and "/" in prompt_path:
            # Split path and try lowercase on the last part (language code)
            parts = prompt_path.split("/")
            if len(parts) >= 2:
                parts[-1] = parts[-1].lower()
                lowercase_path = "/".join(parts)
                full_path = self.prompts_dir / f"{lowercase_path}.txt"
                if not full_path.exists():
                    full_path = self.prompts_dir / f"{lowercase_path}.md"
        
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8").strip()
                self._cache[prompt_path] = content
                logger.debug(f"Loaded prompt: {prompt_path}")
                return content
            except Exception as e:
                logger.error(f"Error loading prompt {prompt_path}: {e}")
                return default
        else:
            logger.warning(f"Prompt not found: {full_path}")
            return default
    
    def load_skill_prompt(self, skill_name: str, prompt_type: str, default: str = "") -> str:
        """
        Load a skill-specific prompt.
        
        Args:
            skill_name: Name of the skill (e.g., "mental_health", "safety_crisis")
            prompt_type: Type of prompt (e.g., "system_prompt", "response_guidelines")
            default: Default value if not found
            
        Returns:
            Prompt content
        """
        return self.load(f"skills/{skill_name}/{prompt_type}", default)
    
    def load_system_prompt(self, prompt_name: str, default: str = "") -> str:
        """
        Load a system-level prompt.
        
        Args:
            prompt_name: Name of the system prompt
            default: Default value if not found
            
        Returns:
            Prompt content
        """
        return self.load(f"system/{prompt_name}", default)
    
    def load_agent_prompt(self, agent_name: str, prompt_type: str, default: str = "") -> str:
        """
        Load an agent-specific prompt.
        
        Args:
            agent_name: Name of the agent
            prompt_type: Type of prompt
            default: Default value if not found
            
        Returns:
            Prompt content
        """
        return self.load(f"agents/{agent_name}/{prompt_type}", default)
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()
        logger.info("Prompt cache cleared")
    
    def reload(self, prompt_path: str) -> str:
        """
        Reload a prompt, bypassing cache.
        
        Args:
            prompt_path: Path to the prompt
            
        Returns:
            Prompt content
        """
        if prompt_path in self._cache:
            del self._cache[prompt_path]
        return self.load(prompt_path)
    
    def list_prompts(self, directory: str = "") -> list:
        """
        List all available prompts in a directory.
        
        Args:
            directory: Subdirectory to list (empty for root)
            
        Returns:
            List of prompt paths
        """
        search_dir = self.prompts_dir / directory if directory else self.prompts_dir
        
        if not search_dir.exists():
            return []
        
        prompts = []
        for file_path in search_dir.rglob("*.txt"):
            rel_path = file_path.relative_to(self.prompts_dir)
            prompts.append(str(rel_path.with_suffix("")))
        
        for file_path in search_dir.rglob("*.md"):
            rel_path = file_path.relative_to(self.prompts_dir)
            prompts.append(str(rel_path.with_suffix("")))
        
        return sorted(prompts)


# Global singleton instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get or create the global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def load_prompt(prompt_path: str, default: str = "") -> str:
    """
    Convenience function to load a prompt.
    
    Args:
        prompt_path: Path to the prompt
        default: Default value if not found
        
    Returns:
        Prompt content
    """
    return get_prompt_loader().load(prompt_path, default)


def load_skill_prompt(skill_name: str, prompt_type: str, default: str = "") -> str:
    """
    Convenience function to load a skill prompt.
    
    Args:
        skill_name: Skill name
        prompt_type: Prompt type
        default: Default value
        
    Returns:
        Prompt content
    """
    return get_prompt_loader().load_skill_prompt(skill_name, prompt_type, default)

