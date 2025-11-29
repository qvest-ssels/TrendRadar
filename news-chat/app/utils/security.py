"""
Security utilities for News Chat

Provides input sanitization, XSS prevention, and context-aware secret detection.
"""

import html
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate potential secrets/credentials in CONFIG-LIKE contexts
# These require assignment operators or JSON-like structure to trigger
SECRET_PATTERNS_CONFIG = [
    # API keys in config (requires = or : assignment)
    (r'(?i)(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?', 'API_KEY'),
    # AWS access keys in config
    (r'(?i)(?:aws)?[_-]?(?:access[_-]?key[_-]?id|secret[_-]?access[_-]?key)\s*[:=]\s*["\']?([A-Z0-9]{16,})["\']?', 'AWS_KEY'),
    # Passwords in config (requires = or : assignment, NOT prose text)
    (r'(?i)(?:password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\'\n,}{]{8,})["\']?', 'PASSWORD'),
    # Generic tokens in config
    (r'(?i)(?:token|secret)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{16,})["\']?', 'TOKEN'),
    # Webhook URLs in config
    (r'(?i)webhook\s*[:=]\s*["\']?(https?://[^\s"\'\n]+)["\']?', 'WEBHOOK_URL'),
    # Database connection strings (always sensitive - contain embedded credentials)
    (r'(?i)(?:mongodb|postgresql|mysql|redis)://[^\s]+:[^\s@]+@', 'DB_CONNECTION'),
]

# Patterns that are ALWAYS sensitive regardless of context
SECRET_PATTERNS_ALWAYS = [
    # Bearer tokens (authentication header format)
    (r'(?i)bearer\s+([a-zA-Z0-9\-_\.]{20,})', 'BEARER_TOKEN'),
    # JWT tokens (distinctive format - always sensitive)
    (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', 'JWT_TOKEN'),
    # Private keys (PEM format - always sensitive)
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', 'PRIVATE_KEY'),
    # Telegram bot tokens (distinctive format: number:alphanumeric)
    (r'\d{8,12}:[a-zA-Z0-9_-]{35}', 'TELEGRAM_TOKEN'),
    # Slack webhook URLs (distinctive URL pattern)
    (r'https://hooks\.slack\.com/services/[A-Z0-9/]+', 'SLACK_WEBHOOK'),
    # GitHub tokens (distinctive prefix format)
    (r'(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}', 'GITHUB_TOKEN'),
]

# Compiled patterns for performance
_compiled_config_patterns = [(re.compile(pattern), name) for pattern, name in SECRET_PATTERNS_CONFIG]
_compiled_always_patterns = [(re.compile(pattern), name) for pattern, name in SECRET_PATTERNS_ALWAYS]


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Truncate overly long inputs
    if len(text) > max_length:
        logger.warning(f"Input truncated from {len(text)} to {max_length} characters")
        text = text[:max_length]
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char in '\n\t' or (ord(char) >= 32 and ord(char) != 127))
    
    return text.strip()


def escape_html_content(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Args:
        text: Text to escape
        
    Returns:
        HTML-escaped text
    """
    return html.escape(text, quote=True)


def detect_secrets(text: str, strict: bool = False) -> list[tuple[str, str]]:
    """
    Detect potential secrets/credentials in text using context-aware detection.
    
    By default, only detects secrets in config-like contexts (with = or : assignment)
    or patterns that are always sensitive (JWT, private keys, etc.).
    
    This avoids false positives when an LLM discusses passwords or tokens in prose.
    
    Args:
        text: Text to scan for secrets
        strict: If True, use stricter detection (may have more false positives)
        
    Returns:
        List of (matched_text, secret_type) tuples
    """
    found_secrets = []
    
    # Always check for patterns that are always sensitive
    for pattern, secret_type in _compiled_always_patterns:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match else ""
            if match and len(match) > 10:
                found_secrets.append((match[:20] + "..." if len(match) > 20 else match, secret_type))
    
    # Check config-like patterns (require assignment context)
    for pattern, secret_type in _compiled_config_patterns:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match else ""
            if match and len(match) > 10:
                found_secrets.append((match[:20] + "..." if len(match) > 20 else match, secret_type))
    
    return found_secrets


def redact_secrets(text: str) -> str:
    """
    Redact potential secrets from text using context-aware detection.
    
    Only redacts secrets that appear in config-like contexts or are
    always-sensitive patterns. Does not redact prose discussions about
    passwords or tokens.
    
    Args:
        text: Text that may contain secrets
        
    Returns:
        Text with secrets redacted
    """
    result = text
    
    # Redact always-sensitive patterns first
    for pattern, secret_type in _compiled_always_patterns:
        def make_redactor(stype):
            def redactor(match):
                full_match = match.group(0)
                logger.warning(f"Redacted potential {stype} in output")
                return full_match[:min(10, len(full_match))] + f"[REDACTED:{stype}]"
            return redactor
        
        result = pattern.sub(make_redactor(secret_type), result)
    
    # Then redact config-like patterns
    for pattern, secret_type in _compiled_config_patterns:
        def make_redactor(stype):
            def redactor(match):
                full_match = match.group(0)
                logger.warning(f"Redacted potential {stype} in output")
                # Keep the key part, redact only the value
                return full_match[:min(15, len(full_match))] + f"[REDACTED:{stype}]"
            return redactor
        
        result = pattern.sub(make_redactor(secret_type), result)
    
    return result


def validate_message_content(content: str) -> tuple[bool, Optional[str]]:
    """
    Validate message content for security concerns.
    
    Args:
        content: Message content to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content:
        return True, None
    
    # Check for extremely long content
    if len(content) > 50000:
        return False, "Message content too long"
    
    # Check for embedded scripts (shouldn't be present but defense in depth)
    dangerous_patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'on\w+\s*=',  # onclick, onerror, etc.
        r'data:text/html',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            logger.warning(f"Potentially dangerous content detected: {pattern}")
            return False, "Content contains potentially dangerous patterns"
    
    return True, None


def sanitize_url(url: str) -> Optional[str]:
    """
    Validate and sanitize a URL.
    
    Args:
        url: URL to validate
        
    Returns:
        Sanitized URL or None if invalid
    """
    if not url:
        return None
    
    url = url.strip()
    
    # Only allow http and https schemes
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return None
    
    # Block javascript and data URLs that might have slipped through
    if re.search(r'(?:javascript|data|vbscript):', url, re.IGNORECASE):
        return None
    
    # Basic URL validation
    # Allow: letters, numbers, and common URL characters
    if not re.match(r'^https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=%]+$', url):
        logger.warning(f"Invalid URL characters detected: {url[:50]}")
        return None
    
    return url
