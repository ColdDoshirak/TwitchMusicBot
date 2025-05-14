from twitchio.ext import commands
import asyncio
import threading

class TwitchBot:
    def __init__(self, config_manager, message_callback=None, music_player=None):
        self.config_manager = config_manager
        self.message_callback = message_callback
        self.music_player = music_player  # Add the music player reference
        self.is_running = False
        self.bot_thread = None
        self.bot_instance = None
        self._loop = None
        self._message_queue = asyncio.Queue()  # Queue for messages to be sent
        
    def start_bot(self):
        """Start the bot in a separate thread."""
        if self.is_running:
            return False
            
        self.is_running = True
        self.bot_thread = threading.Thread(target=self._run)
        self.bot_thread.daemon = True
        self.bot_thread.start()
        return True
        
    def stop_bot(self):
        """Stop the running bot."""
        if not self.is_running:
            return False
            
        self.is_running = False
        
        # Signal the thread to stop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            
        return True
    
    async def _shutdown(self):
        """Properly shutdown the bot"""
        if self.bot_instance:
            await self.bot_instance.close()
        
    def _run(self):
        """Run the bot's event loop in a separate thread."""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        
        try:
            # Get credentials from config
            access_token = self.config_manager.get('access_token')
            bot_username = self.config_manager.get('bot_username')
            channel = self.config_manager.get('channel', '')
            
            if not access_token or not bot_username or not channel:
                raise ValueError("Missing required configuration for Twitch bot")
            
            # Make sure channel doesn't start with #
            if channel.startswith('#'):
                channel = channel[1:]
                
            # Create the bot instance
            self.bot_instance = BotInstance(
                token=access_token,
                prefix='!',
                initial_channels=[channel],  # Single channel as a list element
                nick=bot_username,
                message_callback=self.message_callback,
                message_queue=self._message_queue,
                music_player=self.music_player  # Pass the music player
            )
            
            # Start the message processor task
            message_processor = asyncio.ensure_future(self._process_messages(), loop=loop)
            
            # Run the bot
            loop.run_until_complete(self.bot_instance.start())
            
            # Cancel the message processor when the bot stops
            if not message_processor.done():
                message_processor.cancel()
                
        except Exception as e:
            print(f"Error in bot thread: {str(e)}")
            if self.message_callback:
                self.message_callback(f"Error connecting: {str(e)}")
        finally:
            self.is_running = False
            loop.close()
            self._loop = None
            self.bot_instance = None
    
    async def _process_messages(self):
        """Process messages in the queue and send them."""
        while self.is_running:
            try:
                # Wait for a message in the queue
                channel_name, content = await self._message_queue.get()
                
                # If the bot is idle (not fully connected yet), wait a bit
                if not self.bot_instance.is_ready:
                    await asyncio.sleep(0.5)
                    self._message_queue.put_nowait((channel_name, content))  # Put it back in the queue
                    continue
                
                # Try to find the channel
                channel = None
                try:
                    # Check if we can get the channel
                    if hasattr(self.bot_instance, 'connected_channels'):
                        for ch in self.bot_instance.connected_channels:
                            if ch.name.lower() == channel_name.lower():
                                channel = ch
                                break
                except:
                    pass
                
                # Try to send the message
                try:
                    if channel:
                        # Send via channel object
                        await channel.send(content)
                        print(f"Message sent to {channel_name} via channel object")
                    else:
                        # Use the ctx object from a dummy command handler
                        print(f"Channel object not found, trying alternative method")
                        # Let the user know we failed
                        if self.message_callback:
                            self.message_callback(f"Failed to send message")
                except Exception as e:
                    print(f"Error sending message: {str(e)}")
                    if self.message_callback:
                        self.message_callback(f"Error sending message: {str(e)}")
                
                # Mark the task as done
                self._message_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in message processor: {str(e)}")
                await asyncio.sleep(0.5)  # Brief pause before retry
    
    def send_message(self, message):
        """Queue a message to be sent to the channel."""
        if not self.is_running or not self._loop:
            return False
        
        try:
            # Get the channel name from config
            channel = self.config_manager.get('channel', '')
            if not channel:
                return False
            
            # Remove # if present
            if channel.startswith('#'):
                channel = channel[1:]
            
            # Put the message in the queue via the event loop
            asyncio.run_coroutine_threadsafe(
                self._message_queue.put((channel, message)), 
                self._loop
            )
            
            # Signal success - note that this doesn't guarantee delivery,
            # just that it was queued successfully
            return True
            
        except Exception as e:
            print(f"Error queueing message: {str(e)}")
            if self.message_callback:
                self.message_callback(f"Error queueing message: {str(e)}")
            return False

# Actual Bot Implementation
class BotInstance(commands.Bot):
    def __init__(self, token, prefix, initial_channels, nick, message_callback=None, message_queue=None, music_player=None):
        self.message_callback = message_callback
        self.message_queue = message_queue
        self.music_player = music_player  # Add the music player reference
        self.is_ready = False
        
        # Initialize the parent class
        super().__init__(
            token=token,
            prefix=prefix,
            initial_channels=initial_channels,
            nick=nick,
        )

    async def event_ready(self):
        """Called when the bot is ready."""
        self.is_ready = True
        print(f'Bot is ready | Logged in as {self.nick}')
        if self.message_callback:
            self.message_callback(f"Bot connected and logged in as {self.nick}")
            
        # Print debug info
        print(f"Connected channels: {[ch.name for ch in self.connected_channels]}")
    
    async def event_message(self, message):
        """Called when a message is received."""
        if message.echo:
            return
            
        # Try to store the channel for future use if it's available
        if hasattr(message, 'channel') and message.channel:
            print(f"Got channel from message: {message.channel.name}")
            
        # Notify the UI about the new message
        if self.message_callback:
            formatted_message = f"{message.author.name}: {message.content}"
            self.message_callback(formatted_message)
            
        # Process commands
        await self.handle_commands(message)
    
    @commands.command(name='hello')
    async def hello_command(self, ctx):
        """Simple example command."""
        await ctx.send(f'Hello {ctx.author.name}!')
        
    # Add a helper method to send messages
    async def send_channel_message(self, channel_name, content):
        """Send a message to a channel by name."""
        # Find the channel
        for channel in self.connected_channels:
            if channel.name.lower() == channel_name.lower():
                await channel.send(content)
                return True
        return False
    
    # Add music commands
    @commands.command(name='sr')
    async def song_request(self, ctx, *, query: str):
        """Request a song to be played (!sr <song name or YouTube URL>)."""
        if not self.music_player:
            await ctx.send("Music player is not available.")
            return
            
        success, message = self.music_player.add_to_queue(query, ctx.author.name)
        await ctx.send(message)
    
    @commands.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx):
        """Show the current song queue."""
        if not self.music_player:
            await ctx.send("Музыкальный плеер недоступен.")
            return
        
        # Если очередь пуста
        if not self.music_player.queue and not self.music_player.current_song:
            await ctx.send("Очередь пуста. Добавьте песню командой !sr <название или YouTube URL>")
            return
        
        # Показать текущую песню и следующие несколько
        response = ""
        if self.music_player.current_song:
            response = f"Сейчас играет: {self.music_player.current_song.title}. "
        
        if self.music_player.queue:
            response += "В очереди: "
            # Показываем до 3 песен, чтобы избежать слишком длинного сообщения
            songs_to_show = min(3, len(self.music_player.queue))
            song_titles = [f"{i+1}. {song.title}" for i, song in enumerate(self.music_player.queue[:songs_to_show])]
            response += ", ".join(song_titles)
            
            if len(self.music_player.queue) > songs_to_show:
                response += f" и ещё {len(self.music_player.queue) - songs_to_show} песен"
        else:
            response += "В очереди больше нет песен."
        
        await ctx.send(response)
    
    @commands.command(name='np', aliases=['nowplaying'])
    async def now_playing(self, ctx):
        """Show what song is currently playing."""
        if not self.music_player or not self.music_player.current_song:
            await ctx.send("Сейчас ничего не играет.")
            return
        
        song = self.music_player.current_song
        # Преобразуем duration в целое число для безопасного форматирования
        duration_min = int(song.duration // 60)
        duration_sec = int(song.duration % 60)
        
        await ctx.send(f"Сейчас играет: {song.title} [{duration_min}:{duration_sec:02d}] (запрошено: {song.requester})")
    
    @commands.command(name='skipsong')
    async def skip_song(self, ctx):
        """Skip the current song."""
        if not self.music_player:
            await ctx.send("Музыкальный плеер не инициализирован.")
            return
        
        # Check if user is mod/broadcaster or the requester of the current song
        is_mod = ctx.author.is_mod or ctx.author.name.lower() == ctx.channel.name.lower()
        is_requester = (self.music_player.current_song and 
                       self.music_player.current_song.requester.lower() == ctx.author.name.lower())
        
        if not is_mod and not is_requester:
            await ctx.send(f"@{ctx.author.name} Только модераторы и тот, кто запросил песню, могут пропускать песни.")
            return
        
        # Проверка, есть ли текущая песня для пропуска
        if not self.music_player.current_song:
            await ctx.send("Сейчас ничего не играет.")
            return
        
        # Теперь используем напрямую метод skip_song из music_player
        # который правильно обрабатывает случай отсутствия песен в очереди
        success, message = self.music_player.skip_song()
        
        # Отправляем результат в чат
        await ctx.send(message)
    
    @commands.command(name='wrongsong')
    async def wrong_song(self, ctx):
        """Remove the last song you requested from the queue."""
        if not self.music_player:
            await ctx.send("Music player is not available.")
            return
            
        success, message = self.music_player.wrong_song(ctx.author.name)
        await ctx.send(message)
    
    @commands.command(name='volume')
    async def volume_command(self, ctx, volume=None):
        """Set player volume"""
        if not self.music_player:
            return
            
        # Проверка прав: если запрашивают текущую громкость - показываем всем
        if volume is None:
            # Get current volume
            current_volume = self.music_player.volume
            await ctx.send(f"Текущая громкость: {current_volume}%")
            return
        
        # Если пытаются изменить громкость - проверяем права
        if not (ctx.author.is_mod or ctx.author.name.lower() == ctx.channel.name.lower()):
            await ctx.send("Только модераторы могут менять громкость!")
            return
        
        try:
            # Convert volume to integer
            volume_value = int(volume)
            
            # Enforce volume limits
            if volume_value < 0:
                volume_value = 0
            elif volume_value > 100:
                volume_value = 100
                
            # Set the volume in the music player
            success = self.music_player.set_volume(volume_value)
            
            if success:
                await ctx.send(f"Громкость установлена на {volume_value}%")
                print(f"Volume set to {volume_value}% from chat command by moderator {ctx.author.name}")
                
                # Сохраняем новое значение громкости в конфигурации
                if hasattr(self, 'config_manager') and self.config_manager:
                    self.config_manager.set_player_volume(volume_value)
                    self.config_manager.save_config()
                    print("Volume setting saved to configuration")
                
            else:
                await ctx.send("Не удалось установить громкость")
        except ValueError:
            await ctx.send("Укажите громкость числом от 0 до 100")
        except Exception as e:
            print(f"Error in volume command: {e}")
            await ctx.send("Произошла ошибка при изменении громкости")
    
    @commands.command(name='play')
    async def play(self, ctx):
        """Start or resume playback."""
        if not self.music_player:
            await ctx.send("Music player is not available.")
            return
            
        success, message = self.music_player.toggle_playback()
        await ctx.send(message)
    
    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stop playback."""
        if not self.music_player:
            await ctx.send("Music player is not available.")
            return
        
        # Check if user is a mod or broadcaster
        if not (ctx.author.is_mod or ctx.author.name.lower() == ctx.channel.name.lower()):
            await ctx.send("Only moderators can stop the player.")
            return
            
        success, message = self.music_player.stop_playback()
        await ctx.send(message)
    
    @commands.command(name='ymsr')
    async def yandex_music_request(self, ctx, *, query: str):
        """Request a song from Yandex Music (!ymsr <song name>)."""
        if not self.music_player:
            await ctx.send("Музыкальный плеер недоступен.")
            return
            
        success, message = self.music_player.add_to_queue(query, ctx.author.name, source='yandex')
        await ctx.send(message)
    
    @commands.command(name='mywave')
    async def my_wave(self, ctx, count: str = "3"):
        """Add songs from My Wave to the queue (!mywave [count])."""
        if not self.music_player:
            await ctx.send("Музыкальный плеер недоступен.")
            return
        
        try:
            count_num = int(count)
            if count_num < 1 or count_num > 10:
                await ctx.send("Количество треков должно быть от 1 до 10.")
                return
        except ValueError:
            count_num = 3  # Default if invalid
            
        success, message = self.music_player.add_yandex_wave_tracks(count_num)
        await ctx.send(message)
    
    @commands.command(name='togglewave')
    async def toggle_wave(self, ctx):
        """Toggle automatic addition of tracks from My Wave when queue is empty."""
        if not self.music_player:
            await ctx.send("Музыкальный плеер недоступен.")
            return
        
        # Check if user is a mod or broadcaster
        if not (ctx.author.is_mod or ctx.author.name.lower() == ctx.channel.name.lower()):
            await ctx.send("Только модераторы могут изменять настройки Моей Волны.")
            return
            
        success, message = self.music_player.toggle_auto_play_from_wave()
        await ctx.send(message)