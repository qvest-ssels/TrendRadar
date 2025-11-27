"""
Simple working tests for TrendRadar
"""
import pytest
from datetime import datetime
from unittest.mock import patch
import pytz

from main import get_local_time, format_date_folder, format_time_filename


class TestTimezoneFunctions:
    """Test timezone-related utility functions"""

    @patch('main.CONFIG', {'TIMEZONE': 'UTC'})
    def test_get_local_time_utc(self):
        """Test get_local_time with UTC timezone"""
        result = get_local_time()
        assert isinstance(result, datetime)
        assert result.tzinfo.zone == 'UTC'

    @patch('main.CONFIG', {'TIMEZONE': 'Europe/Paris'})
    def test_get_local_time_paris(self):
        """Test get_local_time with Paris timezone (UTC+1)"""
        result = get_local_time()
        assert isinstance(result, datetime)
        assert result.tzinfo.zone == 'Europe/Paris'

    @patch('main.CONFIG', {'TIMEZONE': 'UTC'})
    def test_format_date_folder(self):
        """Test format_date_folder function"""
        result = format_date_folder()
        assert isinstance(result, str)
        # Check for ISO date format: YYYY-MM-DD
        assert len(result.split('-')) == 3
        assert result.count('-') == 2

    @patch('main.CONFIG', {'TIMEZONE': 'UTC'})
    def test_format_time_filename(self):
        """Test format_time_filename function"""
        result = format_time_filename()
        assert isinstance(result, str)
        # Check for time format: HH-MM
        assert len(result.split('-')) == 2
        assert result.count('-') == 1
