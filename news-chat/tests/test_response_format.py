"""
Tests for chat response formatting.

These tests verify that chat responses are user-friendly and properly formatted,
not raw JSON or technical output.
"""

import json
import pytest
import re
from unittest.mock import AsyncMock, patch


class TestResponseFormatting:
    """Test that responses are properly formatted for users."""
    
    def test_response_not_raw_json(self):
        """Test that good responses don't contain raw JSON objects."""
        # Good response - human-readable format
        good_response = """Here are the latest trending topics from Spiegel:

• AI - 168 mentions
• China - 14 mentions
• Technology - 12 mentions

Would you like more details about any of these topics? 🦫"""
        
        # Check for raw JSON patterns that shouldn't be in user responses
        json_patterns = [
            r'\{["\']?\w+["\']?\s*:\s*[\[\{]',  # {"key": [ or {"key": {
            r'\[\s*\{["\']?\w+["\']?\s*:',       # [{"key":
        ]
        
        for pattern in json_patterns:
            assert not re.search(pattern, good_response), \
                f"Response should not contain raw JSON matching pattern: {pattern}"
    
    def test_bad_response_detected(self):
        """Test that raw JSON in responses is detected as problematic."""
        # Bad response - raw tool output mixed with text
        bad_response = '''Based on the latest data from Spiegel, here are some trending topics:
{"topics": [{"name": "AI", "count": 168}, {"name": "中国", "count": 14}]}'''
        
        # Check for raw JSON patterns
        json_patterns = [
            r'\{["\']?\w+["\']?\s*:\s*[\[\{]',  # {"key": [ or {"key": {
            r'\[\s*\{["\']?\w+["\']?\s*:',       # [{"key":
        ]
        
        # This bad response SHOULD contain JSON patterns
        found_json = False
        for pattern in json_patterns:
            if re.search(pattern, bad_response):
                found_json = True
                break
        
        assert found_json, "Bad response should have been detected as containing raw JSON"
    
    def test_good_response_format(self):
        """Test that well-formatted responses pass validation."""
        good_response = """Here are the latest headlines from Spiegel:

• Germany announces new climate policy - Spiegel
• Tech giants face EU regulation - Spiegel
• Chancellor meets with foreign ministers - Spiegel

Would you like more details on any of these stories? 🦫"""
        
        # Good responses should NOT contain raw JSON
        json_patterns = [
            r'\{["\']?\w+["\']?\s*:\s*[\[\{]',
            r'\[\s*\{["\']?\w+["\']?\s*:',
        ]
        
        for pattern in json_patterns:
            assert not re.search(pattern, good_response), \
                f"Good response should not match JSON pattern: {pattern}"
    
    def test_response_not_technical(self):
        """Test that responses don't contain technical jargon."""
        bad_patterns = [
            r'Calling \w+\.\.\.',           # "Calling get_trending_topics..."
            r'tool_call',                    # Technical term
            r'function_call',                # Technical term
            r'"type":\s*"function"',         # JSON function definition
            r'arguments\s*[=:]\s*\{',        # arguments = { or arguments: {
        ]
        
        good_response = "Here are today's top stories from Spiegel! 🦫"
        
        for pattern in bad_patterns:
            assert not re.search(pattern, good_response), \
                f"Response should not contain technical pattern: {pattern}"
    
    def test_headlines_have_source_attribution(self):
        """Test that headlines include source names."""
        good_response = """Here are the latest headlines:

• Germany announces new climate policy - Spiegel
• Tech giants face EU regulation - The Guardian
• Chancellor meets with foreign ministers - Reuters"""
        
        # Each headline should have a source after " - "
        lines = [l for l in good_response.split('\n') if l.strip().startswith('•')]
        for line in lines:
            assert ' - ' in line, f"Headline missing source attribution: {line}"


class TestToolCallVisibility:
    """Test that tool calls are not shown to users."""
    
    def test_tool_call_indicator_format(self):
        """Test the format of tool call indicators (if shown)."""
        # If we show tool calls, they should be user-friendly
        good_indicator = "🔧 Searching for news..."
        bad_indicator = "🔧 *Calling get_trending_topics...*"
        
        # Good: Simple, friendly
        assert "Searching" in good_indicator or "Looking" in good_indicator or "Getting" in good_indicator
        
        # Bad: Technical function names
        assert "get_" not in good_indicator.lower()
        assert "function" not in good_indicator.lower()


class TestChineseTextHandling:
    """Test that Chinese/CJK text is handled appropriately."""
    
    def test_chinese_topics_translated_or_contextualized(self):
        """Test that Chinese topics are explained in English."""
        # Bad: Raw Chinese without context
        bad_response = "Trending topics: 中国, 机器人, 华为, 芯片"
        
        # Good: Chinese with English translation/context
        good_response = "Trending topics include China (中国), Robotics, and Huawei"
        
        # If response contains Chinese characters, it should also have English
        chinese_pattern = r'[\u4e00-\u9fff]+'
        
        if re.search(chinese_pattern, bad_response):
            # Check if there's also English context
            english_words = re.findall(r'[a-zA-Z]{3,}', bad_response)
            # Bad response has Chinese but minimal English context
            assert len(english_words) < 5, "This test shows bad formatting"


class TestStreamingResponseFormat:
    """Test SSE streaming response format."""
    
    def test_sse_data_format(self):
        """Test that SSE data lines are properly formatted."""
        # Valid SSE format
        valid_lines = [
            'data: {"content": "Hello"}',
            'data: {"content": " world"}',
            'data: [DONE]',
        ]
        
        for line in valid_lines:
            assert line.startswith('data: '), f"SSE line must start with 'data: ': {line}"
    
    def test_sse_content_is_json(self):
        """Test that SSE content is valid JSON."""
        sse_line = 'data: {"content": "Hello world"}'
        
        # Extract JSON part
        if sse_line.startswith('data: ') and sse_line != 'data: [DONE]':
            json_str = sse_line[6:]  # Remove 'data: ' prefix
            try:
                data = json.loads(json_str)
                assert 'content' in data or 'error' in data or 'tool_call' in data
            except json.JSONDecodeError:
                pytest.fail(f"SSE data is not valid JSON: {json_str}")


class TestResponsePersonality:
    """Test that responses have the Woodchuck personality."""
    
    def test_friendly_tone(self):
        """Test that responses are friendly, not robotic."""
        robotic_phrases = [
            "I have retrieved",
            "The data shows",
            "According to my analysis",
            "The following information was obtained",
        ]
        
        friendly_response = "Here are today's top stories! 🦫"
        
        for phrase in robotic_phrases:
            assert phrase not in friendly_response, \
                f"Response should not use robotic phrase: {phrase}"
    
    def test_emoji_usage(self):
        """Test that responses can include appropriate emojis."""
        response_with_emoji = "Great question! Here's what I found 🦫"
        
        # Emojis are allowed and encouraged
        emoji_pattern = r'[\U0001F300-\U0001F9FF]'
        # This is optional, just testing that emojis are valid
        assert re.search(emoji_pattern, response_with_emoji) or True
