import json
import requests
import re
import time
import urllib.request
import urllib.parse
import webbrowser
import random
import os
import subprocess
import tempfile

# Пытаемся импортировать pytube, но также настраиваем альтернативное получение данных
try:
    from pytube import YouTube, Search, extract
    HAS_PYTUBE = True
except ImportError:
    HAS_PYTUBE = False

# Пытаемся импортировать yt-dlp как более надежную альтернативу
try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False

# Импортируем наш модуль для работы с Yandex Music
from yandex_music_api import YandexMusicAPI

# Добавим функцию для получения экземпляра YandexMusicAPI

_yandex_music_api_instance = None

def get_yandex_music_api():
    """Get singleton instance of YandexMusicAPI"""
    global _yandex_music_api_instance
    if _yandex_music_api_instance is None:
        from yandex_music_api import YandexMusicAPI
        _yandex_music_api_instance = YandexMusicAPI()
    return _yandex_music_api_instance

class SongRequest:
    def __init__(self, video_id, title, requester, duration, source="youtube", track_info=None):
        self.video_id = video_id
        self.title = title
        self.requester = requester
        self.duration = duration
        self.request_time = time.time()
        self.source = source  # "youtube" или "yandex"
        self.track_info = track_info  # Дополнительная информация для треков Yandex Music
        
    def __str__(self):
        return f"{self.title} (запрошено: {self.requester})"

class MusicPlayer:
    def __init__(self, message_callback=None, config_manager=None):
        self.message_callback = message_callback
        self.config_manager = config_manager
        self.queue = []
        self.current_song = None
        self.volume = 50  # Default volume (0-100)
        self.is_playing = False
        self.youtube_player = None
        self.yandex_player = None
        self.player_initialized = False
        self.update_queue_callback = None
        
        # Инициализация Yandex Music API
        self.yandex_music = get_yandex_music_api()
        
        # Load auto_play_from_wave setting from config
        self.auto_play_from_wave = False  # Default value
        if config_manager:
            try:
                yandex_config = config_manager.get_yandex_music_config()
                self.auto_play_from_wave = yandex_config.get("auto_play_from_wave", False)
            except Exception as e:
                print(f"Error loading Yandex Music settings: {e}")
        
        # Очистка временной папки от старых файлов при запуске
        self.yandex_music.clean_temp_directory()
                
    def extract_youtube_id(self, url):
        """Extract YouTube video ID from a URL or search term."""
        # Check if it's a URL
        youtube_regex = (
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?\n\r]{11})')
        
        match = re.match(youtube_regex, url)
        if match:
            return match.group(6)  # Group 6 is the video ID
        
        # Check if it's just a video ID
        if re.match(r'^[A-Za-z0-9_-]{11}$', url):
            return url
            
        return None  # Not a URL or video ID
        
    def search_youtube(self, query):
        """Search YouTube for a query and return the top result."""
        # Первый метод: используем yt-dlp (более надежный)
        if HAS_YT_DLP:
            try:
                ydl_opts = {
                    'format': 'bestaudio',
                    'quiet': True,
                    'no_warnings': True,
                    'default_search': 'ytsearch1:',
                    'noplaylist': True,
                    'extract_flat': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f'ytsearch1:{query}', download=False)
                    if 'entries' in info and len(info['entries']) > 0:
                        entry = info['entries'][0]
                        return {
                            'id': entry['id'],
                            'title': entry['title'],
                            'duration': entry.get('duration', 180)  # Если длительность недоступна, используем стандартные 3 минуты
                        }
            except Exception as e:
                print(f"Error searching with yt-dlp: {e}")
                # Fallback to pytube
                
        # Второй метод: используем pytube
        if HAS_PYTUBE:
            try:
                # Perform a search using pytube
                search_results = Search(query).results
                
                if not search_results:
                    return None
                    
                # Get the top result
                video = search_results[0]
                
                # Return video info
                return {
                    'id': video.video_id,
                    'title': video.title,
                    'duration': video.length
                }
                
            except Exception as e:
                print(f"Error searching YouTube with pytube: {e}")
                
        # Третий метод: используем YouTube API через веб-запрос (это не требует API ключа, но менее надежно)
        try:
            # Простой поиск через URL
            query_string = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={query_string}"
            
            # Получаем HTML страницы
            response = requests.get(url)
            html = response.text
            
            # Ищем ID видео
            video_ids = re.findall(r'"videoId":"([^"]+)"', html)
            
            if not video_ids:
                return None
            
            # Берем первый результат
            video_id = video_ids[0]
            
            # Получаем информацию о видео
            video_info = self._get_minimal_video_info(video_id)
            return video_info
            
        except Exception as e:
            print(f"Error with fallback YouTube search: {e}")
            return None
            
    def _get_minimal_video_info(self, video_id, url=None):
        """Get minimal video info without downloading."""
        # Construct URL if not provided
        if url is None:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
        # Метод 1: использовать yt-dlp (наиболее надежный)
        if HAS_YT_DLP:
            try:
                ydl_opts = {
                    'format': 'bestaudio',
                    'quiet': True,
                    'no_warnings': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return {
                        'id': video_id,
                        'title': info.get('title', f"YouTube Video {video_id}"),
                        'duration': info.get('duration', 180)  # Если длительность не найдена, 3 минуты
                    }
            except Exception as e:
                print(f"Error getting video info with yt-dlp: {e}")
                # Continue to fallbacks
                
        # Метод 2: использовать pytube
        if HAS_PYTUBE:
            try:
                yt = YouTube(url)
                return {
                    'id': video_id,
                    'title': yt.title,
                    'duration': yt.length
                }
                
            except Exception as e:
                print(f"Error getting video info with pytube: {e}")
                # Continue to fallbacks
                
        # Метод 3: получить информацию через API без ключа
        try:
            # Запрашиваем JSON с базовыми метаданными с YouTube
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url)
            
            if response.status_code == 200:
                data = response.json()
                title = data.get('title', f"YouTube Video {video_id}")
                
                # У oEmbed нет длительности, поэтому используем стандартную
                return {
                    'id': video_id,
                    'title': title,
                    'duration': 180  # По умолчанию 3 минуты
                }
        except Exception as e:
            print(f"Error getting video info via oEmbed: {e}")
            
        # Последнее средство - просто использовать ID как заголовок
        return {
            'id': video_id,
            'title': f"YouTube Video {video_id}",
            'duration': 180  # По умолчанию 3 минуты
        }
    
    def search_yandex_music(self, query):
        """Поиск трека в Yandex Music."""
        if not self.yandex_music.is_authorized:
            return None, "Необходима авторизация в Yandex Music"
        
        try:
            # Поиск треков по запросу
            tracks = self.yandex_music.search_track(query)
            if not tracks or len(tracks) == 0:
                return None, "Треки не найдены"
            
            # Берем первый результат
            track = tracks[0]
            
            # Получаем ID трека и альбома
            track_id = track.id
            album_id = track.albums[0].id if track.albums else None
            
            # Собираем информацию о треке
            artists = ", ".join([artist.name for artist in track.artists]) if track.artists else "Unknown Artist"
            title = f"{artists} - {track.title}"
            
            # Получаем полную информацию о треке
            track_info = {
                'id': track_id,
                'album_id': album_id,
                'title': title,
                'duration': track.duration_ms / 1000,  # в секундах
                'artists': artists
            }
            
            return track_info, None
            
        except Exception as e:
            print(f"Error searching Yandex Music: {e}")
            return None, f"Ошибка поиска в Yandex Music: {str(e)}"
            
    def add_to_queue(self, url_or_search, requester, source=None):
        """Add a song to the queue from a URL or search term."""
        try:
            # Определяем источник, если не указан явно
            if source is None:
                # Проверяем, если это URL Yandex Music
                if 'music.yandex' in url_or_search:
                    source = 'yandex'
                # Или если запрос начинается с 'ym:'
                elif url_or_search.startswith('ym:'):
                    source = 'yandex'
                    url_or_search = url_or_search[3:].strip()  # Убираем префикс
                else:
                    source = 'youtube'  # По умолчанию YouTube
            
            # Если это YouTube запрос, удаляем все последующие треки Yandex Music из очереди
            if source == 'youtube':
                self._remove_yandex_tracks_from_queue(preserve_current=True)

            # Обрабатываем запрос в зависимости от источника
            if source == 'yandex':
                # Проверяем авторизацию
                if not self.yandex_music.is_authorized:
                    return False, "Для использования Yandex Music необходимо авторизоваться. Используйте настройки."
                
                # Ищем трек в Yandex Music
                track_info, error = self.search_yandex_music(url_or_search)
                if error:
                    return False, error
                
                # Создаем запрос на песню
                song = SongRequest(
                    video_id=f"{track_info['album_id']}:{track_info['id']}",
                    title=track_info['title'],
                    requester=requester,
                    duration=track_info['duration'],
                    source='yandex',
                    track_info=track_info
                )
                
                # Добавляем в очередь
                return self.add_song(song)
                
            else:
                # Стандартный поиск YouTube
                video_id = self.extract_youtube_id(url_or_search)
                
                # If not a URL, search for it
                if not video_id:
                    search_result = self.search_youtube(url_or_search)
                    if not search_result:
                        return False, "Не найдено результатов по вашему запросу."
                    
                    video_id = search_result['id']
                    title = search_result['title']
                    duration = search_result['duration']
                else:
                    # Use minimal info for direct URLs
                    video_info = self._get_minimal_video_info(video_id, url_or_search)
                    title = video_info['title']
                    duration = video_info['duration']
                    
                # Create song request and add to queue
                song = SongRequest(video_id, title, requester, duration, source="youtube")
                return self.add_song(song)
            
        except Exception as e:
            # Print to console but don't send to chat
            print(f"Error adding to queue: {e}")
            return False, f"Ошибка при добавлении песни в очередь: {str(e)}"

    def _remove_yandex_tracks_from_queue(self, preserve_current=True):
        """Удаляет все треки Yandex Music из очереди"""
        # Удаляем из очереди все треки Yandex Music (но не текущий трек)
        self.queue = [song for song in self.queue if song.source != 'yandex']
        
        # Уведомляем о изменении очереди
        if self.message_callback:
            self.message_callback("Очередь очищена от треков Yandex Music из-за нового YouTube реквеста")
        
        # Обновляем отображение очереди
        if self.update_queue_callback:
            self.update_queue_callback()
        
        return True

    def ensure_queue_has_tracks(self, min_tracks=25, max_tracks=25):
        """Проверяет наличие достаточного количества треков в очереди и добавляет из Моей Волны при необходимости"""
        # Если отключено автоматическое добавление из волны, ничего не делаем
        if not self.auto_play_from_wave:
            return False
        
        # Если уже есть достаточно треков, ничего не делаем
        if len(self.queue) >= min_tracks:
            return True
        
        # Если в очереди есть треки YouTube, не добавляем из Моей Волны
        if any(song.source == 'youtube' for song in self.queue):
            return False
        
        # Если авторизация в Yandex Music отсутствует, ничего не делаем
        if not self.yandex_music.is_authorized:
            return False
        
        # Сколько треков нужно добавить
        tracks_to_add = max_tracks - len(self.queue)
        
        try:
            # Добавляем треки из Моей Волны
            success, message = self.add_yandex_wave_tracks(tracks_to_add)
            return success
        except Exception as e:
            print(f"Error ensuring queue has tracks: {e}")
            return False

    def add_yandex_wave_tracks(self, count=25):  # По умолчанию добавляем 5 треков
        """Добавляет треки из Моей Волны в очередь."""
        try:
            if not self.yandex_music.is_authorized:
                return False, "Для использования Моей Волны необходимо авторизоваться в Yandex Music"
                
            # Получаем треки из Моей Волны
            wave_tracks = self.yandex_music.get_wave_tracks(count)
            
            if not wave_tracks or len(wave_tracks) == 0:
                return False, "Не удалось получить треки из Моей Волны"
                
            tracks_added = 0
            for track in wave_tracks:
                # Создаем запрос на песню
                song = SongRequest(
                    video_id=f"{track['album_id']}:{track['id']}",
                    title=f"{' & '.join(track['artists'])} - {track['title']}",
                    requester="Моя Волна",
                    duration=track['duration'],
                    source='yandex',
                    track_info=track
                )
                
                # Добавляем в очередь
                self.add_song(song)
                tracks_added += 1
                
            # Меняем сообщение в зависимости от количества добавленных треков
            if tracks_added == 1:
                return True, f"Добавлен 1 трек из Моей Волны"
            else:
                return True, f"Добавлено {tracks_added} треков из Моей Волны"
                
        except Exception as e:
            print(f"Error adding wave tracks: {e}")
            return False, f"Ошибка при добавлении треков из Моей Волны: {str(e)}"

    def initialize_player(self, player_frame=None, update_queue_callback=None):
        """Initialize the player interface."""
        print(f"Initializing player with frame: {player_frame}, callback: {update_queue_callback}")
        self.player_frame = player_frame
        self.update_queue_callback = update_queue_callback
        self.player_initialized = True
        
        # If we have songs in queue, start playing
        if not self.is_playing and self.queue:
            print(f"We have {len(self.queue)} songs in queue, starting playback")
            self._play_next()
        else:
            print(f"Queue empty or already playing. Queue size: {len(self.queue)}, is_playing: {self.is_playing}")
            
    def update_now_playing(self, song):
        """Update player with current song information"""
        result = False
        
        try:
            # Update appropriate player based on source
            if song:
                if song.source == 'yandex' and hasattr(self, 'yandex_player') and self.yandex_player:
                    # Update Yandex player, hide YouTube player
                    result = self.yandex_player.update_now_playing(song)
                    if hasattr(self, 'youtube_player') and self.youtube_player:
                        self.youtube_player.update_now_playing(None)
                else:
                    # Update YouTube player, hide Yandex player
                    if hasattr(self, 'youtube_player') and self.youtube_player:
                        result = self.youtube_player.update_now_playing(song)
                    if hasattr(self, 'yandex_player') and self.yandex_player:
                        self.yandex_player.update_now_playing(None)
            else:
                # Clear both players
                if hasattr(self, 'youtube_player') and self.youtube_player:
                    self.youtube_player.update_now_playing(None)
                if hasattr(self, 'yandex_player') and self.yandex_player:
                    self.yandex_player.update_now_playing(None)
        except Exception as e:
            print(f"Error updating players: {e}")
        
        return result

    def skip_song(self):
        """Skip to the next song in the queue."""
        # Stop the current song
        if self.current_song:
            old_song = self.current_song.title
            
            # Если в очереди больше нет песен или мало песен, проверяем возможность добавления из Моей Волны
            if len(self.queue) < 3 and self.auto_play_from_wave and self.yandex_music.is_authorized:
                # Пополняем очередь, только если нет YouTube реквестов
                if not any(song.source == 'youtube' for song in self.queue):
                    self.ensure_queue_has_tracks(min_tracks=25, max_tracks=25)
            
            # Если в очереди больше нет песен, просто остановим текущую
            if not self.queue:
                self.current_song = None
                self.is_playing = False
                
                # Обновляем плеер, что воспроизведение закончилось
                if self.player_frame:
                    try:
                        self.player_frame.update_now_playing(None)
                    except Exception as e:
                        print(f"Error updating player: {e}")
                    
                    # Явно посылаем команду очистить видео в браузерный плеер
                    try:
                        if hasattr(self.player_frame, 'pending_command'):
                            self.player_frame.pending_command = {"command": "clear"}
                    except Exception as e:
                        print(f"Error sending clear command: {e}")
                
                if self.message_callback:
                    self.message_callback(f"Пропущено: {old_song}. Очередь пуста.")
                    
                # Обновляем отображение очереди
                if self.update_queue_callback:
                    try:
                        self.update_queue_callback()
                    except Exception as e:
                        print(f"Error updating queue display: {e}")
                    
                return True, f"Пропущено: {old_song}. Очередь пуста."
                
            # Если есть песни в очереди, воспроизводим следующую
            else:
                # Play the next song
                if self._play_next():
                    return True, f"Пропущено: {old_song}"
                else:
                    return False, "Ошибка воспроизведения следующей песни"
        else:
            return False, "Нет текущей песни"
            
    def clear_queue(self):
        """Clear the song queue."""
        self.queue = []
        
        # Update queue display
        if self.update_queue_callback:
            self.update_queue_callback()
            
        return True, "Очередь очищена"
        
    def toggle_playback(self):
        """Toggle play/pause of the current song."""
        if not self.current_song:
            # Попробуем взять песни из Моей Волны, если включена эта функция
            if not self.queue and self.auto_play_from_wave and self.yandex_music.is_authorized:
                success, message = self.add_yandex_wave_tracks()
                if success:
                    return True, message
            
            if self.queue:
                # Start playing if there are songs in the queue
                return self._play_next(), "Starting playback"
            else:
                return False, "Очередь пуста"
        
        # Toggle play state
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            return True, f"Воспроизведение: {self.current_song.title}"
        else:
            return True, f"Пауза: {self.current_song.title}"
    
    def toggle_auto_play_from_wave(self):
        """Включает/выключает автоматическое воспроизведение из Моей Волны."""
        self.auto_play_from_wave = not self.auto_play_from_wave
        
        # Save the setting to config if config_manager is available
        if hasattr(self, 'config_manager') and self.config_manager:
            try:
                self.config_manager.set_yandex_auto_wave(self.auto_play_from_wave)
            except Exception as e:
                print(f"Error saving auto_wave setting: {e}")
        
        if self.auto_play_from_wave:
            return True, "Автоматическое добавление треков из Моей Волны включено"
        else:
            return True, "Автоматическое добавление треков из Моей Волны выключено"
            
    def _play_next(self):
        """Play the next song in the queue."""
        try:
            if not self.queue:
                print("Queue is empty, nothing to play")
                self.current_song = None
                self.is_playing = False
                
                # Update player if available
                if hasattr(self, 'player_frame') and self.player_frame:
                    try:
                        self.player_frame.update_now_playing(None)
                    except Exception as e:
                        print(f"Error updating player frame: {e}")
                
                return False
                
            # Get the next song
            self.current_song = self.queue.pop(0)
            print(f"Now playing: '{self.current_song.title}' (Source: {self.current_song.source})")
            self.is_playing = True
            
            # Update player if available
            if hasattr(self, 'player_frame') and self.player_frame:
                try:
                    success = self.player_frame.update_now_playing(self.current_song)
                    print(f"Player update result: {success}")
                    if not success:
                        print("Player failed to update, trying next song")
                        return self._play_next()
                except Exception as e:
                    print(f"Error updating player frame: {e}")
                    # Try next song in case of error
                    return self._play_next()
            
            # Update queue display if callback is set
            if self.update_queue_callback:
                self.update_queue_callback()
                
            return True
        except Exception as e:
            print(f"Error in _play_next: {e}")
            return False

    def set_volume(self, volume):
        """Set player volume (0-100)"""
        try:
            # Update internal volume value
            self.volume = int(volume)
            
            # Make sure it's within bounds
            self.volume = max(0, min(100, self.volume))
            
            # If we have a player frame, update it
            if hasattr(self, 'player_frame') and self.player_frame:
                print(f"Setting volume to {self.volume}% in player frame")
                success = self.player_frame.set_volume(self.volume)
                
                # If we have config manager, save the volume setting
                if hasattr(self, 'config_manager') and self.config_manager:
                    self.config_manager.set_player_volume(self.volume)
                    self.config_manager.save_config()
                    print("Volume setting saved to configuration from music player")
                    
                return success
            return False
        except Exception as e:
            print(f"Error setting volume in music player: {e}")
            return False
            
    def get_queue(self):
        """Get a copy of the current queue."""
        # Return a copy to avoid threading issues
        return list(self.queue)
        
    def get_current_song(self):
        """Get the currently playing song."""
        return self.current_song

    def wrong_song(self, requester):
        """Remove the last song requested by the user from the queue."""
        # Проверяем всю очередь на предмет песен этого пользователя, начиная с конца
        for i in range(len(self.queue) - 1, -1, -1):
            if self.queue[i].requester.lower() == requester.lower():
                song = self.queue.pop(i)
                
                # Update queue display
                if self.update_queue_callback:
                    self.update_queue_callback()
                    
                return True, f"Удалена песня: {song.title}"
        
        # Если не нашли ни одной песни этого пользователя
        return False, "В очереди нет песен от вас."

    def set_yandex_music_token(self, token):
        """Set Yandex Music API token."""
        success = self.yandex_music.authorize(token)
        if success:
            return True, "Yandex Music API token установлен успешно"
        else:
            return False, "Ошибка авторизации в Yandex Music"

    def add_song(self, song):
        """Add a song to the queue."""
        try:
            self.queue.append(song)
            print(f"Song added to queue: '{song.title}' from {song.source}")
            
            # Update queue display if callback is set
            if self.update_queue_callback:
                self.update_queue_callback()
            
            # Send notification
            if self.message_callback:
                self.message_callback(f"Added to queue: {song.title}")
                
            # Start playing if nothing is currently playing
            if not self.is_playing and self.player_initialized:
                print("Queue was empty, starting playback...")
                self._play_next()
            
            return True, f"Added to queue: {song.title}"
        except Exception as e:
            print(f"Error adding song to queue: {e}")
            return False, f"Error adding song: {str(e)}"

    def create_song_from_youtube_url(self, url, requester="Manual"):
        """Create a Song object from a YouTube URL."""
        try:
            print(f"Creating song from YouTube URL: {url}")
            # Extract video id
            from urllib.parse import urlparse, parse_qs
            
            # Patterns like youtube.com/watch?v=VIDEO_ID
            parsed_url = urlparse(url)
            if parsed_url.netloc in ['youtube.com', 'www.youtube.com']:
                # Standard YouTube URL
                query = parse_qs(parsed_url.query)
                video_id = query.get('v', [None])[0]
            elif parsed_url.netloc == 'youtu.be':
                # Shortened URL
                video_id = parsed_url.path.lstrip('/')
            else:
                video_id = None
                
            print(f"Extracted video ID: {video_id}")
                
            if not video_id:
                print("Could not extract video ID")
                return None, "Invalid YouTube URL format"
            
            # Get video metadata
            video_info = self._get_video_info(video_id)
            if not video_info:
                print("Could not get video info")
                return None, "Failed to get video information"
            
            # Create Song object
            song = Song(
                title=video_info['title'],
                source='youtube',
                video_id=video_id,
                duration=video_info.get('duration', 0),
                thumbnail=video_info.get('thumbnail', ''),
                requester=requester
            )
            print(f"Created song: {song.title}, ID: {song.video_id}")
            
            return song, None
            
        except Exception as e:
            print(f"Error creating song from YouTube: {e}")
            import traceback
            traceback.print_exc()
            return None, str(e)