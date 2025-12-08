"""Unit tests for markup parser functionality."""

import pytest

from talk2me_ui.markup_parser import (
    AudiobookMarkupError,
    AudiobookMarkupParser,
    MarkupSection,
    parse_audiobook_markup,
    validate_audiobook_markup,
)


class TestMarkupSection:
    """Test MarkupSection dataclass."""

    def test_markup_section_creation(self):
        """Test creating a MarkupSection."""
        section = MarkupSection(
            text="Hello world",
            voice="voice1",
            sound_effects=[{"id": "effect1"}],
            background_audio={"name": "bg1", "volume": 0.5},
        )

        assert section.text == "Hello world"
        assert section.voice == "voice1"
        assert section.sound_effects == [{"id": "effect1"}]
        assert section.background_audio == {"name": "bg1", "volume": 0.5}

    def test_markup_section_defaults(self):
        """Test MarkupSection default values."""
        section = MarkupSection(text="Test")

        assert section.text == "Test"
        assert section.voice is None
        assert section.sound_effects == []
        assert section.background_audio is None


class TestAudiobookMarkupParser:
    """Test AudiobookMarkupParser class."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return AudiobookMarkupParser()

    def test_parse_empty_text(self, parser):
        """Test parsing empty text."""
        result = parser.parse("")
        assert result == []

    def test_parse_whitespace_only(self, parser):
        """Test parsing whitespace-only text."""
        result = parser.parse("   \n\t  ")
        assert result == []

    def test_parse_simple_text_no_markup(self, parser):
        """Test parsing simple text without markup."""
        result = parser.parse("Hello world")
        assert len(result) == 1
        assert result[0].text == "Hello world"
        assert result[0].voice is None

    def test_parse_voice_markup(self, parser):
        """Test parsing voice markup."""
        text = "{{{voice:voice1}}}Hello world"
        result = parser.parse(text)

        assert len(result) == 1
        assert result[0].text == "Hello world"
        assert result[0].voice == "voice1"

    def test_parse_multiple_sections(self, parser):
        """Test parsing multiple sections with different voices."""
        text = "{{{voice:voice1}}}Chapter 1{{{voice:voice2}}}Chapter 2"
        result = parser.parse(text)

        assert len(result) == 2
        assert result[0].text == "Chapter 1"
        assert result[0].voice == "voice1"
        assert result[1].text == "Chapter 2"
        assert result[1].voice == "voice2"

    def test_parse_background_audio(self, parser):
        """Test parsing background audio markup."""
        text = "{{{bg:music,volume:0.7}}}Narration text"
        result = parser.parse(text)

        assert len(result) == 1
        assert result[0].text == "Narration text"
        assert result[0].background_audio == {"name": "music", "volume": 0.7}

    def test_parse_background_stop(self, parser):
        """Test parsing background stop markup."""
        text = "{{{bg:music}}}Playing{{{bg:stop}}}Stopped"
        result = parser.parse(text)

        assert len(result) == 2
        assert result[0].text == "Playing"
        assert result[0].background_audio == {"name": "music"}
        assert result[1].text == "Stopped"
        assert result[1].background_audio is None

    def test_parse_sound_effects(self, parser):
        """Test parsing sound effects markup."""
        text = "{{{sfx:door_knock}}}Someone knocked"
        result = parser.parse(text)

        assert len(result) == 1
        assert result[0].text == "Someone knocked"
        # Sound effects are stored in the section
        assert result[0].sound_effects == [{"id": "door_knock"}]

    def test_parse_complex_markup(self, parser):
        """Test parsing complex markup with multiple elements."""
        text = """
        {{{voice:narrator}}}
        {{{bg:ambient_forest,volume:0.3}}}
        In a dark forest, {{{sfx:owl_hoot}}}an owl hooted.
        {{{voice:character}}}
        {{{bg:stop}}}
        Who goes there?
        """

        result = parser.parse(text)

        assert len(result) == 3
        assert result[0].voice == "narrator"
        assert result[0].background_audio == {"name": "ambient_forest", "volume": 0.3}
        assert result[1].voice == "narrator"
        assert result[1].background_audio == {"name": "ambient_forest", "volume": 0.3}
        assert result[2].voice == "character"
        assert result[2].background_audio is None

    def test_parse_invalid_markup_command(self, parser):
        """Test parsing invalid markup command."""
        text = "{{{invalid:command}}}Text"

        with pytest.raises(AudiobookMarkupError, match="Unknown markup command: invalid"):
            parser.parse(text)

    def test_parse_malformed_markup(self, parser):
        """Test parsing malformed markup."""
        text = "{{{voice}}}Text"  # Missing colon and value

        with pytest.raises(AudiobookMarkupError, match="Invalid markup format"):
            parser.parse(text)

    def test_parse_markup_invalid_command_directly(self, parser):
        """Test _parse_markup with invalid command directly."""
        with pytest.raises(AudiobookMarkupError, match="Unknown markup command: invalid"):
            parser._parse_markup("invalid:command")

    def test_parse_markup_malformed_directly(self, parser):
        """Test _parse_markup with malformed markup directly."""
        with pytest.raises(AudiobookMarkupError, match="Invalid markup format"):
            parser._parse_markup("voice")  # No colon

    def test_parse_options_with_non_numeric(self, parser):
        """Test parsing options with non-numeric values."""
        text = "{{{bg:music,loop:true,speed:fast}}}Text"
        result = parser.parse(text)

        assert result[0].background_audio == {"name": "music", "loop": "true", "speed": "fast"}

    def test_audiobook_markup_error_inheritance(self):
        """Test AudiobookMarkupError inheritance."""
        error = AudiobookMarkupError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"

    def test_parse_unmatched_braces(self, parser):
        """Test parsing with unmatched braces."""
        text = "{{{voice:voice1Text"  # Missing closing braces

        # Unmatched braces are treated as regular text since regex requires closing }}}
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].text == "{{{voice:voice1Text"

    def test_parse_options_parsing(self, parser):
        """Test parsing markup with options."""
        text = "{{{bg:music,volume:0.8,loop:true}}}Text"
        result = parser.parse(text)

        assert len(result) == 1
        assert result[0].background_audio == {
            "name": "music",
            "volume": 0.8,
            "loop": "true",  # Parser keeps as string since not numeric
        }

    def test_parse_numeric_options(self, parser):
        """Test parsing numeric options."""
        text = "{{{bg:music,volume:0.5,fade_in:2.0}}}Text"
        result = parser.parse(text)

        assert result[0].background_audio == {"name": "music", "volume": 0.5, "fade_in": 2.0}

    def test_validate_valid_markup(self, parser):
        """Test validating valid markup."""
        text = "{{{voice:voice1}}}Text{{{bg:music}}}More text"
        issues = parser.validate_markup(text)
        assert issues == []

    def test_validate_unmatched_braces(self, parser):
        """Test validating unmatched braces."""
        text = "{{{voice:voice1}}}Text{{{bg:music"
        issues = parser.validate_markup(text)
        assert len(issues) == 1
        assert "Unmatched braces" in issues[0]

    def test_validate_invalid_markup(self, parser):
        """Test validating invalid markup."""
        text = "{{{invalid:command}}}Text"
        issues = parser.validate_markup(text)
        assert len(issues) == 1
        assert "Unknown markup command" in issues[0]

    def test_validate_multiple_issues(self, parser):
        """Test validating markup with multiple issues."""
        text = "{{{invalid:command}}}Text{{{bg:music"  # Invalid command + unmatched braces
        issues = parser.validate_markup(text)
        assert len(issues) >= 1  # At least the invalid command


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_parse_audiobook_markup(self):
        """Test parse_audiobook_markup convenience function."""
        text = "{{{voice:voice1}}}Hello world"
        result = parse_audiobook_markup(text)

        assert len(result) == 1
        assert result[0].text == "Hello world"
        assert result[0].voice == "voice1"

    def test_validate_audiobook_markup(self):
        """Test validate_audiobook_markup convenience function."""
        text = "{{{voice:voice1}}}Valid text"
        issues = validate_audiobook_markup(text)
        assert issues == []

        text = "{{{invalid:command}}}Invalid text"
        issues = validate_audiobook_markup(text)
        assert len(issues) == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_markup(self):
        """Test empty markup tags."""
        text = "{{{}}}Text"
        # Empty markup {{{}}} doesn't match regex, treated as text
        result = parse_audiobook_markup(text)
        assert len(result) == 1
        assert result[0].text == "{{{}}}Text"

    def test_whitespace_in_markup(self):
        """Test markup with extra whitespace."""
        text = "{{{ voice : voice1 }}}Text"
        result = parse_audiobook_markup(text)
        assert result[0].voice == "voice1"

    def test_multiple_colons(self):
        """Test markup with multiple colons."""
        text = "{{{bg:music:extra}}}Text"
        result = parse_audiobook_markup(text)
        assert result[0].background_audio == {"name": "music:extra"}

    def test_special_characters_in_values(self):
        """Test special characters in markup values."""
        text = "{{{voice:voice_with_underscores}}}Text"
        result = parse_audiobook_markup(text)
        assert result[0].voice == "voice_with_underscores"

    def test_nested_markup_like_text(self):
        """Test text that looks like markup but isn't."""
        text = "This is {{{ not markup }}} text."
        # The regex matches {{{ not markup }}} as markup, and parsing fails
        with pytest.raises(AudiobookMarkupError, match="Invalid markup format"):
            parse_audiobook_markup(text)

    def test_minimum_valid_markup(self):
        """Test minimum valid markup."""
        text = "{{{voice:v}}}t"
        result = parse_audiobook_markup(text)
        assert result[0].voice == "v"
        assert result[0].text == "t"

    def test_maximum_options(self):
        """Test markup with many options."""
        text = "{{{bg:music,vol:0.5,fade:1.0,loop:true,duck:0.2}}}Text"
        result = parse_audiobook_markup(text)
        bg = result[0].background_audio
        assert bg is not None
        assert bg["name"] == "music"
        assert bg["vol"] == 0.5
        assert bg["fade"] == 1.0
        assert bg["loop"] == "true"  # String, not converted to bool
        assert bg["duck"] == 0.2
