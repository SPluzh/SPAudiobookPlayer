"""
Listening Tracker Module
Tracks actual listening time for audiobooks with session-based recording.
"""

from datetime import datetime
from typing import Optional
from pathlib import Path


class ListeningTracker:
    """Tracks actual listening time and manages session data"""
    
    def __init__(self, db_manager):
        """Initialize the listening tracker
        
        Args:
            db_manager: DatabaseManager instance for database operations
        """
        self.db = db_manager
        self.current_session_id: Optional[int] = None
        self.session_start_time: Optional[datetime] = None
        self.accumulated_seconds: float = 0.0
        self.last_update_time: Optional[datetime] = None
        self.current_audiobook_id: Optional[int] = None
        self.current_speed: float = 1.0
        self.is_active: bool = False
        
    def start_session(self, audiobook_id: int, speed: float = 1.0):
        """Start a new listening session
        
        Args:
            audiobook_id: ID of the audiobook being played
            speed: Current playback speed
        """
        # End any existing session first
        if self.current_session_id:
            self.end_session()
        
        now = datetime.now()
        session_date = now.strftime('%Y-%m-%d')
        
        # Create new session in database
        self.current_session_id = self.db.create_listening_session(
            audiobook_id=audiobook_id,
            start_time=now,
            speed=speed
        )
        
        if self.current_session_id:
            self.current_audiobook_id = audiobook_id
            self.session_start_time = now
            self.last_update_time = now
            self.accumulated_seconds = 0.0
            self.current_speed = speed
            self.is_active = True
            print(f"[ListeningTracker] Started session {self.current_session_id} for audiobook {audiobook_id}")
    
    def update_session(self, is_playing: bool, speed: float):
        """Called every 100ms from main timer - accumulates listening time
        
        Args:
            is_playing: Whether audio is currently playing
            speed: Current playback speed
        """
        if not is_playing or not self.current_session_id or not self.is_active:
            return
        
        now = datetime.now()
        
        if self.last_update_time:
            # Calculate elapsed real time (wall clock time)
            elapsed = (now - self.last_update_time).total_seconds()
            
            # Accumulate actual listening time (not affected by playback speed)
            # We track REAL time spent listening, not content time
            self.accumulated_seconds += elapsed
            
            # Save to DB every 10 seconds to avoid excessive writes
            if self.accumulated_seconds >= 10.0:
                self._flush_to_database()
        
        self.last_update_time = now
        self.current_speed = speed
    
    def pause_session(self):
        """Pause current session (save progress but keep session open)"""
        if self.current_session_id and self.accumulated_seconds > 0:
            self._flush_to_database()
            print(f"[ListeningTracker] Paused session {self.current_session_id}")
    
    def end_session(self):
        """End current session and save to database"""
        if not self.current_session_id:
            return
        
        # Flush any remaining accumulated time
        if self.accumulated_seconds > 0:
            self._flush_to_database()
        
        # Close the session
        now = datetime.now()
        self.db.close_listening_session(
            session_id=self.current_session_id,
            end_time=now
        )
        
        print(f"[ListeningTracker] Ended session {self.current_session_id}")
        
        # Reset state
        self.current_session_id = None
        self.session_start_time = None
        self.accumulated_seconds = 0.0
        self.last_update_time = None
        self.current_audiobook_id = None
        self.is_active = False
    
    def _flush_to_database(self):
        """Persist accumulated time to database"""
        if not self.current_session_id or self.accumulated_seconds <= 0:
            return
        
        try:
            self.db.update_listening_session(
                session_id=self.current_session_id,
                duration_seconds=self.accumulated_seconds,
                speed=self.current_speed
            )
            
            print(f"[ListeningTracker] Flushed {self.accumulated_seconds:.1f}s to session {self.current_session_id}")
            
            # Reset accumulator after successful save
            self.accumulated_seconds = 0.0
            
        except Exception as e:
            print(f"[ListeningTracker] Error flushing to database: {e}")
    
    def switch_audiobook(self, new_audiobook_id: int, speed: float = 1.0):
        """Switch to a different audiobook (ends current session and starts new one)
        
        Args:
            new_audiobook_id: ID of the new audiobook
            speed: Playback speed for the new audiobook
        """
        if self.current_audiobook_id != new_audiobook_id:
            self.end_session()
            self.start_session(new_audiobook_id, speed)
