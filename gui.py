import customtkinter as ctk
import tkinter as tk
from config import ConfigManager
from twitch_bot import TwitchBot
from music_player import MusicPlayer
from youtube_player import YouTubePlayerFrame
import threading
import queue
import webbrowser
import random
import time
import os

class TwitchBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TwitchBot Music Player")
        self.root.geometry("1280x720")
        self.root.iconbitmap("icon.ico") if os.path.exists("icon.ico") else None
        
        # Initialize config manager
        self.config_manager = ConfigManager()
        
        # Initialize music player
        self.message_queue = queue.Queue()
        self.music_player = MusicPlayer(
            message_callback=self._add_chat_message,
            config_manager=self.config_manager  # Pass config_manager to MusicPlayer
        )
        
        # Create tabs and UI
        self._setup_gui()
        
        # Create bot
        self._setup_bot()
        
    def _setup_gui(self):
        """Setup the GUI components"""
        # Create main frame
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.pack(fill=tk.BOTH, expand=True)
        
        # Add tabs
        self.chat_tab = self.tab_view.add("Chat")
        self.player_tab = self.tab_view.add("Music Player")
        self.queue_tab = self.tab_view.add("Song Queue")
        self.settings_tab = self.tab_view.add("Settings")
        
        # Setup chat tab
        self._setup_chat_tab()
        
        # Setup player tab
        self._setup_player_tab()
        
        # Setup queue tab
        self._setup_queue_tab()
        
        # Setup settings tab
        self._setup_settings_tab()
        
        # Status bar at the bottom
        self.status_frame = ctk.CTkFrame(self.root, height=30)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Now playing indicator in status bar
        self.now_playing_label = ctk.CTkLabel(self.status_frame, text="")
        self.now_playing_label.pack(side=tk.RIGHT, padx=5)

    def _setup_chat_tab(self):
        """Setup the chat tab components"""
        # Chat display
        chat_frame = ctk.CTkFrame(self.chat_tab)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Chat text area (read-only)
        self.chat_display = ctk.CTkTextbox(chat_frame)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_display.configure(state="disabled")
        
        # Message input
        input_frame = ctk.CTkFrame(chat_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.message_var = ctk.StringVar()
        self.message_entry = ctk.CTkEntry(input_frame, placeholder_text="Type message here...", textvariable=self.message_var)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.send_button = ctk.CTkButton(input_frame, text="Send", command=self._send_message)
        self.send_button.pack(side=tk.RIGHT, padx=5)
        
        # Connect/Disconnect button
        control_frame = ctk.CTkFrame(chat_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.connect_button = ctk.CTkButton(control_frame, text="Connect", command=self._toggle_connection)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = ctk.CTkButton(control_frame, text="Clear Chat", command=self._clear_chat)
        self.clear_button.pack(side=tk.LEFT, padx=5)

    def _setup_player_tab(self):
        """Set up the player tab."""
        # Создаем фрейм-контейнер для плеера
        player_frame = ctk.CTkFrame(self.player_tab)
        player_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            print("Creating YouTube player frame")
            # Создаем универсальный плеер
            self.player_frame = YouTubePlayerFrame(
                player_frame,
                music_player=self.music_player,
                config_manager=self.config_manager
            )
            
            # Добавляем обработчик для пропуска песни
            self.player_frame.skip_callback = self._skip_current_song
            
            # Показываем плеер
            self.player_frame.pack(fill=tk.BOTH, expand=True)
            
            print("Initializing player in music controller")
            # Инициализируем плеер в контроллере музыки
            self.music_player.initialize_player(
                player_frame=self.player_frame,
                update_queue_callback=self._update_queue_display
            )
        except Exception as e:
            print(f"Error creating player: {e}")
            import traceback
            traceback.print_exc()
            # Создаем заглушку в случае ошибки
            self.player_frame = ctk.CTkFrame(player_frame)
            ctk.CTkLabel(self.player_frame, text=f"Error loading player: {str(e)}").pack(pady=20)
            self.player_frame.pack(fill=tk.BOTH, expand=True)

    def _setup_queue_tab(self):
        """Setup the song queue tab"""
        # Create a frame for the queue
        queue_frame = ctk.CTkFrame(self.queue_tab)
        queue_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Queue controls
        controls_frame = ctk.CTkFrame(queue_frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Clear queue button
        self.clear_queue_btn = ctk.CTkButton(controls_frame, text="Clear Queue", 
                                             command=self._clear_queue)
        self.clear_queue_btn.pack(side=tk.LEFT, padx=5)
        
        # Shuffle queue button
        self.shuffle_queue_btn = ctk.CTkButton(controls_frame, text="Shuffle Queue", 
                                              command=self._shuffle_queue)
        self.shuffle_queue_btn.pack(side=tk.LEFT, padx=5)
        
        # Skip song button
        self.skip_btn = ctk.CTkButton(controls_frame, text="Skip Current Song", 
                                     command=self._skip_current_song)
        self.skip_btn.pack(side=tk.LEFT, padx=5)
        
        # Queue display frame
        queue_list_frame = ctk.CTkFrame(queue_frame)
        queue_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Queue display - using a Listbox
        self.queue_list = tk.Listbox(queue_list_frame, bg="#2b2b2b", fg="white", 
                                     selectbackground="#3a3a3a", font=("Arial", 12))
        self.queue_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Add scrollbar
        scrollbar = tk.Scrollbar(queue_list_frame)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        
        # Connect scrollbar to listbox
        self.queue_list.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.queue_list.yview)
        
        # Item control buttons
        queue_item_controls_frame = ctk.CTkFrame(queue_frame)
        queue_item_controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Remove selected song button
        self.remove_song_btn = ctk.CTkButton(queue_item_controls_frame, text="Remove Selected", 
                                            command=self._remove_selected_song)
        self.remove_song_btn.pack(side=tk.LEFT, padx=5)
        
        # Add song button
        self.add_song_btn = ctk.CTkButton(queue_item_controls_frame, text="Add Song", 
                                          command=self._add_manual_song_request)
        self.add_song_btn.pack(side=tk.LEFT, padx=5)
        
        # Register update callback
        self.music_player.update_queue_callback = self._update_queue_display

    def _setup_settings_tab(self):
        """Setup the settings tab components"""
        settings_frame = ctk.CTkFrame(self.settings_tab)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs for different settings
        settings_tab_view = ctk.CTkTabview(settings_frame)
        settings_tab_view.pack(fill=tk.BOTH, expand=True)
        
        # Add settings tabs
        twitch_tab = settings_tab_view.add("Twitch")
        yandex_tab = settings_tab_view.add("Yandex Music")
        
        # Setup Twitch settings
        self._setup_twitch_settings(twitch_tab)
        
        # Setup Yandex Music settings
        self._setup_yandex_settings(yandex_tab)
        
    def _setup_twitch_settings(self, parent_frame):
        """Setup Twitch settings UI"""
        # Info text at the top
        info_text = "Get tokens from https://twitchtokengenerator.com\nSelect 'Chat Bot' scope for your bot"
        info_label = ctk.CTkLabel(parent_frame, text=info_text)
        info_label.pack(pady=10)
        
        token_generator_button = ctk.CTkButton(
            parent_frame, 
            text="Open Twitch Token Generator", 
            command=lambda: webbrowser.open('https://twitchtokengenerator.com')
        )
        token_generator_button.pack(pady=5)
        
        # Client ID
        client_id_frame = ctk.CTkFrame(parent_frame)
        client_id_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(client_id_frame, text="Client ID:").pack(side=tk.LEFT, padx=5)
        
        self.client_id_var = ctk.StringVar(value=self.config_manager.get("client_id", ""))
        self.client_id_entry = ctk.CTkEntry(client_id_frame, textvariable=self.client_id_var, width=400)
        self.client_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Access token
        access_token_frame = ctk.CTkFrame(parent_frame)
        access_token_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(access_token_frame, text="Access Token:").pack(side=tk.LEFT, padx=5)
        
        self.access_token_var = ctk.StringVar(value=self.config_manager.get("access_token", ""))
        self.access_token_entry = ctk.CTkEntry(access_token_frame, textvariable=self.access_token_var, width=400, show="*")
        self.access_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.show_access_token = ctk.CTkButton(access_token_frame, text="Show", width=40, 
                                        command=lambda: self._toggle_entry_visibility(self.access_token_entry, self.show_access_token))
        self.show_access_token.pack(side=tk.RIGHT, padx=5)
        
        # Refresh token
        refresh_token_frame = ctk.CTkFrame(parent_frame)
        refresh_token_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(refresh_token_frame, text="Refresh Token:").pack(side=tk.LEFT, padx=5)
        
        self.refresh_token_var = ctk.StringVar(value=self.config_manager.get("refresh_token", ""))
        self.refresh_token_entry = ctk.CTkEntry(refresh_token_frame, textvariable=self.refresh_token_var, width=400, show="*")
        self.refresh_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.show_refresh_token = ctk.CTkButton(refresh_token_frame, text="Show", width=40,
                                        command=lambda: self._toggle_entry_visibility(self.refresh_token_entry, self.show_refresh_token))
        self.show_refresh_token.pack(side=tk.RIGHT, padx=5)
        
        # Bot username
        username_frame = ctk.CTkFrame(parent_frame)
        username_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(username_frame, text="Bot Username:").pack(side=tk.LEFT, padx=5)
        
        self.username_var = ctk.StringVar(value=self.config_manager.get("bot_username", ""))
        self.username_entry = ctk.CTkEntry(username_frame, textvariable=self.username_var)
        self.username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Channel (single)
        channel_frame = ctk.CTkFrame(parent_frame)
        channel_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(channel_frame, text="Channel:").pack(side=tk.LEFT, padx=5)
        
        self.channel_var = ctk.StringVar(value=self.config_manager.get("channel", ""))
        self.channel_entry = ctk.CTkEntry(channel_frame, textvariable=self.channel_var)
        self.channel_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Save button
        save_frame = ctk.CTkFrame(parent_frame)
        save_frame.pack(fill=tk.X, padx=5, pady=15)
        
        self.save_button = ctk.CTkButton(save_frame, text="Save Twitch Settings", command=self._save_twitch_settings)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        
    def _setup_yandex_settings(self, parent_frame):
        """Setup Yandex Music settings UI with OAuth authentication"""
        info_text = """
        Для использования Yandex Music API необходимо авторизоваться.
        
        Нажмите кнопку 'Авторизоваться в Yandex Music' и следуйте инструкциям:
        1) Войдите в аккаунт Yandex Music (если требуется)
        2) Разрешите доступ приложению
        3) Скопируйте URL из адресной строки и вставьте его в поле ниже
        """
        
        info_label = ctk.CTkLabel(parent_frame, text=info_text, justify="left")
        info_label.pack(pady=10)
        
        # Button to open Yandex OAuth page
        auth_button_frame = ctk.CTkFrame(parent_frame)
        auth_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        auth_button = ctk.CTkButton(
            auth_button_frame, 
            text="Авторизоваться в Yandex Music", 
            command=self._open_yandex_auth
        )
        auth_button.pack(pady=5)
        
        # URL entry
        url_frame = ctk.CTkFrame(parent_frame)
        url_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(url_frame, text="Вставьте URL после авторизации:").pack(side=tk.LEFT, padx=5)
        
        self.yandex_auth_url_var = ctk.StringVar(value="")
        self.yandex_auth_url_entry = ctk.CTkEntry(url_frame, textvariable=self.yandex_auth_url_var, width=400)
        self.yandex_auth_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        extract_button = ctk.CTkButton(
            url_frame, 
            text="Извлечь токен", 
            width=100,
            command=self._extract_yandex_token
        )
        extract_button.pack(side=tk.RIGHT, padx=5)
        
        # Token display
        token_frame = ctk.CTkFrame(parent_frame)
        token_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(token_frame, text="Yandex Music Token:").pack(side=tk.LEFT, padx=5)
        
        # Загружаем токен из конфигурации
        yandex_token = ""
        if hasattr(self.music_player, 'yandex_music'):
            yandex_token = self.music_player.yandex_music.token or ""
        
        self.yandex_token_var = ctk.StringVar(value=yandex_token)
        self.yandex_token_entry = ctk.CTkEntry(token_frame, textvariable=self.yandex_token_var, width=400, show="*")
        self.yandex_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.show_yandex_token = ctk.CTkButton(
            token_frame, 
            text="Show", 
            width=40,
            command=lambda: self._toggle_entry_visibility(self.yandex_token_entry, self.show_yandex_token)
        )
        self.show_yandex_token.pack(side=tk.RIGHT, padx=5)
        
        # Автоматическое добавление из Моей Волны
        auto_wave_frame = ctk.CTkFrame(parent_frame)
        auto_wave_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Получаем текущее значение из конфигурации
        auto_wave_value = False
        try:
            # First try from music player (which loaded from config)
            if hasattr(self.music_player, 'auto_play_from_wave'):
                auto_wave_value = self.music_player.auto_play_from_wave
            # As fallback, load directly from config
            else:
                auto_wave_value = self.config_manager.get_yandex_auto_wave()
        except Exception as e:
            print(f"Error loading auto_wave setting: {e}")
        
        self.auto_wave_var = ctk.BooleanVar(value=auto_wave_value)
        self.auto_wave_checkbox = ctk.CTkCheckBox(
            auto_wave_frame, 
            text="Автоматически добавлять треки из Моей Волны, когда очередь пуста",
            variable=self.auto_wave_var
        )
        self.auto_wave_checkbox.pack(side=tk.LEFT, padx=5)
        
        # Action buttons
        button_frame = ctk.CTkFrame(parent_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=15)
        
        # Кнопка для пополнения очереди из Моей Волны
        self.add_wave_button = ctk.CTkButton(
            button_frame, 
            text="Добавить треки из Моей Волны",
            command=self._add_tracks_from_wave
        )
        self.add_wave_button.pack(side=tk.LEFT, padx=5)
        
        # Save button
        self.save_yandex_button = ctk.CTkButton(
            button_frame, 
            text="Save Yandex Settings", 
            command=self._save_yandex_settings
        )
        self.save_yandex_button.pack(side=tk.RIGHT, padx=5)
        
        # Test connection button
        self.test_yandex_button = ctk.CTkButton(
            button_frame, 
            text="Test Connection", 
            command=self._test_yandex_connection
        )
        self.test_yandex_button.pack(side=tk.RIGHT, padx=5)

    def _open_yandex_auth(self):
        """Open Yandex OAuth page in browser"""
        if not hasattr(self.music_player, 'yandex_music'):
            self._add_chat_message("Yandex Music API not initialized")
            return
            
        success = self.music_player.yandex_music.open_auth_page()
        if success:
            self._add_chat_message("Yandex Music authentication page opened in browser")
        else:
            self._add_chat_message("Failed to open Yandex Music authentication page")

    def _extract_yandex_token(self):
        """Extract token from URL after OAuth authentication"""
        url = self.yandex_auth_url_var.get().strip()
        if not url:
            self._add_chat_message("Please enter the URL after authentication")
            return
            
        if not hasattr(self.music_player, 'yandex_music'):
            self._add_chat_message("Yandex Music API not initialized")
            return
            
        token = self.music_player.yandex_music.extract_token_from_url(url)
        if token:
            self.yandex_token_var.set(token)
            self._add_chat_message("Token extracted successfully")
        else:
            self._add_chat_message("Failed to extract token from URL. Make sure you copied the full URL.")
    
    def _save_twitch_settings(self):
        """Save Twitch settings to config"""
        # Get values from inputs
        client_id = self.client_id_var.get().strip()
        access_token = self.access_token_var.get().strip()
        refresh_token = self.refresh_token_var.get().strip()
        bot_username = self.username_var.get().strip()
        channel = self.channel_var.get().strip()
        
        # Remove # if present (we'll add it when needed)
        if channel.startswith('#'):
            channel = channel[1:]
        
        # Update config
        self.config_manager.set("client_id", client_id)
        self.config_manager.set("access_token", access_token)
        self.config_manager.set("refresh_token", refresh_token)
        self.config_manager.set("bot_username", bot_username)
        self.config_manager.set("channel", channel)
        
        # Save and notify
        if self.config_manager.save_config():
            self._add_chat_message("Twitch settings saved")
        else:
            self._add_chat_message("Failed to save Twitch settings")
            
    def _save_yandex_settings(self):
        """Save Yandex Music settings to config"""
        try:
            # Get values from inputs
            yandex_token = self.yandex_token_var.get().strip()
            auto_wave = self.auto_wave_var.get()
            
            # Update the music player
            self.music_player.auto_play_from_wave = auto_wave
            
            # Explicitly save to configuration
            yandex_config = {
                "token": yandex_token,
                "auto_play_from_wave": auto_wave
            }
            
            # Save to config manager
            self.config_manager.set_yandex_music_config(yandex_config)
            
            # Authorize with token if provided
            if yandex_token:
                success, message = self.music_player.set_yandex_music_token(yandex_token)
                self._add_chat_message(message)
                
                if not success:
                    return False
            
            self._add_chat_message("Настройки Yandex Music сохранены")
            return True
        
        except Exception as e:
            print(f"Error saving Yandex settings: {e}")
            self._add_chat_message(f"Ошибка при сохранении настроек Yandex Music: {str(e)}")
            return False
    
    def _test_yandex_connection(self):
        """Test Yandex Music connection"""
        # Get token from entry
        token = self.yandex_token_var.get().strip()
        
        if not token:
            self._add_chat_message("Please enter a Yandex Music token")
            return
            
        # Try to authenticate
        success, message = self.music_player.set_yandex_music_token(token)
        self._add_chat_message(message)
        
        if success:
            # Try to get user info
            user_info = self.music_player.yandex_music.get_user_info()
            if user_info:
                self._add_chat_message(f"Successfully connected to Yandex Music as {user_info.account.login}")
            else:
                self._add_chat_message("Connected to Yandex Music but couldn't get user info")
    
    def _add_tracks_from_wave(self):
        """Add tracks from Yandex Music My Wave to queue"""
        if not self.music_player.yandex_music.is_authorized:
            self._add_chat_message("Необходимо авторизоваться в Yandex Music. Введите токен и сохраните настройки.")
            return
            
        success, message = self.music_player.add_yandex_wave_tracks(5)  # Add 5 tracks from My Wave
        self._add_chat_message(message)

    def _toggle_entry_visibility(self, entry_widget, button_widget):
        """Toggle visibility of an entry field"""
        if entry_widget.cget("show") == "*":
            entry_widget.configure(show="")
            button_widget.configure(text="Hide")
        else:
            entry_widget.configure(show="*")
            button_widget.configure(text="Show")

    def _setup_bot(self):
        """Setup the bot and music player"""
        # Используем уже созданный экземпляр ConfigManager
        
        # Message queue for thread-safe communication
        self.message_queue = queue.Queue()
        
        # Теперь не создаем новый экземпляр MusicPlayer, а используем существующий
        
        # Bot instance (will be initialized on connect)
        self.bot = None
        
        # Start periodic tasks
        self._setup_periodic_tasks()

    def _setup_periodic_tasks(self):
        """Setup periodic tasks"""
        # Check for messages from the bot thread
        self.root.after(100, self._process_message_queue)

    def _process_message_queue(self):
        """Process messages from the queue"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                self._add_chat_message(message)
                self.message_queue.task_done()
        except queue.Empty:
            pass
        
        # Schedule the next check
        self.root.after(100, self._process_message_queue)

    def _on_new_message(self, message):
        """Callback for new messages from the bot"""
        self.message_queue.put(message)

    def _add_chat_message(self, message):
        """Add a message to the chat display."""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"{timestamp} {message}"
        
        # Add the message to the chat window
        self.chat_display.configure(state="normal")
        self.chat_display.insert(tk.END, formatted_message + "\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)  # Scroll to the last message

    def _toggle_connection(self):
        """Toggle connection to Twitch"""
        if self.bot and self.bot.is_running:
            # Disconnect
            self.bot.stop_bot()
            self.connect_button.configure(text="Connect")
            self.status_label.configure(text="Disconnected")
            self._add_chat_message("Bot disconnected")
        else:
            # Connect
            try:
                # Pass the music player to the bot
                self.bot = TwitchBot(self.config_manager, self._on_new_message, self.music_player)
                if self.bot.start_bot():
                    self.connect_button.configure(text="Disconnect")
                    self.status_label.configure(text=f"Connected to {self.config_manager.get('channel', '')}")
                    self._add_chat_message("Bot connected to Twitch")
                else:
                    self._add_chat_message("Failed to start bot")
            except Exception as e:
                self._add_chat_message(f"Error connecting: {str(e)}")

    def _send_message(self):
        """Send a message to the connected channel"""
        if not self.bot or not self.bot.is_running:
            self._add_chat_message("Bot is not connected")
            return
            
        message = self.message_var.get().strip()
        
        if not message:
            return
            
        success = self.bot.send_message(message)
        if success:
            channel = self.config_manager.get('channel', '')
            # Show a pending message
            self._add_chat_message(f"Sending to {channel}: {message}")
            self.message_var.set("")  # Clear the message input
        else:
            self._add_chat_message(f"Failed to queue message")

    def _clear_chat(self):
        """Clear the chat display"""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")

    def _on_player_message(self, message):
        """Handle messages from the music player."""
        # Update the now playing label in the status bar
        self.now_playing_label.configure(text=message)
        
        # Also add to chat for visibility
        self._add_chat_message(f"[PLAYER] {message}")
        
        # If this is a "Сейчас играет:" message, update the player UI
        if message.startswith("Сейчас играет:"):
            # The current_song should already be set in the music player
            if self.music_player.current_song:
                self.player_frame.update_now_playing(self.music_player.current_song)
    
    def _update_queue_display(self):
        """Update the song queue display."""
        # Clear the current list
        self.queue_list.delete(0, tk.END)
        
        # Add the current song at the top if there is one
        if self.music_player.current_song:
            self.queue_list.insert(tk.END, f"▶ {self.music_player.current_song.title} (Запрошено: {self.music_player.current_song.requester})")
        else:
            # Покажем пустое состояние, если нет текущей песни
            self.queue_list.insert(tk.END, "Очередь пуста")
        
        # Add all songs in the queue
        for i, song in enumerate(self.music_player.queue):
            self.queue_list.insert(tk.END, f"{i+1}. {song.title} (Запрошено: {song.requester})")
    
    def _clear_queue(self):
        """Clear the song queue."""
        success, message = self.music_player.clear_queue()
        self._add_chat_message(f"[PLAYER] {message}")
    
    def _shuffle_queue(self):
        """Shuffle the song queue."""
        if not self.music_player.queue:
            self._add_chat_message("[PLAYER] Queue is empty")
            return
        
        # Shuffle the queue
        random.shuffle(self.music_player.queue)
        self._update_queue_display()
        self._add_chat_message("[PLAYER] Queue shuffled")

    def _skip_current_song(self):
        """Skip the current song from the GUI."""
        success, message = self.music_player.skip_song()
        self._add_chat_message(f"[PLAYER] {message}")
    
    def _remove_selected_song(self):
        """Remove the selected song from the queue."""
        # Get selected index
        selected_indices = self.queue_list.curselection()
        if not selected_indices:
            self._add_chat_message("[PLAYER] No song selected")
            return
        
        index = selected_indices[0]
        
        # Adjust index if we have a current song showing at position 0
        queue_index = index
        if self.music_player.current_song:
            queue_index = index - 1
        
        # Check if it's the currently playing song (index 0 when there's a current song)
        if self.music_player.current_song and index == 0:
            success, message = self.music_player.skip_song()
            self._add_chat_message(f"[PLAYER] {message}")
            return
        
        # Check if the index is valid for our queue
        if queue_index >= 0 and queue_index < len(self.music_player.queue):
            # Get the song to show its name in the message
            removed_song = self.music_player.queue[queue_index]
            
            # Remove from queue
            self.music_player.queue.pop(queue_index)
            
            # Update display
            self._update_queue_display()
            self._add_chat_message(f"[PLAYER] Removed: {removed_song.title}")
        else:
            self._add_chat_message("[PLAYER] Invalid song selection")

    def _add_manual_song_request(self):
        """Add a song request from the GUI."""
        dialog = ctk.CTkInputDialog(
            text="Enter YouTube URL or search term:", 
            title="Add Song Request"
        )
        query = dialog.get_input()
        
        if query:
            success, message = self.music_player.add_to_queue(query, "GUI User")
            self._add_chat_message(f"[PLAYER] {message}")

    def _on_volume_changed(self, value):
        """Handle volume change from slider."""
        volume = int(float(value))
        
        # Установка громкости в плеере
        if self.music_player:
            self.music_player.set_volume(volume)
            
        # Сохраняем громкость в конфигурации
        if hasattr(self, 'config_manager'):
            self.config_manager.set_player_volume(volume)

    def _skip_song_callback(self):
        """Callback for skipping songs from player UI"""
        # Вызываем метод пропуска песни в music_player
        if hasattr(self, 'music_player'):
            success, message = self.music_player.skip_song()
            self._add_chat_message(message)
            return success
        return False