"""Internationalization (i18n) support for Talk2Me UI.

This module provides translation functionality for both backend templates
and frontend JavaScript applications.
"""

import json
from pathlib import Path
from typing import Any


class I18nManager:
    """Manages internationalization for the application."""

    def __init__(self, translations_dir: str = None):
        """Initialize the i18n manager.

        Args:
            translations_dir: Directory containing translation files
        """
        if translations_dir is None:
            # Default to the directory where this module is located
            module_dir = Path(__file__).parent
            self.translations_dir = module_dir / "translations"
        else:
            self.translations_dir = Path(translations_dir)

        self.translations: dict[str, dict[str, Any]] = {}
        self.default_locale = "en"
        self.supported_locales = ["en", "es", "fr", "de", "zh"]

        self._load_translations()

    def _load_translations(self) -> None:
        """Load all translation files."""
        for locale in self.supported_locales:
            translation_file = self.translations_dir / f"{locale}.json"
            if translation_file.exists():
                try:
                    with open(translation_file, encoding="utf-8") as f:
                        self.translations[locale] = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    # Fallback to empty dict if file is corrupted or missing
                    self.translations[locale] = {}
            else:
                self.translations[locale] = {}

    def get_text(self, key: str, locale: str = None, **kwargs) -> str:
        """Get translated text for a given key.

        Args:
            key: Translation key (dot-separated for nested access)
            locale: Language locale (defaults to default_locale)
            **kwargs: Variables to interpolate in the translation

        Returns:
            Translated text or the key if not found
        """
        if locale is None:
            locale = self.default_locale

        # Ensure locale exists
        if locale not in self.translations:
            locale = self.default_locale

        # Navigate through nested keys
        keys = key.split(".")
        value = self.translations[locale]

        try:
            for k in keys:
                value = value[k]
        except (KeyError, TypeError):
            # Fallback to English if translation not found
            if locale != self.default_locale:
                return self.get_text(key, self.default_locale, **kwargs)
            # Return key if no translation found
            return key

        # Handle string interpolation
        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return value if isinstance(value, str) else str(value)

    def set_locale(self, locale: str) -> None:
        """Set the current locale.

        Args:
            locale: Language locale code
        """
        if locale in self.supported_locales:
            self.default_locale = locale

    def get_available_locales(self) -> list[str]:
        """Get list of available locales.

        Returns:
            List of supported locale codes
        """
        return self.supported_locales.copy()

    def detect_locale_from_request(self, accept_language: str = None) -> str:
        """Detect locale from HTTP Accept-Language header.

        Args:
            accept_language: Accept-Language header value

        Returns:
            Detected locale code
        """
        if not accept_language:
            return self.default_locale

        # Parse Accept-Language header
        languages = []
        for lang in accept_language.split(","):
            lang = lang.strip().split(";")[0].strip()
            # Extract base language (e.g., 'en-US' -> 'en')
            base_lang = lang.split("-")[0].lower()
            languages.append(base_lang)

        # Find first supported language
        for lang in languages:
            if lang in self.supported_locales:
                return lang

        return self.default_locale


# Global i18n manager instance
i18n_manager = I18nManager()


def gettext(key: str, **kwargs) -> str:
    """Get translated text (alias for i18n_manager.get_text).

    Args:
        key: Translation key
        **kwargs: Variables for interpolation

    Returns:
        Translated text
    """
    return i18n_manager.get_text(key, **kwargs)


def ngettext(singular: str, plural: str, n: int, **kwargs) -> str:
    """Get translated text with plural forms.

    Args:
        singular: Singular form key
        plural: Plural form key
        n: Count for plural determination
        **kwargs: Variables for interpolation

    Returns:
        Translated text
    """
    # For simplicity, just use singular/plural based on n
    key = singular if n == 1 else plural
    return i18n_manager.get_text(key, **kwargs)


# Template context functions
def get_template_context(locale: str = None):
    """Get template context with translation functions.

    Args:
        locale: Language locale

    Returns:
        Dictionary with translation functions
    """
    if locale:
        i18n_manager.set_locale(locale)

    return {
        "_": gettext,
        "gettext": gettext,
        "ngettext": ngettext,
    }
