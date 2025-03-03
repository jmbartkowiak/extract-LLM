# placeholder_matcher.py
# v1.0.3
# 2-27-25

'''
Plan:

    Use regex to extract placeholders for skills (<SKILL N>), overview, and bullet points.
    Validate the template text.
    Optionally pair skills by length.
    Log extraction and any errors.
    
'''



"""
Placeholder Matcher Module

This module handles the extraction and pairing of placeholders from resume templates.
It:
- Detects skill placeholders of the form <SKILL N> (where N is 1–10).
- Validates that required placeholders (e.g., <OverView> and bullet placeholders) exist.
- Can pair skill placeholders with provided skill texts for balanced layout.
- Logs all steps and errors.
"""

import re
from typing import Dict, List, Tuple, Optional, Pattern
from dataclasses import dataclass
from functools import lru_cache

from logging_manager import log_process

# Type alias for a dictionary mapping skill numbers to placeholders.
PlaceholderDict = Dict[int, str]
# Type for pairing two skills.
SkillPair = Tuple[str, str, str, str]  # (placeholder1, skill1, placeholder2, skill2)

class PlaceholderError(Exception):
    """Custom exception for placeholder-related errors."""
    pass

@dataclass
class PlaceholderMatch:
    """
    Data class to store information about a placeholder match.
    """
    number: int
    placeholder: str
    start: int
    end: int

class PlaceholderMatcher:
    """
    Handles extraction and pairing of placeholders from resume templates.
    
    Supported placeholders:
    - <SKILL N> for skills.
    - <OverView> for the overview section.
    - <Experience-BulletN-BoldedOverview-JX> for bullet points.
    """
    SKILL_PATTERN: Pattern = re.compile(r"<SKILL\s*(\d+)>")
    OVERVIEW_PATTERN: Pattern = re.compile(r"<OverView>")
    BULLET_PATTERN: Pattern = re.compile(r"<Experience-Bullet(\d+)-(BoldedOverview|Description)-J(\d+)>")
    
    @classmethod
    def validate_text(cls, text: str) -> None:
        """
        Validates that the provided text is non-empty and is a string.
        """
        if not text:
            raise PlaceholderError("Empty text provided")
        if not isinstance(text, str):
            raise PlaceholderError(f"Expected string, got {type(text)}")
    
    @classmethod
    def extract_skill_placeholders(cls, text: str) -> PlaceholderDict:
        """
        Extracts skill placeholders from the provided text.
        Returns a dictionary mapping skill numbers to the placeholder text.
        """
        cls.validate_text(text)
        placeholders: PlaceholderDict = {}
        for match in cls.SKILL_PATTERN.finditer(text):
            try:
                num = int(match.group(1))
                if 1 <= num <= 10:
                    placeholders[num] = match.group(0)
            except ValueError:
                continue
        log_process(f"Extracted {len(placeholders)} skill placeholders", "DEBUG", module="PlaceholderMatcher")
        return placeholders
    
    @classmethod
    def pair_skills_by_length(cls, skills_dict: PlaceholderDict, skills_texts: Dict[int, str]) -> List[SkillPair]:
        """
        Pairs skills by length to create balanced layout.
        Returns a list of tuples containing paired placeholders and skill texts.
        """
        try:
            skills_list = [
                (num, skills_texts.get(num, ""), skills_dict[num])
                for num in sorted(skills_dict.keys())
            ]
            sorted_skills = sorted(skills_list, key=lambda x: len(x[1]), reverse=True)
            pairs: List[SkillPair] = []
            n = len(sorted_skills)
            for i in range(n // 2):
                first = sorted_skills[i]
                last = sorted_skills[n - 1 - i]
                pairs.append((first[2], first[1], last[2], last[1]))
            log_process(f"Created {len(pairs)} skill pairs", "DEBUG", module="PlaceholderMatcher")
            return pairs
        except Exception as e:
            raise PlaceholderError(f"Failed to pair skills: {e}")
    
    @classmethod
    def match_and_pair_skills(cls, template_text: str, skills_texts: Dict[int, str]) -> Optional[List[SkillPair]]:
        """
        Extracts skill placeholders from the template and pairs them with provided skill texts.
        Ensures exactly 10 skill placeholders are present.
        """
        try:
            cls.validate_text(template_text)
            placeholders = cls.extract_skill_placeholders(template_text)
            if len(placeholders) != 10:
                raise PlaceholderError(f"Expected 10 skill placeholders, found {len(placeholders)}")
            return cls.pair_skills_by_length(placeholders, skills_texts)
        except Exception as e:
            raise PlaceholderError(f"Failed to match and pair skills: {e}")
    
    @classmethod
    @lru_cache(maxsize=32)
    def validate_template(cls, template_text: str) -> bool:
        """
        Validates that the resume template contains all required placeholders.
        Returns True if valid; otherwise, logs the error and returns False.
        """
        try:
            cls.validate_text(template_text)
            if not cls.OVERVIEW_PATTERN.search(template_text):
                raise PlaceholderError("Missing overview placeholder")
            skill_placeholders = cls.extract_skill_placeholders(template_text)
            if len(skill_placeholders) != 10:
                raise PlaceholderError(f"Expected 10 skill placeholders, found {len(skill_placeholders)}")
            bullet_matches = list(cls.BULLET_PATTERN.finditer(template_text))
            if not bullet_matches:
                raise PlaceholderError("Missing bullet point placeholders")
            return True
        except Exception as e:
            log_process(f"Template validation failed: {e}", "ERROR", module="PlaceholderMatcher")
            return False

# End of placeholder_matcher.py
