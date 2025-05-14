import json
import os

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self):
        """Load config from file or create default."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                # If config doesn't exist, create default
                config = self._get_default_config()
                self.save_config(config)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._get_default_config()
            
    def _get_default_config(self):
        """Return default configuration."""
        return {
            "client_id": "",
            "access_token": "",
            "refresh_token": "",
            "bot_username": "",
            "channels": [""],
            "channel": "",
            "player": {
                "volume": 50,
                "auto_play": True,
                "max_queue_size": 10
            },
            "yandex_music": {
                "token": "",
                "auto_play_from_wave": True
            }
        }
        
    def save_config(self, config=None):
        """Save config to file."""
        if config is None:
            config = self.config
            
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key, default=None):
        """Get a specific config value by key."""
        # Поддержка для оригинальных настроек в корне объекта конфигурации
        if key in self.config:
            return self.config[key]
            
        # Поддержка для поиска ключа в секциях twitch и player
        for section in ["twitch", "player", "yandex_music"]:
            if section in self.config and key in self.config[section]:
                return self.config[section][key]
        
        # Возвращаем значение по умолчанию, если ключ не найден
        return default
    
    def set(self, key, value):
        """Set a specific config value by key."""
        # Проверяем, есть ли ключ в секциях конфигурации
        for section in ["twitch", "player", "yandex_music"]:
            if section in self.config and key in self.config[section]:
                self.config[section][key] = value
                return True
        
        # Если ключ не найден в секциях, добавляем его в корень
        self.config[key] = value
        return True
        
    def get_twitch_config(self):
        """Get Twitch configuration."""
        if "twitch" in self.config:
            return self.config["twitch"]
        # Поддерживаем обратную совместимость
        twitch_keys = ["client_id", "access_token", "refresh_token", "bot_username", "channel", "channels"]
        twitch_config = {}
        for key in twitch_keys:
            if key in self.config:
                twitch_config[key] = self.config[key]
        return twitch_config
        
    def set_twitch_config(self, twitch_config):
        """Set Twitch configuration."""
        if "twitch" not in self.config:
            # Если секции еще нет, добавляем напрямую в корень (поддержка старого формата)
            for key, value in twitch_config.items():
                self.config[key] = value
        else:
            # Обновляем существующую секцию
            self.config["twitch"].update(twitch_config)
        
    def get_player_config(self):
        """Get player configuration."""
        return self.config.get("player", {"volume": 50, "auto_play": True, "max_queue_size": 10})
        
    def set_player_config(self, player_config):
        """Set player configuration."""
        self.config["player"] = player_config
        
    def get_player_volume(self):
        """Get player volume."""
        player_config = self.get_player_config()
        return player_config.get("volume", 50)
        
    def set_player_volume(self, volume):
        """Set player volume."""
        player_config = self.get_player_config()
        player_config["volume"] = volume
        self.set_player_config(player_config)
        
    def get_yandex_music_config(self):
        """Get Yandex Music configuration."""
        # Ensure the yandex_music section exists
        if "yandex_music" not in self.config:
            self.config["yandex_music"] = {"token": "", "auto_play_from_wave": False}
        return self.config["yandex_music"]
        
    def set_yandex_music_config(self, yandex_config):
        """Set Yandex Music configuration."""
        if "yandex_music" not in self.config:
            self.config["yandex_music"] = {}
        self.config["yandex_music"].update(yandex_config)
        # Save changes immediately to ensure they're persisted
        self.save_config()
        
    def get_yandex_auto_wave(self):
        """Get auto play from wave setting."""
        yandex_config = self.get_yandex_music_config()
        return yandex_config.get("auto_play_from_wave", False)
        
    def set_yandex_auto_wave(self, enabled):
        """Set auto play from wave setting."""
        yandex_config = self.get_yandex_music_config()
        yandex_config["auto_play_from_wave"] = enabled
        self.set_yandex_music_config(yandex_config)