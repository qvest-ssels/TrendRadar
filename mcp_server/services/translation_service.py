"""
Translation Service

Provides translation functionality using LibreTranslate or other backends.
Designed to be modular and support multiple translation services.
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Translation service using LibreTranslate API.
    
    Can be used to:
    - Translate text between languages
    - Detect source language
    - Get available language pairs
    """
    
    def __init__(self, base_url: str = "http://localhost:5555", timeout: int = 30):
        """
        Initialize translation service.
        
        Args:
            base_url: LibreTranslate API URL (default: localhost:5555)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._available = None
        self._languages = None
    
    def is_available(self) -> bool:
        """Check if translation service is available."""
        if self._available is not None:
            return self._available
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            self._available = response.status_code == 200
        except Exception as e:
            logger.debug(f"Translation service not available: {e}")
            self._available = False
        
        return self._available
    
    def get_languages(self) -> List[Dict[str, Any]]:
        """
        Get available languages from the translation service.
        
        Returns:
            List of language dictionaries with code, name, and targets
        """
        if self._languages is not None:
            return self._languages
        
        if not self.is_available():
            return []
        
        try:
            response = requests.get(
                f"{self.base_url}/languages",
                timeout=self.timeout
            )
            if response.status_code == 200:
                self._languages = response.json()
                return self._languages
        except Exception as e:
            logger.error(f"Failed to get languages: {e}")
        
        return []
    
    def get_supported_language_codes(self) -> List[str]:
        """Get list of supported language codes."""
        languages = self.get_languages()
        return [lang['code'] for lang in languages]
    
    def can_translate(self, source: str, target: str) -> bool:
        """
        Check if translation between source and target is supported.
        
        Args:
            source: Source language code (e.g., 'en', 'de', 'zh-Hans')
            target: Target language code
            
        Returns:
            True if translation pair is supported
        """
        languages = self.get_languages()
        for lang in languages:
            if lang['code'] == source:
                return target in lang.get('targets', [])
        return False
    
    def translate(
        self,
        text: str,
        source: str = "auto",
        target: str = "en"
    ) -> Optional[str]:
        """
        Translate text from source to target language.
        
        Args:
            text: Text to translate
            source: Source language code or 'auto' for detection
            target: Target language code
            
        Returns:
            Translated text or None on failure
        """
        if not self.is_available():
            logger.warning("Translation service not available")
            return None
        
        if not text or not text.strip():
            return text
        
        try:
            response = requests.post(
                f"{self.base_url}/translate",
                json={
                    "q": text,
                    "source": source,
                    "target": target
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('translatedText')
            else:
                logger.error(f"Translation failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Translation error: {e}")
        
        return None
    
    def translate_batch(
        self,
        texts: List[str],
        source: str = "auto",
        target: str = "en"
    ) -> List[Optional[str]]:
        """
        Translate multiple texts.
        
        Args:
            texts: List of texts to translate
            source: Source language code or 'auto'
            target: Target language code
            
        Returns:
            List of translated texts (None for failed translations)
        """
        if not self.is_available():
            return [None] * len(texts)
        
        results = []
        for text in texts:
            translated = self.translate(text, source, target)
            results.append(translated)
        
        return results
    
    def detect_language(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect the language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with 'language' and 'confidence' or None
        """
        if not self.is_available():
            return None
        
        try:
            response = requests.post(
                f"{self.base_url}/detect",
                json={"q": text},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    return results[0]
                    
        except Exception as e:
            logger.error(f"Language detection error: {e}")
        
        return None


# Global singleton instance
_translation_service: Optional[TranslationService] = None


def get_translation_service(base_url: str = "http://localhost:5555") -> TranslationService:
    """
    Get or create the translation service singleton.
    
    Args:
        base_url: LibreTranslate API URL
        
    Returns:
        TranslationService instance
    """
    global _translation_service
    
    if _translation_service is None:
        _translation_service = TranslationService(base_url)
    
    return _translation_service


def translate_text(
    text: str,
    source: str = "auto",
    target: str = "en",
    base_url: str = "http://localhost:5555"
) -> Optional[str]:
    """
    Convenience function to translate text.
    
    Args:
        text: Text to translate
        source: Source language code or 'auto'
        target: Target language code
        base_url: LibreTranslate API URL
        
    Returns:
        Translated text or None
    """
    service = get_translation_service(base_url)
    return service.translate(text, source, target)
