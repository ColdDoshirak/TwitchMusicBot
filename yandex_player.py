import customtkinter as ctk
import tkinter as tk
import threading
import webbrowser
import requests
from PIL import Image, ImageTk
from io import BytesIO
from audio_player import AudioPlayer

class YandexMusicPlayerFrame(ctk.CTkFrame):
    def __init__(self, master, skip_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.skip_callback = skip_callback
        self.current_track = None
        self.is_playing = False
        self.volume = 50
        self.audio_player = AudioPlayer()
        self.audio_player.set_update_callback(self._on_playback_update)
        self.pending_download = None
        
        # Настройка UI
        self.setup_ui()
        
        # Скрываем по умолчанию
        self.hide()
    
    def _on_playback_update(self, event_type):
        """Обработчик событий аудиоплеера"""
        if event_type == 'finished':
            # Трек закончился, переходим к следующему
            if self.skip_callback and callable(self.skip_callback):
                # Выполняем в основном потоке через after
                self.after(0, self.skip_callback)
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Заголовок трека
        self.title_label = ctk.CTkLabel(self, text="Готов к воспроизведению", 
                                       font=("Roboto", 16, "bold"), wraplength=400)
        self.title_label.pack(pady=(10, 5), padx=10)
        
        # Исполнитель
        self.artist_label = ctk.CTkLabel(self, text="", font=("Roboto", 14))
        self.artist_label.pack(pady=(0, 10))
        
        # Обложка альбома
        self.cover_frame = ctk.CTkFrame(self, width=300, height=300)
        self.cover_frame.pack(pady=10)
        self.cover_frame.pack_propagate(False)
        
        self.cover_label = ctk.CTkLabel(self.cover_frame, text="")
        self.cover_label.pack(fill=tk.BOTH, expand=True)
        
        # Кнопки управления
        controls_frame = ctk.CTkFrame(self)
        controls_frame.pack(fill=tk.X, pady=10, padx=20)
        
        self.play_pause_btn = ctk.CTkButton(controls_frame, text="Play", width=100, 
                                           command=self.toggle_playback)
        self.play_pause_btn.pack(side=tk.LEFT, padx=10)
        
        self.skip_btn = ctk.CTkButton(controls_frame, text="Skip", width=100, 
                                     command=self.skip_track)
        self.skip_btn.pack(side=tk.RIGHT, padx=10)
        
        # Громкость
        volume_frame = ctk.CTkFrame(self)
        volume_frame.pack(fill=tk.X, pady=10, padx=20)
        
        ctk.CTkLabel(volume_frame, text="Громкость:").pack(side=tk.LEFT, padx=10)
        
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, number_of_steps=20)
        self.volume_slider.set(50)
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        # Дополнительные сведения о треке
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill=tk.X, pady=10, padx=20)
        
        ctk.CTkLabel(self.info_frame, text="Источник: Yandex Music | Моя Волна").pack(pady=5)
        
        # Создаем заглушку для обложки
        self.placeholder_image = self.create_placeholder_image(300, 300)
        self.cover_label.configure(image=self.placeholder_image)
        
        # Ссылка на Yandex Music
        link_frame = ctk.CTkFrame(self)
        link_frame.pack(fill=tk.X, pady=(5, 15), padx=20)
        
        self.open_link_btn = ctk.CTkButton(link_frame, text="Открыть в браузере", 
                                          command=self.open_in_browser)
        self.open_link_btn.pack(pady=5)
        
    def create_placeholder_image(self, width, height):
        """Создает заглушку для обложки альбома"""
        try:
            # Создаем пустое изображение желтого цвета (как в логотипе Яндекса)
            placeholder = Image.new("RGB", (width, height), "#FFCC00")
            
            # Добавляем текст
            try:
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(placeholder)
                try:
                    # Пробуем загрузить шрифт, если не получится - используем стандартный
                    font = ImageFont.truetype("arial.ttf", 24)
                except:
                    font = None
                draw.text((width//2 - 60, height//2 - 12), "Yandex Music", fill="black", font=font)
            except Exception as e:
                print(f"Error adding text to placeholder: {e}")
                
            return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, 
                             size=(width, height))
        except Exception as e:
            print(f"Error creating placeholder: {e}")
            return None
    
    def update_now_playing(self, song):
        """Обновляет информацию о проигрываемом треке"""
        try:
            if song and song.source == 'yandex' and song.track_info:
                self.current_track = song
                
                # Обновляем информацию
                self.title_label.configure(text=song.title)
                
                # Проверяем разные форматы данных
                if isinstance(song.track_info, dict) and 'artists' in song.track_info:
                    artists_str = " & ".join(song.track_info['artists'])
                    self.artist_label.configure(text=f"Исполнитель: {artists_str}")
                
                # Обновляем кнопки
                self.play_pause_btn.configure(text="Pause")
                self.is_playing = True
                
                # Загружаем обложку альбома
                self.load_album_art(song.track_info)
                
                # Показываем плеер
                self.show()
                
                # Скачиваем и начинаем воспроизведение трека
                from music_player import get_yandex_music_api
                yandex = get_yandex_music_api()
                if yandex:
                    # Отменяем предыдущую загрузку, если есть
                    self.pending_download = None
                    
                    # Устанавливаем индикатор загрузки
                    self.title_label.configure(text=f"Загрузка трека: {song.title}")
                    
                    # Запускаем асинхронную загрузку
                    self.pending_download = yandex.download_track_async(
                        song.track_info, 
                        self._on_track_downloaded
                    )
                
                return True
            else:
                # Если трек не из Yandex Music или нет трека вообще
                self.current_track = None
                self.title_label.configure(text="Готов к воспроизведению")
                self.artist_label.configure(text="")
                self.play_pause_btn.configure(text="Play")
                self.is_playing = False
                
                # Останавливаем воспроизведение
                self.audio_player.stop()
                
                # Возвращаем заглушку
                self.cover_label.configure(image=self.placeholder_image)
                
                # Скрываем плеер
                self.hide()
                return False
                
        except Exception as e:
            print(f"Error updating Yandex player: {e}")
            return False
    
    def _on_track_downloaded(self, file_path):
        """Callback после загрузки трека"""
        if file_path:
            # Загружаем трек в аудиоплеер
            if self.audio_player.load(file_path):
                # Устанавливаем громкость и начинаем воспроизведение
                self.audio_player.set_volume(self.volume / 100.0)
                self.audio_player.play()
                
                # Обновляем UI
                self.play_pause_btn.configure(text="Pause")
                self.is_playing = True
                
                # Обновляем надпись (убираем "Загрузка трека:")
                if self.current_track:
                    self.title_label.configure(text=self.current_track.title)
            else:
                self.title_label.configure(text="Ошибка загрузки трека")
        else:
            self.title_label.configure(text="Не удалось скачать трек")
    
    def load_album_art(self, track_info):
        """Загружает обложку альбома"""
        # Запускаем в отдельном потоке, чтобы не блокировать UI
        threading.Thread(target=self._fetch_album_art, args=(track_info,), daemon=True).start()
    
    def _fetch_album_art(self, track_info):
        """Загружает обложку альбома из сети"""
        try:
            if not isinstance(track_info, dict):
                return
                
            # Получаем ID альбома и трека
            album_id = track_info.get('album_id')
            track_id = track_info.get('id')
            
            if not album_id or not track_id:
                return
                
            # Формируем URL обложки (обычно это был бы API-вызов)
            # В данном случае делаем упрощенно - предполагаем, что URL можно сформировать статически
            try:
                # У нас нет прямого доступа к API из этого потока, используем статичный URL
                cover_url = f"https://avatars.yandex.net/get-music-content/{album_id}/{track_id}/400x400"
                response = requests.get(cover_url)
                
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    
                    # Создаем CTkImage
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(300, 300))
                    
                    # Обновляем UI безопасно из главного потока
                    self.after(0, lambda: self.cover_label.configure(image=ctk_img))
                    # Сохраняем ссылку, чтобы избежать сборки мусора
                    self._current_cover = ctk_img
            except Exception as e:
                print(f"Error loading album art: {e}")
                # В случае ошибки оставляем заглушку
        
        except Exception as e:
            print(f"Error fetching album art: {e}")
    
    def toggle_playback(self):
        """Переключает воспроизведение/паузу"""
        if self.is_playing:
            self.audio_player.pause()
            self.play_pause_btn.configure(text="Play")
        else:
            self.audio_player.resume()
            self.play_pause_btn.configure(text="Pause")
            
        self.is_playing = not self.is_playing
    
    def skip_track(self):
        """Пропускает текущий трек"""
        # Останавливаем воспроизведение
        self.audio_player.stop()
        
        # Вызываем callback пропуска
        if self.skip_callback and callable(self.skip_callback):
            self.skip_callback()
    
    def set_volume(self, volume):
        """Устанавливает громкость (0-100)"""
        self.volume = volume
        self.volume_slider.set(volume)
        self.audio_player.set_volume(volume / 100.0)
    
    def show(self):
        """Показывает плеер"""
        self.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        """Скрывает плеер"""
        self.pack_forget()
    
    def open_in_browser(self):
        """Открывает трек в браузере"""
        if self.current_track and hasattr(self.current_track, 'track_info'):
            try:
                track_id = self.current_track.track_info.get('id')
                album_id = self.current_track.track_info.get('album_id')
                
                if track_id:
                    # Формируем URL для яндекс музыки
                    url = f"https://music.yandex.ru/album/{album_id}/track/{track_id}"
                    webbrowser.open(url)
            except Exception as e:
                print(f"Error opening track in browser: {e}")