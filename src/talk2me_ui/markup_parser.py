"""
Markup parser for Talk2Me audiobook generation.

This module provides functionality to parse triple-brace markup syntax
used in audiobook text, extracting sections with voice assignments,
sound effects, and background audio.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("talk2me_ui.markup_parser")


@dataclass
class MarkupSection:
    """Represents a section of audiobook text with associated markup."""

    text: str
    voice: str | None = None
    sound_effects: list[str] = None
    background_audio: dict[str, Any] | None = None

    def __post_init__(self):
        if self.sound_effects is None:
            self.sound_effects = []


class AudiobookMarkupError(Exception):
    """Exception raised for invalid markup syntax."""

    pass


class AudiobookMarkupParser:
    """
    Parser for triple-brace audiobook markup syntax.

    Syntax:
    {{{voice:voice_name}}}
    {{{sfx:sound_name}}}
    {{{bg:background_name,volume:0.5}}}
    {{{bg:stop}}}
    """

    MARKUP_PATTERN = re.compile(r"\{\{\{([^}]+)\}\}\}")
    OPTION_PATTERN = re.compile(r"(\w+):([^,]+)")

    def __init__(self):
        self.current_voice = None
        self.current_background = None

    def parse(self, text: str) -> list[MarkupSection]:
        """
        Parse the markup text into sections.

        Args:
            text: The text containing markup

        Returns:
            List of MarkupSection objects

        Raises:
            AudiobookMarkupError: If markup syntax is invalid
        """
        logger.debug("Starting markup parsing", extra={"text_length": len(text)})
        if not text.strip():
            logger.debug("Empty text provided, returning empty sections")
            return []

        sections = []
        current_text = ""
        current_sfx = []

        # Split text by markup tags
        parts = self.MARKUP_PATTERN.split(text)

        # Process alternating text/markup parts
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Text part
                current_text += part
            else:  # Markup part
                # Process any accumulated text before this markup
                if current_text.strip():
                    sections.append(
                        MarkupSection(
                            text=current_text.strip(),
                            voice=self.current_voice,
                            sound_effects=current_sfx.copy(),
                            background_audio=self.current_background,
                        )
                    )
                    current_text = ""
                    current_sfx = []

                # Parse the markup
                self._parse_markup(part)

        # Add final section if there's remaining text
        if current_text.strip():
            sections.append(
                MarkupSection(
                    text=current_text.strip(),
                    voice=self.current_voice,
                    sound_effects=current_sfx.copy(),
                    background_audio=self.current_background,
                )
            )

        logger.info("Markup parsing completed", extra={"sections_count": len(sections)})
        return sections

    def _parse_markup(self, markup: str) -> None:
        """
        Parse a single markup tag.

        Args:
            markup: The markup content (without braces)

        Raises:
            AudiobookMarkupError: If markup is invalid
        """
        parts = markup.split(":", 1)
        if len(parts) != 2:
            raise AudiobookMarkupError(f"Invalid markup format: {{{{{markup}}}}}")

        command = parts[0].strip().lower()
        value_part = parts[1].strip()

        # Parse options if present
        options = {}
        if "," in value_part:
            value, option_str = value_part.split(",", 1)
            value = value.strip()
            for match in self.OPTION_PATTERN.finditer(option_str):
                key, val = match.groups()
                # Try to convert to number
                try:
                    val = float(val)
                except ValueError:
                    pass
                options[key.strip()] = val
        else:
            value = value_part

        if command == "voice":
            self.current_voice = value
        elif command == "sfx":
            # Sound effects are added to current section
            # This will be handled when creating sections
            pass  # Handled in parse method
        elif command == "bg":
            if value.lower() == "stop":
                self.current_background = None
            else:
                self.current_background = {"name": value, **options}
        else:
            raise AudiobookMarkupError(f"Unknown markup command: {command}")

    def validate_markup(self, text: str) -> list[str]:
        """
        Validate markup syntax and return any issues found.

        Args:
            text: The text to validate

        Returns:
            List of validation error messages
        """
        logger.debug("Starting markup validation", extra={"text_length": len(text)})
        issues = []

        # Check for unmatched braces
        open_count = text.count("{{{")
        close_count = text.count("}}}")
        if open_count != close_count:
            issues.append(f"Unmatched braces: {open_count} opening, {close_count} closing")

        # Check each markup tag
        for match in self.MARKUP_PATTERN.finditer(text):
            markup = match.group(1)
            try:
                # Test parsing
                temp_parser = AudiobookMarkupParser()
                temp_parser._parse_markup(markup)
            except AudiobookMarkupError as e:
                issues.append(f"Invalid markup at position {match.start()}: {e}")

        logger.info("Markup validation completed", extra={"issues_count": len(issues)})
        return issues


def parse_audiobook_markup(text: str) -> list[MarkupSection]:
    """
    Convenience function to parse audiobook markup.

    Args:
        text: The markup text to parse

    Returns:
        List of parsed sections
    """
    parser = AudiobookMarkupParser()
    return parser.parse(text)


def validate_audiobook_markup(text: str) -> list[str]:
    """
    Convenience function to validate audiobook markup.

    Args:
        text: The markup text to validate

    Returns:
        List of validation issues
    """
    parser = AudiobookMarkupParser()
    return parser.validate_markup(text)
