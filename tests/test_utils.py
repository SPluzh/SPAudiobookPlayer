import pytest
from utils import format_duration, format_time, format_time_short

# Mocking trf for testing purposes since it depends on translations
import utils
original_trf = None

@pytest.fixture(autouse=True)
def mock_trf(monkeypatch):
    """Mock trf to return predictable strings"""
    def mock_return(key, **kwargs):
        if key == "formats.duration_hours":
            return f"{kwargs['hours']} ч {kwargs['minutes']} мин"
        elif key == "formats.duration_minutes":
            return f"{kwargs['minutes']} мин"
        elif key == "formats.duration_seconds":
            return f"{kwargs['seconds']} сек"
        elif key == "formats.time_hms":
            return f"{kwargs['hours']:02d}:{kwargs['minutes']:02d}:{kwargs['seconds']:02d}"
        elif key == "formats.time_ms":
            return f"{kwargs['minutes']:02d}:{kwargs['seconds']:02d}"
        return key

    monkeypatch.setattr(utils, "trf", mock_return)

class TestFormatDuration:
    def test_zero(self):
        assert format_duration(0) == ""
        assert format_duration(None) == ""
        
    def test_seconds_only(self):
        # 45 seconds
        assert format_duration(45) == "45 сек"
        
    def test_minutes_only(self):
        # 5 minutes, 0 seconds
        assert format_duration(300) == "5 мин"
        # 5 minutes, 30 seconds (seconds are ignored in this format if minutes exist?)
        # Implementation: if minutes: return ... minutes
        assert format_duration(330) == "5 мин"
        
    def test_hours(self):
        # 1 hour, 30 minutes
        assert format_duration(5400) == "1 ч 30 мин"
        # 2 hours, 0 minutes
        assert format_duration(7200) == "2 ч 0 мин"

class TestFormatTime:
    def test_zero(self):
        assert format_time(0) == "00:00:00"
        
    def test_negative(self):
        assert format_time(-10) == "00:00:00"
        
    def test_minutes_seconds(self):
        assert format_time(65) == "00:01:05"
        
    def test_hours_minutes_seconds(self):
        assert format_time(3665) == "01:01:05"

class TestFormatTimeShort:
    def test_zero(self):
        assert format_time_short(0) == "00:00"
        
    def test_negative(self):
        assert format_time_short(-5) == "00:00"
        
    def test_minutes_seconds(self):
        assert format_time_short(65) == "01:05"
        
    def test_large_duration(self):
        # 1 hour 5 sec -> 61:05 in MM:SS
        assert format_time_short(3665) == "61:05"
