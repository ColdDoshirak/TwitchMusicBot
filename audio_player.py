import pygame
import threading
import time
import os

class AudioPlayer:
    """Simple audio player for local files using pygame"""
    
    def __init__(self):
        self.initialized = False
        self.current_file = None
        self.is_playing = False
        self.volume = 0.5  # 0.0 to 1.0
        self.position = 0
        self.duration = 0
        self.update_callback = None
        self._position_thread = None
        self._stop_flag = threading.Event()
        
        # Initialize pygame mixer
        self._initialize()
    
    def _initialize(self):
        """Initialize pygame mixer"""
        try:
            pygame.mixer.init()
            self.initialized = True
            print("Audio player initialized")
        except Exception as e:
            print(f"Failed to initialize audio player: {e}")
            self.initialized = False
    
    def load(self, file_path):
        """Load an audio file"""
        if not self.initialized:
            self._initialize()
            if not self.initialized:
                print("Audio player not initialized")
                return False
        
        try:
            # Stop any currently playing audio
            self.stop()
            
            # Load the new file
            pygame.mixer.music.load(file_path)
            self.current_file = file_path
            
            # Get file duration (approximate based on MP3 file size and bitrate)
            try:
                file_size = os.path.getsize(file_path)
                # Assuming 320 kbps bitrate
                self.duration = file_size / (320 * 1024 / 8)
            except:
                self.duration = 0  # Unknown duration
                
            return True
        except Exception as e:
            print(f"Failed to load audio file: {e}")
            return False
    
    def play(self):
        """Start playing the loaded file"""
        if not self.initialized or not self.current_file:
            return False
        
        try:
            # Set volume before playing
            pygame.mixer.music.set_volume(self.volume)
            
            # Start playing
            pygame.mixer.music.play()
            self.is_playing = True
            
            # Start position tracking thread
            self._stop_flag.clear()
            self._position_thread = threading.Thread(
                target=self._track_position, 
                daemon=True
            )
            self._position_thread.start()
            
            return True
        except Exception as e:
            print(f"Failed to play audio: {e}")
            return False
    
    def pause(self):
        """Pause playback"""
        if not self.initialized or not self.is_playing:
            return False
            
        try:
            pygame.mixer.music.pause()
            self.is_playing = False
            return True
        except Exception as e:
            print(f"Failed to pause audio: {e}")
            return False
    
    def resume(self):
        """Resume playback"""
        if not self.initialized:
            return False
            
        try:
            pygame.mixer.music.unpause()
            self.is_playing = True
            return True
        except Exception as e:
            print(f"Failed to resume audio: {e}")
            return False
    
    def stop(self):
        """Stop playback"""
        if not self.initialized:
            return False
        
        # Stop position tracking
        self._stop_flag.set()
        if self._position_thread and self._position_thread.is_alive():
            self._position_thread.join(1.0)  # Wait up to 1 second
        
        try:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.position = 0
            return True
        except Exception as e:
            print(f"Failed to stop audio: {e}")
            return False
    
    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)"""
        if not self.initialized:
            return False
            
        try:
            # Constrain volume between 0 and 1
            self.volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(self.volume)
            return True
        except Exception as e:
            print(f"Failed to set volume: {e}")
            return False
    
    def _track_position(self):
        """Track the current playback position"""
        while not self._stop_flag.is_set():
            try:
                # Check if music is still playing
                if not pygame.mixer.music.get_busy():
                    # Music finished, trigger callback
                    if self.update_callback:
                        self.update_callback('finished')
                    self.is_playing = False
                    break
                
                # Update position (approximate)
                self.position += 0.1
                
                # Notify subscribers
                if self.update_callback:
                    self.update_callback('position_update')
                    
            except Exception as e:
                print(f"Error in position tracking: {e}")
                
            time.sleep(0.1)  # Update every 100ms
    
    def get_position(self):
        """Get current position in seconds"""
        return self.position
    
    def set_update_callback(self, callback):
        """Set callback for position updates and playback completion"""
        self.update_callback = callback