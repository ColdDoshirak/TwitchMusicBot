import os
import json
import time
import webbrowser
import tempfile
import threading
import shutil
from urllib.parse import urlparse, parse_qs

try:
    from yandex_music import Client
    HAS_YANDEX_MUSIC = True
except ImportError:
    print("Yandex Music API not installed.")
    HAS_YANDEX_MUSIC = False

class YandexMusicAPI:
    """Helper class for Yandex Music API operations"""
    
    def __init__(self):
        self.client = None
        self.is_authorized = False
        self.token = None
        self.token_file = "yandex_token.json"
        self.temp_dir = os.path.join(tempfile.gettempdir(), "yandex_music_bot")
        
        # Создаем временную папку, если её нет
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            
        self.load_token()
    
    def load_token(self):
        """Load token from file if available"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.token = data.get('token', None)
                    if self.token:
                        self.authorize(self.token)
        except Exception as e:
            print(f"Error loading Yandex Music token: {e}")
    
    def save_token(self):
        """Save token to file"""
        try:
            with open(self.token_file, 'w') as f:
                json.dump({'token': self.token}, f)
        except Exception as e:
            print(f"Error saving Yandex Music token: {e}")
    
    def authorize(self, token):
        """Authorize with Yandex Music using token"""
        if not HAS_YANDEX_MUSIC:
            print("Yandex Music API not installed")
            return False
        
        try:
            self.token = token
            self.client = Client(token).init()
            self.is_authorized = True
            self.save_token()
            return True
        except Exception as e:
            print(f"Yandex Music authorization failed: {e}")
            self.is_authorized = False
            return False
    
    def open_auth_page(self):
        """Open Yandex OAuth page in browser"""
        auth_url = "https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d"
        try:
            webbrowser.open(auth_url)
            return True
        except Exception as e:
            print(f"Failed to open auth page: {e}")
            return False
    
    def extract_token_from_url(self, url):
        """Extract token from redirect URL"""
        try:
            if "#access_token=" in url:
                token_part = url.split("#access_token=")[1]
                token = token_part.split("&")[0]
                return token
            return None
        except Exception as e:
            print(f"Error extracting token: {e}")
            return None
    
    def get_user_info(self):
        """Get user info to test connection"""
        if not self.is_authorized:
            return None
        
        try:
            return self.client.me
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None
    
    def search_track(self, query, limit=10):
        """Search tracks by query"""
        if not self.is_authorized:
            return []
        
        try:
            result = self.client.search(query, type_="track")
            if result and result.tracks and result.tracks.results:
                return result.tracks.results[:limit]
            return []
        except Exception as e:
            print(f"Error searching tracks: {e}")
            return []
    
    def get_wave_tracks(self, count=1):
        """Get tracks from user's personal wave"""
        if not self.is_authorized:
            return []
        
        try:
            # Get station with ID "user:onyourwave"
            station_id = "user:onyourwave"
            
            # Get batch of tracks from personal wave
            station_tracks = self.client.rotor_station_tracks(station_id)
            
            # Preprocess tracks to extract required info
            tracks = []
            for batch in station_tracks.sequence:
                if len(tracks) >= count:
                    break
                    
                track = batch.track
                if not track:
                    continue
                    
                # Extract artists
                artists = [artist.name for artist in track.artists] if track.artists else ["Unknown Artist"]
                
                # Extract album info
                album_id = track.albums[0].id if track.albums else None
                
                tracks.append({
                    'id': track.id,
                    'album_id': album_id,
                    'title': track.title,
                    'artists': artists,
                    'duration': track.duration_ms / 1000,  # Convert to seconds
                })
            
            return tracks[:count]
        except Exception as e:
            print(f"Error getting wave tracks: {e}")
            
            # Alternative approach using stations list
            try:
                print("Trying alternative method to get My Wave tracks...")
                # Get user stations
                stations = self.client.rotor_stations_list()
                
                # Find "Моя волна" station
                wave_station = None
                for station in stations:
                    if station.id.type == 'personal-station' and station.id.tag == 'playlistOfTheDay':
                        wave_station = station
                        break
                
                if not wave_station:
                    print("Could not find My Wave station")
                    return []
                
                # Get tracks from the station
                batch = self.client.rotor_station_tracks(
                    station=wave_station.id.station_id,
                    settings2=wave_station.id
                )
                
                # Process tracks
                tracks = []
                for sequence_item in batch.sequence:
                    if len(tracks) >= count:
                        break
                        
                    track = sequence_item.track
                    if not track:
                        continue
                        
                    # Extract artists
                    artists = [artist.name for artist in track.artists] if track.artists else ["Unknown Artist"]
                    
                    # Extract album info
                    album_id = track.albums[0].id if track.albums else None
                    
                    tracks.append({
                        'id': track.id,
                        'album_id': album_id,
                        'title': track.title,
                        'artists': artists,
                        'duration': track.duration_ms / 1000,  # Convert to seconds
                    })
                
                return tracks[:count]
                
            except Exception as backup_error:
                print(f"Alternative method also failed: {backup_error}")
                return []
    
    def download_track(self, track_info):
        """Download a track and return the local path"""
        if not self.is_authorized:
            print("Not authorized to download tracks")
            return None
            
        try:
            track_id = track_info['id']
            album_id = track_info.get('album_id')
            
            print(f"Starting download of track ID: {track_id}")
            
            # Создаем имя файла на основе информации о треке
            artists_str = "_".join(track_info.get('artists', ['Unknown']))
            title = track_info.get('title', 'Unknown')
            filename = f"{artists_str} - {title}.mp3"
            # Заменяем недопустимые символы для файловой системы
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                filename = filename.replace(char, '_')
            
            # Путь к локальному файлу
            local_path = os.path.join(self.temp_dir, filename)
            
            # Если файл уже скачан, просто возвращаем путь
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                print(f"Using cached track: {local_path}")
                return local_path
            
            # Получаем трек по ID
            track = self.client.tracks(track_id)[0]
            
            # Скачиваем трек
            print(f"Starting download of {track.title} to {local_path}")
            track.download(local_path, bitrate_in_kbps=320)
            
            # Проверяем, что файл успешно скачался
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                print(f"Successfully downloaded track to {local_path}, size: {os.path.getsize(local_path)} bytes")
                return local_path
            else:
                print("Failed to download track: file not created or empty")
                return None
                
        except Exception as e:
            print(f"Error downloading track: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def clean_temp_directory(self, max_age_hours=24):
        """Очистить временную директорию от старых файлов"""
        try:
            current_time = time.time()
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                if os.path.isfile(file_path):
                    # Проверяем возраст файла
                    file_age_hours = (current_time - os.path.getmtime(file_path)) / 3600
                    if file_age_hours > max_age_hours:
                        os.remove(file_path)
                        print(f"Deleted old file: {filename}")
        except Exception as e:
            print(f"Error cleaning temp directory: {e}")
            
    def download_track_async(self, track_info, callback=None):
        """Скачать трек асинхронно и вызвать callback с путем к файлу"""
        def download_and_callback():
            path = self.download_track(track_info)
            if callback and callable(callback):
                callback(path)
        
        # Запускаем загрузку в отдельном потоке
        thread = threading.Thread(target=download_and_callback, daemon=True)
        thread.start()
        return thread