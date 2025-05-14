import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import os
import sys
import socket
import http.server
import socketserver
import subprocess
import tempfile
import threading
import webbrowser
import json
import urllib.parse
import io

class YouTubePlayerFrame(ctk.CTkFrame):
    def __init__(self, master, music_player, config_manager=None, skip_callback=None, **kwargs):
        super().__init__(master, **kwargs)  # Передаем только стандартные параметры в родительский класс
        
        # Сохраняем пользовательские параметры
        self.music_player = music_player
        self.config_manager = config_manager
        self.skip_callback = skip_callback  # Сохраняем колбэк пропуска песни
        
        self.master = master
        self.current_video_id = None
        self.is_playing = False
        
        # Для аудиофайлов
        self.current_audio_src = None
        self.current_audio_info = None
        
        # Загружаем сохраненную громкость из конфига
        self.volume = 50  # Значение по умолчанию
        if self.config_manager:
            self.volume = self.config_manager.get_player_volume()
            print(f"Loaded volume from config: {self.volume}")
        
        # Храним ссылки на все изображения, чтобы избежать сборки мусора
        self.image_references = {}
        
        # Добавим placeholder-изображение для случаев ошибок
        self._create_placeholder_image()
        
        # Player window process
        self.player_process = None
        self.server_port = self._find_free_port()
        self.server = None
        self.server_thread = None
        self.waiting_for_player = False
        
        # Create the HTML file for the player
        self.html_path = self._create_player_html()
        
        # Start server for player communication
        self._start_server()
        
        # Create the player UI
        self._create_ui()
        
        # Safety timer for automatic playback and advancement
        self.safety_timer = None
        
        # Pending command for the player
        self.pending_command = {"command": "none"}
        
        # Добавляем поле для отслеживания состояния браузера
        self.browser_launched = False
    
    def _create_placeholder_image(self):
        """Create a placeholder image for error cases."""
        try:
            # Создаем простое изображение 640x360 с градиентом
            img = Image.new('RGB', (640, 360), color='#333333')
            
            # Добавляем текст на изображение
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            
            # Попытка использовать системный шрифт, с резервным вариантом
            try:
                font = ImageFont.truetype("Arial", 24)
            except IOError:
                font = ImageFont.load_default()
                
            text = "Thumbnail not available"
            text_width, text_height = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else (200, 30)
            
            # Центрируем текст
            position = ((640 - text_width) // 2, (360 - text_height) // 2)
            
            # Добавляем текст
            draw.text(position, text, fill="#FFFFFF", font=font)
            
            # Создаем CTkImage
            self.placeholder_image = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 360))
            
            # Добавляем в словарь ссылок
            self.image_references["placeholder"] = self.placeholder_image
            
        except Exception as e:
            print(f"Error creating placeholder image: {e}")
            self.placeholder_image = None
    
    def _find_free_port(self):
        """Find a free port to use for the server."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port
        
    def _create_ui(self):
        """Create the player UI elements."""
        # Main player area
        self.player_area = ctk.CTkFrame(self)
        self.player_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Video info display
        self.title_label = ctk.CTkLabel(self.player_area, text="No video playing", 
                                       font=("Arial", 14, "bold"), wraplength=500)
        self.title_label.pack(pady=(10, 5))
        
        # Player frame for thumbnail
        self.player_frame = ctk.CTkFrame(self.player_area, width=640, height=360)
        self.player_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.player_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Thumbnail label
        self.thumbnail_label = ctk.CTkLabel(self.player_frame, text="Ready to play videos", image=None)
        self.thumbnail_label.pack(fill=tk.BOTH, expand=True)
        
        # Now Playing info
        self.now_playing_label = ctk.CTkLabel(self.player_area, text="", font=("Arial", 12))
        self.now_playing_label.pack(pady=5)
        
        # Controls frame
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Play/Pause button
        self.play_pause_btn = ctk.CTkButton(self.controls_frame, text="Play", command=self._toggle_play)
        self.play_pause_btn.pack(side=tk.LEFT, padx=5)
        
        # Skip button
        self.skip_btn = ctk.CTkButton(self.controls_frame, text="Skip", command=self._skip_song)
        self.skip_btn.pack(side=tk.LEFT, padx=5)
        
        # Volume slider
        self.volume_label = ctk.CTkLabel(self.controls_frame, text="Volume:")
        self.volume_label.pack(side=tk.LEFT, padx=(15, 5))
        
        self.volume_slider = ctk.CTkSlider(self.controls_frame, from_=0, to=100, number_of_steps=100,
                                          command=self._on_volume_change)
        self.volume_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.volume_slider.set(self.volume)
        
        # Open in Browser button (as fallback)
        self.open_browser_btn = ctk.CTkButton(self.controls_frame, text="Open in Browser", 
                                             command=self._open_in_browser)
        self.open_browser_btn.pack(side=tk.RIGHT, padx=5)
        
        # Launch Player Window button
        self.launch_player_btn = ctk.CTkButton(self.controls_frame, text="Player Window", 
                                              command=self._launch_player_window)
        self.launch_player_btn.pack(side=tk.RIGHT, padx=5)
        
        # Set this frame as the player frame for the music player
        self.music_player.initialize_player(self, self.update_queue_display)
        
    def _create_player_html(self):
        """Create an HTML file for the media player that supports both YouTube and audio files."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Music Bot Player</title>
            <style>
                body {{ 
                    margin: 0; 
                    padding: 0; 
                    background-color: #000; 
                    overflow: hidden;
                    font-family: Arial, sans-serif;
                }}
                #player {{ 
                    width: 100%; 
                    height: 100vh; 
                }}
                #audio-player {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    color: white;
                    background: #000;
                    z-index: 100;
                    display: none;
                }}
                #audio-player.active {{
                    display: flex;
                }}
                .cover-art {{
                    width: 300px;
                    height: 300px;
                    background-color: #FFCC00;
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-size: 24px;
                    color: black;
                    overflow: hidden;
                    position: relative;
                }}
                .cover-art img {{
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }}
                .track-info {{
                    text-align: center;
                    margin-bottom: 20px;
                    width: 80%;
                    max-width: 600px;
                }}
                .track-title {{
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .track-artist {{
                    font-size: 18px;
                    opacity: 0.8;
                }}
                .audio-controls {{
                    display: flex;
                    justify-content: center;
                    gap: 15px;
                    margin-top: 20px;
                }}
                .audio-control-btn {{
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    min-width: 100px;
                }}
                #audio-progress {{
                    width: 80%;
                    max-width: 500px;
                    margin: 10px 0;
                }}
                #audio-volume {{
                    width: 200px;
                    margin: 10px 0;
                }}
                #controls {{
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    background: rgba(0,0,0,0.7);
                    color: white;
                    padding: 10px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    z-index: 1000;
                }}
                .control-button {{
                    background: #4CAF50;
                    border: none;
                    color: white;
                    padding: 5px 10px;
                    cursor: pointer;
                    border-radius: 3px;
                    margin: 0 5px;
                }}
                #status {{
                    margin-left: 10px;
                }}
                #song-info {{
                    flex-grow: 1;
                    text-align: center;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                #autoplay-overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0,0,0,0.85);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    z-index: 2000;
                    color: white;
                }}
                #autoplay-button {{
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 15px 30px;
                    font-size: 18px;
                    cursor: pointer;
                    border-radius: 4px;
                    margin-top: 20px;
                    transition: background 0.3s;
                }}
                #autoplay-button:hover {{
                    background: #3e8e41;
                }}
                .source-indicator {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: rgba(0,0,0,0.6);
                    color: white;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <!-- YouTube Player -->
            <div id="player"></div>
            
            <!-- Audio Player for Yandex Music -->
            <div id="audio-player">
                <div class="source-indicator">Yandex Music</div>
                <div class="cover-art" id="cover-container">
                    <div id="cover-placeholder">Yandex Music</div>
                    <img id="cover-image" style="display:none;">
                </div>
                <div class="track-info">
                    <div class="track-title" id="audio-title">Трек не выбран</div>
                    <div class="track-artist" id="audio-artist">Исполнитель</div>
                </div>
                <audio id="audio-element" preload="auto"></audio>
                <input type="range" id="audio-progress" min="0" max="100" value="0">
                <div class="time-display">
                    <span id="current-time">0:00</span> / <span id="total-time">0:00</span>
                </div>
                <div class="audio-controls">
                    <button class="audio-control-btn" id="audio-play-pause">Play</button>
                    <button class="audio-control-btn" id="audio-skip">Skip</button>
                </div>
                <div class="volume-control">
                    <label for="audio-volume">Громкость:</label>
                    <input type="range" id="audio-volume" min="0" max="100" value="{self.volume}">
                </div>
            </div>
            
            <!-- Оверлей для нажатия кнопки автовоспроизведения -->
            <div id="autoplay-overlay">
                <h2>Музыкальный плеер готов к работе</h2>
                <p>Для запуска автоматического воспроизведения нажмите кнопку ниже</p>
                <button id="autoplay-button" onclick="enableAutoplay()">Запустить воспроизведение</button>
            </div>
            
            <div id="controls">
                <div id="status">Ready</div>
                <div id="song-info">No song playing</div>
                <div>
                    <button class="control-button" onclick="skipSong()">Skip</button>
                </div>
            </div>
            
            <script>
                // Communication with the main app
                const PORT = {self.server_port};
                const BASE_URL = `http://localhost:${{PORT}}`;
                
                // Сохраняем настройку громкости, чтобы применить её сразу после инициализации
                let pendingVolume = {self.volume};
                let pendingVideoId = null;
                let pendingVideoTitle = null;
                let pendingAudioSrc = null;
                let pendingAudioInfo = null;
                let autoplayEnabled = false;
                let currentMediaType = null; // 'youtube' или 'audio'
                
                // Получаем элементы аудио-плеера
                const audioPlayer = document.getElementById('audio-player');
                const audioElement = document.getElementById('audio-element');
                const audioTitle = document.getElementById('audio-title');
                const audioArtist = document.getElementById('audio-artist');
                const audioProgress = document.getElementById('audio-progress');
                const audioVolume = document.getElementById('audio-volume');
                const audioPlayPause = document.getElementById('audio-play-pause');
                const audioSkip = document.getElementById('audio-skip');
                const currentTimeDisplay = document.getElementById('current-time');
                const totalTimeDisplay = document.getElementById('total-time');
                const coverImage = document.getElementById('cover-image');
                const coverPlaceholder = document.getElementById('cover-placeholder');
                
                // Настраиваем аудио-плеер
                function setupAudioPlayer() {{
                    // Обновление прогресса
                    audioElement.addEventListener('timeupdate', function() {{
                        if (audioElement.duration) {{
                            const percent = (audioElement.currentTime / audioElement.duration) * 100;
                            audioProgress.value = percent;
                            
                            // Обновляем отображение времени
                            currentTimeDisplay.textContent = formatTime(audioElement.currentTime);
                        }}
                    }});
                    
                    // При изменении ползунка прогресса
                    audioProgress.addEventListener('input', function() {{
                        const seekTime = (audioProgress.value / 100) * audioElement.duration;
                        audioElement.currentTime = seekTime;
                    }});
                    
                    // При изменении громкости
                    audioVolume.addEventListener('input', function() {{
                        const volume = audioVolume.value / 100;
                        audioElement.volume = volume;
                        pendingVolume = audioVolume.value;
                    }});
                    
                    // Кнопка Play/Pause
                    audioPlayPause.addEventListener('click', function() {{
                        if (audioElement.paused) {{
                            audioElement.play();
                            audioPlayPause.textContent = 'Pause';
                        }} else {{
                            audioElement.pause();
                            audioPlayPause.textContent = 'Play';
                        }}
                    }});
                    
                    // Кнопка Skip
                    audioSkip.addEventListener('click', skipSong);
                    
                    // При загрузке метаданных трека
                    audioElement.addEventListener('loadedmetadata', function() {{
                        totalTimeDisplay.textContent = formatTime(audioElement.duration);
                    }});
                    
                    // При окончании трека
                    audioElement.addEventListener('ended', function() {{
                        console.log('Audio ended, playing next song');
                        audioPlayPause.textContent = 'Play';
                        skipSong();
                    }});
                    
                    // Устанавливаем начальную громкость
                    audioVolume.value = pendingVolume;
                    audioElement.volume = pendingVolume / 100;
                }}
                
                // Форматирование времени в формат MM:SS
                function formatTime(seconds) {{
                    const min = Math.floor(seconds / 60);
                    const sec = Math.floor(seconds % 60);
                    return `${{min}}:${{sec < 10 ? '0' : ''}}${{sec}}`;
                }}
                
                // Показать аудио-плеер
                function showAudioPlayer() {{
                    audioPlayer.classList.add('active');
                    if (document.querySelector('#player iframe')) {{
                        document.querySelector('#player iframe').style.display = 'none';
                    }}
                    currentMediaType = 'audio';
                    console.log("Audio player activated");
                }}
                
                // Показать YouTube-плеер
                function showYouTubePlayer() {{
                    audioPlayer.classList.remove('active');
                    if (document.querySelector('#player iframe')) {{
                        document.querySelector('#player iframe').style.display = 'block';
                    }}
                    currentMediaType = 'youtube';
                    console.log("YouTube player activated");
                }}
                
                // Загрузить аудиофайл и начать воспроизведение
                function loadAudio(src, info) {{
                    console.log('Loading audio:', src, info);
                    
                    if (!autoplayEnabled) {{
                        pendingAudioSrc = src;
                        pendingAudioInfo = info;
                        document.getElementById('song-info').innerText = "Нажмите кнопку 'Запустить воспроизведение'";
                        return false;
                    }}
                    
                    showAudioPlayer();
                    
                    // Остановим YouTube плеер если он играет
                    if (player && typeof player.stopVideo === 'function') {{
                        player.stopVideo();
                    }}
                    
                    // Загружаем аудиофайл
                    audioElement.src = src;
                    
                    // Обновляем информацию о треке
                    if (info) {{
                        audioTitle.textContent = info.title || 'Неизвестный трек';
                        audioArtist.textContent = info.artist || 'Неизвестный исполнитель';
                        document.getElementById('song-info').innerText = `${{info.title}} - ${{info.artist}}`;
                        
                        // Обновляем обложку если есть
                        if (info.cover) {{
                            coverImage.src = info.cover;
                            coverImage.style.display = 'block';
                            coverPlaceholder.style.display = 'none';
                        }} else {{
                            coverImage.style.display = 'none';
                            coverPlaceholder.style.display = 'block';
                        }}
                    }}
                    
                    // Воспроизводим трек
                    audioElement.play()
                        .then(() => {{
                            audioPlayPause.textContent = 'Pause';
                            document.getElementById('status').innerText = "Now playing";
                        }})
                        .catch(e => {{
                            console.error('Error playing audio:', e);
                            document.getElementById('status').innerText = "Error: " + e;
                        }});
                    
                    return true;
                }}
                
                // Функция для разрешения автовоспроизведения
                function enableAutoplay() {{
                    console.log('Enabling autoplay');
                    
                    // Скрываем оверлей
                    document.getElementById('autoplay-overlay').style.display = 'none';
                    autoplayEnabled = true;
                    
                    // Настраиваем аудио-плеер
                    setupAudioPlayer();
                    
                    // Явно применяем громкость сразу после активации
                    if (player && player.setVolume) {{
                        player.setVolume(pendingVolume);
                        console.log(`Applied volume on autoplay enable: ${{pendingVolume}}`);
                        
                        // Убедимся, что звук не выключен
                        if (player.isMuted && player.isMuted()) {{
                            player.unMute();
                            console.log("Unmuted player");
                        }}
                    }}
                    
                    // Небольшая задержка перед проверкой контента
                    setTimeout(() => {{
                        // Проверяем, что у нас есть в очереди
                        if (pendingVideoId) {{
                            console.log('Loading pending video:', pendingVideoId);
                            loadVideo(pendingVideoId, pendingVideoTitle);
                            pendingVideoId = null;
                            pendingVideoTitle = null;
                        }} else if (pendingAudioSrc) {{
                            console.log('Loading pending audio:', pendingAudioSrc);
                            loadAudio(pendingAudioSrc, pendingAudioInfo);
                            pendingAudioSrc = null;
                            pendingAudioInfo = null;
                        }} else {{
                            // Иначе просто проверяем, есть ли текущее видео
                            checkForPendingMedia();
                        }}
                    }}, 300);
                }}
                
                // YouTube Player API
                var tag = document.createElement('script');
                tag.src = "https://www.youtube.com/iframe_api";
                var firstScriptTag = document.getElementsByTagName('script')[0];
                firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
                
                var player;
                function onYouTubeIframeAPIReady() {{
                    console.log('YouTube API ready');
                    player = new YT.Player('player', {{
                        height: '100%',
                        width: '100%',
                        videoId: '',
                        playerVars: {{
                            'autoplay': 0, // Начинаем без автовоспроизведения
                            'controls': 1,
                            'rel': 0,
                            'modestbranding': 1
                        }},
                        events: {{
                            'onReady': onPlayerReady,
                            'onStateChange': onPlayerStateChange,
                            'onError': onPlayerError
                        }}
                    }});
                }}
                
                function onPlayerReady(event) {{
                    console.log('Player ready');
                    document.getElementById('status').innerText = "Player ready";
                    
                    // Устанавливаем сохраненную громкость
                    if (pendingVolume) {{
                        player.setVolume(pendingVolume);
                        console.log(`Applied initial volume: ${{pendingVolume}}`);
                    }}
                    
                    // Notify main app that player is ready
                    fetch(`${{BASE_URL}}/player_ready`)
                        .catch(e => console.error('Error notifying ready:', e));
                    
                    // Check for pending media
                    setTimeout(() => {{
                        checkForPendingMedia();
                    }}, 500);
                }}
                
                function onPlayerStateChange(event) {{
                    // Check if video ended (0 = ended)
                    if (event.data === 0) {{
                        console.log('Video ended');
                        document.getElementById('status').innerText = "Video ended";
                        
                        // Notify main app
                        fetch(`${{BASE_URL}}/video_ended`)
                            .catch(e => console.error('Error notifying video ended:', e));
                    }}
                }}
                
                function onPlayerError(event) {{
                    console.log('Player error: ' + event.data);
                    document.getElementById('status').innerText = "Error: " + event.data;
                    
                    // Notify main app
                    fetch(`${{BASE_URL}}/player_error?code=${{event.data}}`)
                        .catch(e => console.error('Error notifying error:', e));
                }}
                
                function loadVideo(videoId, title = "Unknown Title") {{
                    console.log('Loading video:', videoId, title);
                    
                    if (player && player.loadVideoById) {{
                        if (autoplayEnabled) {{
                            console.log(`Loading video: ${{videoId}} with volume ${{pendingVolume}}`);
                            
                            // Проверяем громкость перед загрузкой видео
                            if (player.getVolume() != pendingVolume) {{
                                player.setVolume(pendingVolume);
                                console.log(`Re-applied volume before loading: ${{pendingVolume}}`);
                            }}
                            
                            // Убедимся, что звук не выключен
                            if (player.isMuted && player.isMuted()) {{
                                player.unMute();
                            }}
                            
                            // Показываем YouTube плеер
                            showYouTubePlayer();
                            
                            // Останавливаем аудио если играет
                            if (audioElement && !audioElement.paused) {{
                                audioElement.pause();
                                audioPlayPause.textContent = 'Play';
                            }}
                            
                            // Загружаем видео
                            player.loadVideoById(videoId);
                            document.getElementById('song-info').innerText = title;
                            document.getElementById('status').innerText = "Now playing";
                            
                            // Force play
                            player.playVideo();
                            
                            return true;
                        }} else {{
                            // Сохраняем видео для автовоспроизведения после нажатия кнопки
                            console.log(`Saving video for autoplay: ${{videoId}}`);
                            pendingVideoId = videoId;
                            pendingVideoTitle = title;
                            document.getElementById('song-info').innerText = "Нажмите кнопку 'Запустить воспроизведение'";
                            return false;
                        }}
                    }} else {{
                        console.error("Player not ready");
                        document.getElementById('status').innerText = "Player not ready";
                        pendingVideoId = videoId;
                        pendingVideoTitle = title;
                        return false;
                    }}
                }}
                
                function skipSong() {{
                    // Tell the main app to skip the song
                    fetch(`${{BASE_URL}}/skip_song`)
                        .catch(e => console.error('Error sending skip command:', e));
                }}
                
                // Check for pending media from the main app
                function checkForPendingMedia() {{
                    fetch(`${{BASE_URL}}/get_current_video`)
                        .then(response => response.json())
                        .then(data => {{
                            console.log('Checking for pending media, received:', data);
                            if (data.video_id) {{
                                console.log(`Got pending video: ${{data.video_id}}`);
                                loadVideo(data.video_id, data.title);
                            }} else if (data.audio_src) {{
                                console.log(`Got pending audio: ${{data.audio_src}}`);
                                loadAudio(data.audio_src, data.audio_info);
                            }}
                        }})
                        .catch(e => console.error('Error checking for pending media:', e));
                }}
                
                // Poll for changes
                setInterval(() => {{
                    fetch(`${{BASE_URL}}/check_for_commands`)
                        .then(response => response.json())
                        .then(data => {{
                            if (data.command === 'load') {{
                                console.log('Load command received:', data);
                                if (data.video_id) {{
                                    loadVideo(data.video_id, data.title);
                                }} else if (data.audio_src) {{
                                    loadAudio(data.audio_src, data.audio_info);
                                }}
                            }} else if (data.command === 'pause') {{
                                console.log('Pause command received');
                                if (autoplayEnabled) {{
                                    if (currentMediaType === 'youtube' && player && player.pauseVideo) {{
                                        player.pauseVideo();
                                    }} else if (currentMediaType === 'audio') {{
                                        audioElement.pause();
                                        audioPlayPause.textContent = 'Play';
                                    }}
                                }}
                            }} else if (data.command === 'play') {{
                                console.log('Play command received');
                                if (autoplayEnabled) {{
                                    if (currentMediaType === 'youtube' && player && player.playVideo) {{
                                        player.playVideo();
                                    }} else if (currentMediaType === 'audio') {{
                                        audioElement.play().then(() => {{
                                            audioPlayPause.textContent = 'Pause';
                                        }}).catch(e => console.error('Error playing audio:', e));
                                    }}
                                }} else {{
                                    // Если воспроизведение не разрешено, подсказываем пользователю
                                    document.getElementById('autoplay-button').style.animation = 'pulse 1s infinite';
                                }}
                            }} else if (data.command === 'volume' && data.value !== undefined) {{
                                console.log('Volume command received:', data.value);
                                pendingVolume = data.value;
                                
                                // Применяем громкость к активному плееру
                                if (currentMediaType === 'youtube' && player && player.setVolume) {{
                                    player.setVolume(data.value);
                                    console.log(`YouTube volume set to ${{data.value}}`);
                                }} else if (currentMediaType === 'audio') {{
                                    audioElement.volume = data.value / 100;
                                    audioVolume.value = data.value;
                                    console.log(`Audio volume set to ${{data.value}}`);
                                }} else {{
                                    console.log(`Volume value ${{data.value}} saved for later`);
                                }}
                            }} else if (data.command === 'clear') {{
                                console.log('Clear command received');
                                // Остановка текущего медиа
                                if (currentMediaType === 'youtube' && player && player.stopVideo) {{
                                    player.stopVideo();
                                    player.clearVideo();
                                }} else if (currentMediaType === 'audio') {{
                                    audioElement.pause();
                                    audioElement.currentTime = 0;
                                    audioElement.src = '';  // Очищаем источник
                                    audioPlayPause.textContent = 'Play';
                                }}
                                
                                document.getElementById('song-info').innerText = "No song playing";
                                document.getElementById('status').innerText = "Ready";
                                
                                console.log("Playlist ended, player cleared");
                            }}
                        }})
                        .catch(e => console.error('Error checking for commands:', e));
                }}, 1000);
            </script>
        </body>
        </html>
        """
        
        try:
            # Create a temporary HTML file that will persist for the session
            fd, path = tempfile.mkstemp(suffix='.html')
            
            # Важно: явно указываем кодировку UTF-8 при записи файла
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Закрываем файловый дескриптор, открытый tempfile.mkstemp()
            os.close(fd)
            
            return path
            
        except Exception as e:
            print(f"Error creating player HTML file: {e}")
            
            # Запасной вариант без специальных символов
            backup_html = html_content.replace("Оверлей", "Overlay").replace("Запустить воспроизведение", "Start playback")
            
            fd, path = tempfile.mkstemp(suffix='.html')
            with os.fdopen(fd, 'w') as f:
                f.write(backup_html)
                
            return path
    
    def _start_server(self):
        """Start a simple HTTP server to communicate with the player."""
        class PlayerHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, player_frame=None, **kwargs):
                self.player_frame = player_frame
                super().__init__(*args, **kwargs)
                
            def do_GET(self):
                try:
                    import urllib.parse
                    
                    parsed_path = urllib.parse.urlparse(self.path)
                    path = parsed_path.path
                    
                    print(f"GET request received: {path}")
                    
                    # Обработка аудиофайлов
                    if path.startswith('/audio/'):
                        # Декодируем путь к файлу
                        audio_file = urllib.parse.unquote(path[7:])  # Удаляем префикс '/audio/'
                        print(f"Audio file requested: {audio_file}")
                        
                        # Проверяем существование файла
                        if os.path.exists(audio_file) and os.path.isfile(audio_file):
                            try:
                                print(f"Serving audio file: {audio_file}, size: {os.path.getsize(audio_file)} bytes")
                                
                                # Отправляем заголовки
                                self.send_response(200)
                                self.send_header('Content-type', 'audio/mpeg')
                                self.send_header('Content-Length', str(os.path.getsize(audio_file)))
                                self.send_header('Access-Control-Allow-Origin', '*')  # CORS
                                self.end_headers()
                                
                                # Отправляем файл
                                with open(audio_file, 'rb') as f:
                                    self.wfile.write(f.read())
                                    
                                print(f"File {audio_file} sent successfully")
                                return
                            except Exception as e:
                                print(f"Error serving audio file: {e}")
                                self.send_response(500)
                                self.send_header('Content-type', 'text/plain')
                                self.end_headers()
                                self.wfile.write(f"Error: {str(e)}".encode())
                                return
                        else:
                            print(f"Audio file not found: {audio_file}")
                            self.send_response(404)
                            self.send_header('Content-type', 'text/plain')
                            self.end_headers()
                            self.wfile.write(b'File not found')
                            return
                    
                    # Для остальных запросов - стандартная обработка JSON API
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    # Обработка API запросов
                    if path == '/player_ready':
                        print("Player ready notification received")
                        if self.player_frame:
                            # Schedule on main thread
                            self.player_frame.master.after(0, self.player_frame._on_player_ready)
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                        
                    elif path == '/video_ended':
                        print("Media ended notification received")
                        if self.player_frame:
                            # Schedule on main thread
                            self.player_frame.master.after(0, self.player_frame._on_media_ended)
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                        
                    elif path == '/player_error':
                        query = urllib.parse.parse_qs(parsed_path.query)
                        error_code = query.get('code', ['unknown'])[0]
                        print(f"Player error notification received: {error_code}")
                        if self.player_frame:
                            # Schedule on main thread
                            self.player_frame.master.after(0, lambda: self.player_frame._on_player_error(error_code))
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                        
                    elif path == '/get_current_video':
                        response = {"video_id": "", "title": "", "audio_src": "", "audio_info": {}}
                        if self.player_frame:
                            if self.player_frame.current_video_id:
                                response = {
                                    "video_id": self.player_frame.current_video_id,
                                    "title": self.player_frame.title_label.cget("text"),
                                    "audio_src": "",
                                    "audio_info": {}
                                }
                            elif hasattr(self.player_frame, 'current_audio_src') and self.player_frame.current_audio_src:
                                response = {
                                    "video_id": "",
                                    "title": "",
                                    "audio_src": self.player_frame.current_audio_src,
                                    "audio_info": self.player_frame.current_audio_info or {}
                                }
                        self.wfile.write(json.dumps(response).encode())
                        
                    elif path == '/check_for_commands':
                        response = {"command": "none"}
                        if hasattr(self.player_frame, 'pending_command'):
                            response = self.player_frame.pending_command
                            self.player_frame.pending_command = {"command": "none"}
                        self.wfile.write(json.dumps(response).encode())
                        
                    elif path == '/skip_song':
                        print("Skip song command received")
                        if self.player_frame:
                            # Schedule on main thread
                            self.player_frame.master.after(0, self.player_frame._skip_song)
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                        
                    else:
                        self.wfile.write(json.dumps({"error": "unknown_command"}).encode())
                
                except Exception as e:
                    print(f"Error handling request {self.path}: {e}")
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                    except:
                        pass
                        
            def log_message(self, format, *args):
                # Suppress default log messages
                pass

        # Initialize pending command
        self.pending_command = {"command": "none"}
        
        # Create handler with reference to this frame
        handler = lambda *args, **kwargs: PlayerHandler(*args, player_frame=self, **kwargs)
        
        try:
            # Start server on the chosen port
            self.server = socketserver.ThreadingTCPServer(("localhost", self.server_port), handler)
            self.server.daemon_threads = True  # Ensure threads exit when main thread exits
            print(f"Starting server on port {self.server_port}")
            
            # Run server in a background thread
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
        except Exception as e:
            print(f"Error starting server: {e}")
            self.server = None
    
    def _launch_player_window(self):
        """Launch the player in a browser window."""
        try:
            if self.html_path and os.path.exists(self.html_path):
                url = f"file://{self.html_path}"
                
                # Проверяем, запущен ли уже браузер
                if hasattr(self, 'browser_launched') and self.browser_launched:
                    print("Browser already launched, skipping browser launch")
                    # We should still set the volume even if browser is already launched
                    self.pending_command = {"command": "volume", "value": self.volume}
                    return
                    
                print(f"Opening player at: {url}")
                
                # Открываем браузер с плеером
                if webbrowser.open(url):
                    self.browser_launched = True
                    print("Browser window opened successfully")
                    # Set initial volume after launch
                    self.pending_command = {"command": "volume", "value": self.volume}
                else:
                    print("Failed to open browser window")
                    
                # Запоминаем процесс для отслеживания
                self.player_process = subprocess.Popen(
                    [webbrowser.get().basename, url],
                    shell=True, 
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE
                )
        except Exception as e:
            print(f"Error launching player window: {e}")
    
    def _load_thumbnail_from_url(self, video_id):
        """Load a thumbnail for a YouTube video."""
        try:
            # Если у нас уже есть кешированное изображение, используем его
            if video_id in self.image_references:
                return self.image_references[video_id]
                
            # URL for the YouTube thumbnail (high quality)
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            
            # Load image from URL
            with urllib.request.urlopen(thumbnail_url) as url_response:
                img_data = url_response.read()
                
            # Create PIL image from data
            pil_img = Image.open(io.BytesIO(img_data))
            
            # Convert to CTkImage for proper HiDPI support
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(640, 360))
            
            # Save reference to prevent garbage collection
            self.image_references[video_id] = ctk_img
            
            return ctk_img
            
        except Exception as e:
            print(f"Error loading thumbnail: {e}")
            return self.placeholder_image if hasattr(self, "placeholder_image") else None
    
    def _on_player_ready(self):
        """Called when the player is ready."""
        try:
            print("Player ready callback received")
            
            # Установка громкости должна происходить сразу после готовности плеера
            self.pending_command = {"command": "volume", "value": self.volume}
            
            # Если у нас есть текущее видео, загружаем его с небольшой задержкой
            # для обеспечения корректной установки громкости перед загрузкой видео
            if self.current_video_id:
                # Используем метод after для создания небольшой задержки
                self.after(300, lambda: self._send_video_to_player())
        except Exception as e:
            print(f"Error in player ready callback: {e}")
            
    def _send_video_to_player(self):
        """Send current video to player with correct settings."""
        try:
            if self.current_video_id:
                print(f"Loading video {self.current_video_id} with volume {self.volume}")
                self.pending_command = {
                    "command": "load",
                    "video_id": self.current_video_id,
                    "title": self.title_label.cget("text")
                }
        except Exception as e:
            print(f"Error sending video to player: {e}")
    
    def update_queue_display(self):
        """Update the queue display."""
        pass
    
    def show(self):
        """Показывает плеер"""
        self.pack(fill=tk.BOTH, expand=True)

    def hide(self):
        """Скрывает плеер"""
        self.pack_forget()

    def update_now_playing(self, song):
        """Update the now playing display with the current song."""
        try:
            print(f"YouTube player: update_now_playing called with song: {song}")
            
            if song is None:
                # Если нет текущего трека
                print("Clearing player - no song provided")
                self.title_label.configure(text="No video playing")
                self.now_playing_label.configure(text="")
                self.current_video_id = None
                self.current_audio_src = None
                self.current_audio_info = None
                self.play_pause_btn.configure(text="Play")
                self.is_playing = False
                
                # Очищаем изображение
                self.thumbnail_label.configure(image=None, text="Ready to play videos")
                
                # Clear any existing timer
                if hasattr(self, 'safety_timer') and self.safety_timer:
                    self.after_cancel(self.safety_timer)
                    self.safety_timer = None
                    
                # Очищаем плеер в браузере
                self.pending_command = {"command": "clear"}
                
                # Показываем плеер для следующего трека
                self.pack(fill=tk.BOTH, expand=True)
                
                return False
                
            # Показываем плеер
            self.pack(fill=tk.BOTH, expand=True)
                
            # Определяем тип медиа
            if song.source == 'yandex':
                print("Processing Yandex track")
                # Yandex Music трек - загружаем и проигрываем как аудио
                self.title_label.configure(text=song.title)
                self.now_playing_label.configure(text=f"Requested by: {song.requester}")
                
                # Очищаем YouTube видео ID
                self.current_video_id = None
                
                # Загружаем заглушку для Yandex Music
                if hasattr(self, "placeholder_image") and self.placeholder_image:
                    self.thumbnail_label.configure(image=self.placeholder_image, text="")
                else:
                    self.thumbnail_label.configure(image=None, text="Yandex Music")
                
                # Update play/pause button
                self.play_pause_btn.configure(text="Pause")
                self.is_playing = True
                
                # Скачиваем файл и отправляем в плеер
                result = self._prepare_yandex_track(song)
                print(f"Yandex track preparation result: {result}")
                return result  # Возвращаем результат подготовки
            else:
                # YouTube видео или другой источник
                print(f"Processing YouTube track: {song.title}, video ID: {song.video_id}")
                self.title_label.configure(text=song.title)
                self.now_playing_label.configure(text=f"Requested by: {song.requester}")
                
                # Очищаем аудио источник
                self.current_audio_src = None
                self.current_audio_info = None
                
                # Проверяем наличие video_id
                video_id = getattr(song, 'video_id', None)
                if not video_id:
                    print("Error: No video ID in song object")
                    return False
                    
                self.current_video_id = video_id
                print(f"Set current_video_id to: {self.current_video_id}")
                
                # Загружаем миниатюру
                try:
                    ctk_img = self._load_thumbnail_from_url(video_id)
                    if ctk_img:
                        self.thumbnail_label.configure(image=ctk_img, text="")
                    else:
                        if hasattr(self, "placeholder_image") and self.placeholder_image:
                            self.thumbnail_label.configure(image=self.placeholder_image, text="")
                        else:
                            self.thumbnail_label.configure(image=None, text="Thumbnail not available")
                except Exception as thumbnail_error:
                    print(f"Error loading thumbnail: {thumbnail_error}")
                    if hasattr(self, "placeholder_image") and self.placeholder_image:
                        self.thumbnail_label.configure(image=self.placeholder_image, text="")
                    else:
                        self.thumbnail_label.configure(image=None, text="Error loading thumbnail")
                
                # Update play/pause button
                self.play_pause_btn.configure(text="Pause")
                self.is_playing = True
                
                # Load video in player
                self.pending_command = {
                    "command": "load",
                    "video_id": video_id,
                    "title": song.title
                }
                print(f"Set pending_command to load video: {video_id}")
                
                # Убедимся, что браузер запущен
                if not hasattr(self, 'browser_launched') or not self.browser_launched:
                    self._launch_player_window()
                
                # Set safety timer
                duration_secs = getattr(song, 'duration', 300)  # Default to 5 minutes if duration unknown
                
                # Clear any existing safety timer
                if hasattr(self, 'safety_timer') and self.safety_timer:
                    self.after_cancel(self.safety_timer)
                    self.safety_timer = None
                    
                # Set new safety timer
                self.safety_timer = self.after(int((duration_secs + 30) * 1000), self._on_safety_timeout)
                
                return True
                
        except Exception as e:
            print(f"Error updating player: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _prepare_yandex_track(self, song):
        """Prepare Yandex Music track for playback"""
        try:
            # Показываем индикатор загрузки
            self.title_label.configure(text=f"Загрузка: {song.title}")
            
            # Получаем API из music_player
            from music_player import get_yandex_music_api
            yandex_api = get_yandex_music_api()
            
            if not yandex_api or not hasattr(yandex_api, 'is_authorized') or not yandex_api.is_authorized:
                print("Yandex Music API not authorized")
                self.title_label.configure(text=f"Ошибка: API не авторизован")
                return False
            
            # Запускаем скачивание в отдельном потоке
            threading.Thread(
                target=self._download_yandex_track,
                args=(yandex_api, song),
                daemon=True
            ).start()
            
            # Важно! Возвращаем True, чтобы система знала, что трек обрабатывается
            return True
            
        except Exception as e:
            print(f"Error preparing Yandex track: {e}")
            import traceback
            traceback.print_exc()
            self.title_label.configure(text=f"Ошибка загрузки: {song.title}")
            return False

    def _download_yandex_track(self, yandex_api, song):
        """Download Yandex track in background thread"""
        try:
            # Скачиваем трек
            file_path = yandex_api.download_track(song.track_info)
            
            if file_path and os.path.exists(file_path):
                # Переход обратно в основной поток
                self.after(0, lambda: self._on_track_downloaded(file_path, song))
            else:
                # Ошибка загрузки
                self.after(0, lambda: self.title_label.configure(text=f"Ошибка загрузки: {song.title}"))
        
        except Exception as e:
            print(f"Error downloading Yandex track: {e}")
            # Переход обратно в основной поток
            self.after(0, lambda: self.title_label.configure(text=f"Ошибка: {str(e)}"))

    def _on_track_downloaded(self, file_path, song):
        """Called when Yandex track is downloaded"""
        try:
            if not file_path:
                print(f"Download failed for track: {song.title}")
                self.title_label.configure(text=f"Ошибка загрузки: {song.title}")
                return
                
            print(f"Track downloaded: {file_path}")
            
            # Готовим информацию для аудио-плеера
            audio_info = {
                "title": song.title,
                "artist": " & ".join(song.track_info.get('artists', [])) if isinstance(song.track_info, dict) else "Unknown Artist",
                "cover": None
            }
            
            # Создаем URL для доступа к файлу через наш HTTP сервер
            import urllib.parse
            encoded_path = urllib.parse.quote(file_path)
            audio_src = f"http://localhost:{self.server_port}/audio/{encoded_path}"
            
            print(f"Created audio URL: {audio_src}")
            
            # Сохраняем информацию о текущем треке
            self.current_audio_src = audio_src
            self.current_audio_info = audio_info
            self.current_video_id = None  # Сбрасываем текущий YouTube ID
            
            # Загружаем трек в плеер
            self.pending_command = {
                "command": "load",
                "audio_src": audio_src,
                "audio_info": audio_info
            }
            
            # Запускаем браузер если нужно
            if not hasattr(self, 'browser_launched') or not self.browser_launched:
                self._launch_player_window()
            
            # Обновляем информацию в UI
            self.title_label.configure(text=song.title)
            
        except Exception as e:
            print(f"Error starting audio playback: {e}")
            import traceback
            traceback.print_exc()
            self.title_label.configure(text=f"Ошибка воспроизведения: {str(e)}")

    def _on_media_ended(self):
        """Called when any media (video or audio) ends."""
        try:
            print("Media ended, playing next song")
            
            # Cancel safety timer
            if self.safety_timer:
                self.after_cancel(self.safety_timer)
                self.safety_timer = None
            
            # Skip to next song
            success, message = self.music_player.skip_song()
            
            # Если это была последняя песня и больше нет в очереди, явно очистим плеер
            if not self.music_player.is_playing:
                self.current_video_id = None
                self.current_audio_src = None
                self.current_audio_info = None
                self.is_playing = False
                self.pending_command = {"command": "clear"}
                
        except Exception as e:
            print(f"Error handling media end: {e}")

    def _on_video_ended(self):
        """Called when a video ends."""
        try:
            print("Video ended, playing next song")
            
            # Cancel safety timer
            if self.safety_timer:
                self.after_cancel(self.safety_timer)
                self.safety_timer = None
            
            # Skip to next song
            success, message = self.music_player.skip_song()
            
            # Если это была последняя песня и больше нет в очереди, явно очистим плеер
            if not self.music_player.is_playing:
                self.current_video_id = None
                self.is_playing = False
                self.pending_command = {"command": "clear"}
                
        except Exception as e:
            print(f"Error handling video end: {e}")
    
    def _on_player_error(self, error_code):
        """Called when there's a player error."""
        print(f"Player error: {error_code}")
        # Skip to next song after a delay
        self.after(3000, self._skip_song)
    
    def _on_safety_timeout(self):
        """Called when the safety timer fires."""
        try:
            print("Safety timeout triggered - video might be stuck")
            
            # Пробуем перейти к следующей песне
            if self.music_player:
                self.music_player.skip_song()
                
            # Сбрасываем таймер
            self.safety_timer = None
        except Exception as e:
            print(f"Error in safety timeout: {e}")
    
    def _toggle_play(self):
        """Toggle between play and pause."""
        if self.is_playing:
            # Pause the video
            self.pending_command = {"command": "pause"}
            self.is_playing = False
            self.play_pause_btn.configure(text="Play")
        else:
            if self.current_video_id:
                # Resume the video
                self.pending_command = {"command": "play"}
                self.is_playing = True
                self.play_pause_btn.configure(text="Pause")
                
                # Launch the player window if it's not already open
                self._launch_player_window()
            else:
                # Try to play the next song
                success, message = self.music_player.toggle_playback()
                if success:
                    self.is_playing = True
                    self.play_pause_btn.configure(text="Pause")
    
    def _skip_song(self):
        """Skip to the next song."""
        if self.skip_callback and callable(self.skip_callback):
            self.skip_callback()
        else:
            # Старый код на случай, если callback не определен
            try:
                self.music_player.skip_song()
            except Exception as e:
                print(f"Error skipping song: {e}")
    
    def _on_volume_change(self, value):
        """Handle volume slider change."""
        try:
            # Convert to integer (0-100)
            volume = int(float(value))
            self.volume = volume
            
            # Send to player immediately
            self.pending_command = {"command": "volume", "value": volume}
            
            # Save to config if available
            if hasattr(self, 'config_manager') and self.config_manager:
                self.config_manager.set_player_volume(volume)
        except Exception as e:
            print(f"Error in volume change handler: {e}")
    
    def set_volume(self, volume_fraction):
        """Set the player volume (0-1)."""
        try:
            # Handle volume as percentage (0-100) or fraction (0-1)
            if isinstance(volume_fraction, str):
                # Convert string to float first
                volume_fraction = float(volume_fraction)
                
            if volume_fraction <= 1.0 and isinstance(volume_fraction, float):
                self.volume = int(volume_fraction * 100)
            else:
                self.volume = int(volume_fraction)
                
            # Enforce bounds
            self.volume = max(0, min(100, self.volume))
            
            # Update the volume slider if it exists
            if hasattr(self, 'volume_slider'):
                self.volume_slider.set(self.volume)
            
            # Send command to player immediately
            self.pending_command = {"command": "volume", "value": self.volume}
            
            print(f"Volume set to {self.volume}% (input was {volume_fraction})")
            
            # Save to config if available
            if hasattr(self, 'config_manager') and self.config_manager:
                self.config_manager.set_player_volume(self.volume)
                
            return True
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False
    
    def _open_in_browser(self):
        """Open the current video in a web browser."""
        if self.current_video_id:
            url = f"https://www.youtube.com/watch?v={self.current_video_id}"
            webbrowser.open(url)
    
    def _ensure_player_running(self):
        """Ensure the player browser window is running"""
        try:
            if not hasattr(self, 'player_process') or self.player_process is None or self.player_process.poll() is not None:
                print("Player not running, launching new player window")
                self._launch_player_window()
            else:
                print("Player already running")
        except Exception as e:
            print(f"Error checking player status: {e}")
            # Попробуем перезапустить плеер
            self._launch_player_window()

    def destroy(self):
        """Clean up resources when the frame is destroyed."""
        try:
            # Очищаем все ссылки на изображения
            self.image_references.clear()
            
            # Отменяем все запланированные таймеры
            if self.safety_timer:
                self.after_cancel(self.safety_timer)
                self.safety_timer = None
                
            # Stop the HTTP server if it's running
            if self.server:
                try:
                    self.server.shutdown()
                    self.server.server_close()
                    print("HTTP server stopped")
                except Exception as e:
                    print(f"Error stopping HTTP server: {e}")
        except Exception as e:
            print(f"Error in destroy: {e}")
        finally:
            # Call parent destroy
            super().destroy()
