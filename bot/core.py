#  start of something wonderful!
import logging
from telegram.ext import ApplicationBuilder
from .config import Config
from .handlers import *
from .utility import json_read


class TelegramBot:
    logging.info('TelegramBot')

    def __init__(self):
        self.app = ApplicationBuilder().token(Config.TOKEN).build()
        self.profiles = None

    def load_profiles(self):
        profiles_data = json_read(Config.database)
        self.profiles = ProfileManager(profiles_data)

    def register_handlers(self):
        handler = Handlers(self.profiles)
        handler.register(self.app)

    def run(self) -> None:
        self.app.run_polling()
