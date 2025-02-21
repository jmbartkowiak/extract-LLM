"""
placeholder_matcher.py
2/17/2025
v8.0.1

This module handles the extraction and pairing of placeholders in resume templates.
Key features:

1. Placeholder Detection:
   - Extracts skill placeholders (<SKILL N>)
   - Validates placeholder structure
   - Supports template validation

2. Content Pairing:
   - Pairs skills by length for balanced layout
   - Optimizes visual presentation
   - Maintains placeholder ordering

3. Error Handling:
   - Validates input text
   - Provides detailed error messages
   - Maintains comprehensive logging
"""

import re
from typing import Dict, List, Tuple, Optional, Pattern, Match
from dataclasses import dataclass
from functools import lru_cache

from logging_manager import log_process

# Type aliases
PlaceholderDict = Dict[int, str]
SkillPair = Tuple[str, str, str, str]  # (placeholder1, skill1, placeholder2, skill2)

class PlaceholderError(Exception):
    """Custom exception for placeholder-related errors"""
    pass

@dataclass
class PlaceholderMatch:
    """Container for placeholder match data"""
    number: int
    placeholder: str
    start: int
    end: int

class PlaceholderMatcher:
    """Handles placeholder extraction and pairing"""
    
    # Cached regex patterns
    SKILL_PATTERN: Pattern = re.compile(r"<SKILL\s*(\d+)>")
    OVERVIEW_PATTERN: Pattern = re.compile(r"<OverView>")
    BULLET_PATTERN: Pattern = re.compile(
        r"<Experience-Bullet(\d+)-(BoldedOverview|Description)-J(\d+)>"
    )
    
    @classmethod
    def validate_text(cls, text: str) -> None:
        """
        Validates input text format.
        
        Args:
            text: Input text to validate
            
        Raises:
            PlaceholderError: If text is invalid
        """
        if not text:
            raise PlaceholderError("Empty text provided")
        if not isinstance(text, str):
            raise PlaceholderError(f"Expected string, got {type(text)}")

    @classmethod
    def extract_skill_placeholders(cls, text: str) -> PlaceholderDict:
        """
        Extracts skill placeholders from text.
        
        Args:
            text: Text containing placeholders
            
        Returns:
            Dict[int, str]: Mapping of skill numbers to placeholders
            
        Raises:
            PlaceholderError: If extraction fails
        """
        try:
            cls.validate_text(text)
            
            placeholders: PlaceholderDict = {}
            for match in cls.SKILL_PATTERN.finditer(text):
                try:
                    num = int(match.group(1))
                    if 1 <= num <= 10:
                        placeholders[num] = match.group(0)
                except ValueError:
                    continue  # Skip invalid numbers
                    
            log_process(
                f"Extracted {len(placeholders)} skill placeholders",
                "DEBUG"
            )
            return placeholders
            
        except Exception as e:
            error_msg = f"Failed to extract skill placeholders: {str(e)}"
            log_process(error_msg, "ERROR")
            raise PlaceholderError(error_msg)

    @classmethod
    def pair_skills_by_length(
        cls,
        skills_dict: PlaceholderDict,
        skills_texts: Dict[int, str]
    ) -> List[SkillPair]:
        """
        Pairs skills by length for balanced layout.
        
        Args:
            skills_dict: Mapping of skill numbers to placeholders
            skills_texts: Mapping of skill numbers to skill text
            
        Returns:
            List[SkillPair]: Paired skills and placeholders
            
        Raises:
            PlaceholderError: If pairing fails
        """
        try:
            # Create list of (number, text, placeholder) tuples
            skills_list = [
                (num, skills_texts.get(num, ""), skills_dict[num])
                for num in sorted(skills_dict.keys())
            ]
            
            # Sort by text length
            sorted_skills = sorted(
                skills_list,
                key=lambda x: len(x[1]),
                reverse=True
            )
            
            # Pair longest with shortest
            pairs: List[SkillPair] = []
            n = len(sorted_skills)
            for i in range(n // 2):
                first = sorted_skills[i]
                last = sorted_skills[n - 1 - i]
                pairs.append((
                    first[2],   # First placeholder
                    first[1],   # First skill text
                    last[2],    # Last placeholder
                    last[1]     # Last skill text
                ))
                
            log_process(
                f"Created {len(pairs)} skill pairs",
                "DEBUG"
            )
            return pairs
            
        except Exception as e:
            error_msg = f"Failed to pair skills: {str(e)}"
            log_process(error_msg, "ERROR")
            raise PlaceholderError(error_msg)

    @classmethod
    def match_and_pair_skills(
        cls,
        template_text: str,
        skills_texts: Dict[int, str]
    ) -> Optional[List[SkillPair]]:
        """
        Extracts and pairs skills from template text.
        
        Args:
            template_text: Template containing placeholders
            skills_texts: Mapping of skill numbers to skill text
            
        Returns:
            Optional[List[SkillPair]]: Paired skills if successful
            
        Raises:
            PlaceholderError: If matching fails
        """
        try:
            cls.validate_text(template_text)
            
            placeholders = cls.extract_skill_placeholders(template_text)
            if len(placeholders) != 10:
                raise PlaceholderError(
                    f"Expected 10 skill placeholders, found {len(placeholders)}"
                )
                
            return cls.pair_skills_by_length(placeholders, skills_texts)
            
        except Exception as e:
            error_msg = f"Failed to match and pair skills: {str(e)}"
            log_process(error_msg, "ERROR")
            raise PlaceholderError(error_msg)

    @classmethod
    @lru_cache(maxsize=32)
    def validate_template(cls, template_text: str) -> bool:
        """
        Validates template structure.
        
        Args:
            template_text: Template to validate
            
        Returns:
            bool: True if template is valid
            
        Raises:
            PlaceholderError: If validation fails
        """
        try:
            cls.validate_text(template_text)
            
            # Check for required placeholders
            if not cls.OVERVIEW_PATTERN.search(template_text):
                raise PlaceholderError("Missing overview placeholder")
                
            skill_placeholders = cls.extract_skill_placeholders(template_text)
            if len(skill_placeholders) != 10:
                raise PlaceholderError(
                    f"Expected 10 skill placeholders, found {len(skill_placeholders)}"
                )
                
            # Check bullet point placeholders
            bullet_matches = list(cls.BULLET_PATTERN.finditer(template_text))
            if not bullet_matches:
                raise PlaceholderError("Missing bullet point placeholders")
                
            return True
            
        except Exception as e:
            error_msg = f"Template validation failed: {str(e)}"
            log_process(error_msg, "ERROR")
            return False

if __name__ == "__main__":
    # Example usage
    try:
        template = """
        <OverView>
        Skills:
        <SKILL 1>  <SKILL 2>
        <SKILL 3>  <SKILL 4>
        <SKILL 5>  <SKILL 6>
        <SKILL 7>  <SKILL 8>
        <SKILL 9>  <SKILL 10>
        
        Experience:
        <Experience-Bullet1-BoldedOverview-J1>: <Experience-Bullet1-Description-J1>
        """
        
        skills = {
            1: "Python Development",
            2: "TypeScript",
            3: "Cloud Architecture",
            4: "DevOps",
            5: "System Design",
            6: "API Design",
            7: "TDD",
            8: "Git",
            9: "SQL",
            10: "CI/CD"
        }
        
        if PlaceholderMatcher.validate_template(template):
            pairs = PlaceholderMatcher.match_and_pair_skills(template, skills)
            print("Skill pairs:", pairs)
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
