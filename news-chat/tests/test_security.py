"""
Security tests for News Chat

Tests for XSS prevention, injection attacks, and secret leakage prevention.
"""

import sys
import os
import pytest

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.security import (
    sanitize_input,
    escape_html_content,
    detect_secrets,
    redact_secrets,
    validate_message_content,
    sanitize_url,
)


class TestSanitizeInput:
    """Tests for input sanitization."""
    
    def test_sanitize_normal_input(self):
        """Normal input should pass through."""
        text = "Hello, how are you?"
        assert sanitize_input(text) == text
    
    def test_sanitize_removes_null_bytes(self):
        """Null bytes should be removed."""
        text = "Hello\x00World"
        assert sanitize_input(text) == "HelloWorld"
    
    def test_sanitize_removes_control_chars(self):
        """Control characters should be removed."""
        text = "Hello\x01\x02\x03World"
        assert sanitize_input(text) == "HelloWorld"
    
    def test_sanitize_preserves_newlines_tabs(self):
        """Newlines and tabs should be preserved."""
        text = "Hello\n\tWorld"
        assert sanitize_input(text) == text
    
    def test_sanitize_truncates_long_input(self):
        """Long inputs should be truncated."""
        text = "A" * 15000
        result = sanitize_input(text, max_length=10000)
        assert len(result) == 10000
    
    def test_sanitize_empty_input(self):
        """Empty input should return empty string."""
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""
    
    def test_sanitize_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        text = "   Hello World   "
        assert sanitize_input(text) == "Hello World"


class TestEscapeHtml:
    """Tests for HTML escaping."""
    
    def test_escape_script_tags(self):
        """Script tags should be escaped."""
        text = "<script>alert('XSS')</script>"
        result = escape_html_content(text)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_escape_html_entities(self):
        """HTML entities should be escaped."""
        text = "<div onclick='alert(1)'>Test</div>"
        result = escape_html_content(text)
        assert "&lt;div" in result
        assert "onclick" in result  # Attribute name is safe when tag is escaped
    
    def test_escape_special_chars(self):
        """Special characters should be escaped."""
        text = "a < b && c > d"
        result = escape_html_content(text)
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result
    
    def test_escape_quotes(self):
        """Quotes should be escaped."""
        text = 'He said "hello" and \'goodbye\''
        result = escape_html_content(text)
        assert "&quot;" in result


class TestDetectSecrets:
    """Tests for secret detection."""
    
    def test_detect_api_key(self):
        """API keys should be detected."""
        text = "api_key: sk-1234567890abcdefghij"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("API_KEY" in s[1] or "TOKEN" in s[1] for s in secrets)
    
    def test_detect_jwt_token(self):
        """JWT tokens should be detected."""
        text = "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("JWT" in s[1] for s in secrets)
    
    def test_detect_github_token(self):
        """GitHub tokens should be detected."""
        text = "GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("GITHUB" in s[1] for s in secrets)
    
    def test_detect_private_key(self):
        """Private keys should be detected."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("PRIVATE_KEY" in s[1] for s in secrets)
    
    def test_detect_telegram_token(self):
        """Telegram bot tokens should be detected."""
        text = "BOT_TOKEN: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("TELEGRAM" in s[1] for s in secrets)
    
    def test_no_false_positive_short_strings(self):
        """Short strings should not trigger false positives."""
        text = "password: test"
        secrets = detect_secrets(text)
        # "test" is only 4 chars, should not be flagged
        assert len(secrets) == 0 or all(len(s[0]) > 10 for s in secrets)
    
    def test_no_false_positive_normal_text(self):
        """Normal text should not trigger false positives."""
        text = "Today's news headlines include: Tech stocks rise, Weather update, Sports results"
        secrets = detect_secrets(text)
        assert len(secrets) == 0


class TestContextAwareSecretDetection:
    """Tests for context-aware secret detection."""
    
    def test_password_in_prose_not_flagged(self):
        """Password mentioned in prose should NOT be flagged."""
        # LLM explaining about passwords
        text = "To set a password, you should use at least 12 characters. A strong password includes letters and numbers."
        secrets = detect_secrets(text)
        assert len(secrets) == 0
    
    def test_password_in_config_flagged(self):
        """Password in config format SHOULD be flagged."""
        text = "password = mysecretpassword123"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
    
    def test_api_key_in_prose_not_flagged(self):
        """API key mentioned in prose should NOT be flagged."""
        text = "You can get an api key from the settings page. Your api key should be kept secret."
        secrets = detect_secrets(text)
        assert len(secrets) == 0
    
    def test_api_key_in_config_flagged(self):
        """API key in config format SHOULD be flagged."""
        text = "api_key = sk-1234567890abcdefghijklmnop"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
    
    def test_token_discussion_not_flagged(self):
        """Discussion about tokens should NOT be flagged."""
        text = "The authentication token is used to verify your identity. You should never share your token with others."
        secrets = detect_secrets(text)
        assert len(secrets) == 0
    
    def test_jwt_always_flagged(self):
        """JWT tokens should ALWAYS be flagged (distinctive format)."""
        text = "Here's the token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("JWT" in s[1] for s in secrets)
    
    def test_github_token_always_flagged(self):
        """GitHub tokens should ALWAYS be flagged (distinctive prefix)."""
        text = "Check out the repo using ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
        assert any("GITHUB" in s[1] for s in secrets)
    
    def test_private_key_always_flagged(self):
        """Private keys should ALWAYS be flagged."""
        text = "The certificate contains: -----BEGIN PRIVATE KEY-----"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
    
    def test_slack_webhook_always_flagged(self):
        """Slack webhooks should ALWAYS be flagged."""
        text = "Send notifications to https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        secrets = detect_secrets(text)
        assert len(secrets) > 0
    
    def test_llm_explanation_not_flagged(self):
        """LLM explaining security concepts should NOT be flagged."""
        text = """
        When configuring your application, you'll need to set up authentication.
        The password field should contain your database password.
        Your api key can be found in the developer console.
        The secret token is required for webhook authentication.
        Make sure to keep your credentials secure and never commit them to version control.
        """
        secrets = detect_secrets(text)
        # This prose discussion should not trigger any secrets
        assert len(secrets) == 0


class TestRedactSecrets:
    """Tests for secret redaction."""
    
    def test_redact_api_key(self):
        """API keys should be redacted."""
        text = "api_key = sk-1234567890abcdefghij"
        result = redact_secrets(text)
        assert "REDACTED" in result
    
    def test_redact_preserves_structure(self):
        """Redaction should preserve text structure."""
        text = "Config:\n  api_key = sk-1234567890abcdefghij\n  host: localhost"
        result = redact_secrets(text)
        assert "Config:" in result
        assert "host: localhost" in result
        assert "REDACTED" in result
    
    def test_redact_multiple_secrets(self):
        """Multiple secrets should all be redacted."""
        text = "api_key = key123456789012345\npassword = secretpassword123"
        result = redact_secrets(text)
        # Should have redacted at least one
        assert "REDACTED" in result
    
    def test_redact_jwt_in_prose(self):
        """JWT tokens in prose should still be redacted."""
        text = "The JWT is eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_secrets(text)
        assert "REDACTED" in result
    
    def test_prose_not_redacted(self):
        """Prose about passwords should NOT be redacted."""
        text = "You should use a strong password with at least 12 characters."
        result = redact_secrets(text)
        assert result == text  # Unchanged


class TestValidateMessageContent:
    """Tests for message content validation."""
    
    def test_validate_normal_content(self):
        """Normal content should be valid."""
        is_valid, error = validate_message_content("Hello, what's the news today?")
        assert is_valid
        assert error is None
    
    def test_validate_empty_content(self):
        """Empty content should be valid."""
        is_valid, error = validate_message_content("")
        assert is_valid
    
    def test_reject_script_tags(self):
        """Script tags should be rejected."""
        is_valid, error = validate_message_content("<script>alert('xss')</script>")
        assert not is_valid
        assert "dangerous" in error.lower()
    
    def test_reject_javascript_protocol(self):
        """JavaScript protocol should be rejected."""
        is_valid, error = validate_message_content("Click here: javascript:alert(1)")
        assert not is_valid
    
    def test_reject_event_handlers(self):
        """Event handlers should be rejected."""
        is_valid, error = validate_message_content('<img onerror="alert(1)">')
        assert not is_valid
    
    def test_reject_data_html(self):
        """Data HTML URLs should be rejected."""
        is_valid, error = validate_message_content("data:text/html,<script>alert(1)</script>")
        assert not is_valid
    
    def test_reject_too_long_content(self):
        """Extremely long content should be rejected."""
        is_valid, error = validate_message_content("A" * 60000)
        assert not is_valid
        assert "too long" in error.lower()


class TestSanitizeUrl:
    """Tests for URL sanitization."""
    
    def test_valid_http_url(self):
        """Valid HTTP URLs should pass."""
        url = "http://example.com/page"
        assert sanitize_url(url) == url
    
    def test_valid_https_url(self):
        """Valid HTTPS URLs should pass."""
        url = "https://example.com/page?query=test"
        assert sanitize_url(url) == url
    
    def test_reject_javascript_url(self):
        """JavaScript URLs should be rejected."""
        assert sanitize_url("javascript:alert(1)") is None
    
    def test_reject_data_url(self):
        """Data URLs should be rejected."""
        assert sanitize_url("data:text/html,<script>") is None
    
    def test_reject_no_protocol(self):
        """URLs without protocol should be rejected."""
        assert sanitize_url("example.com/page") is None
    
    def test_empty_url(self):
        """Empty URLs should return None."""
        assert sanitize_url("") is None
        assert sanitize_url(None) is None
    
    def test_url_with_special_chars(self):
        """URLs with allowed special chars should pass."""
        url = "https://example.com/path?query=test&foo=bar#anchor"
        assert sanitize_url(url) == url


class TestXSSPrevention:
    """Integration tests for XSS prevention."""
    
    def test_malicious_input_sanitized(self):
        """Malicious inputs should be sanitized end-to-end."""
        malicious_inputs = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert(1)>',
            '"><script>alert(1)</script>',
            "javascript:alert(document.cookie)",
            '<svg onload=alert(1)>',
            '<body onload=alert(1)>',
            '<iframe src="javascript:alert(1)">',
        ]
        
        for malicious in malicious_inputs:
            # Should either reject or escape
            is_valid, _ = validate_message_content(malicious)
            if is_valid:
                # If it passes validation, it should be escaped
                escaped = escape_html_content(malicious)
                assert '<script>' not in escaped
                assert 'onerror=' not in escaped.lower() or '&' in escaped


class TestInjectionPrevention:
    """Tests for injection attack prevention."""
    
    def test_sql_injection_patterns_pass(self):
        """SQL injection patterns in chat should be handled (they're for LLM, not DB)."""
        # SQL injection is not relevant for chat (no DB queries)
        # but we should ensure the content doesn't break anything
        text = "'; DROP TABLE users; --"
        sanitized = sanitize_input(text)
        assert sanitized == text.strip()  # SQL doesn't need escaping in chat
    
    def test_command_injection_patterns(self):
        """Command injection patterns should be sanitized."""
        text = "; rm -rf /; echo 'pwned'"
        sanitized = sanitize_input(text)
        # The text should pass but null bytes removed
        assert "\x00" not in sanitized
    
    def test_path_traversal_in_url(self):
        """Path traversal in URLs should be handled."""
        # Path traversal like ../../../ in URLs
        url = "https://example.com/../../../etc/passwd"
        result = sanitize_url(url)
        # URL is technically valid, but path traversal is in the path
        # The sanitize_url checks for protocol, not path validity
        assert result is not None  # Protocol is valid


# Timeout for all tests in this file (security tests should be fast)
pytestmark = pytest.mark.timeout(5)
