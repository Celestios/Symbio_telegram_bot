#  start of something wonderful!
import logging
from telegram.ext import ApplicationBuilder
from .construct import Config
from .handlers import *
from .handlers import register
from .utility import json_read


class TelegramBot:
    logging.info('TelegramBot')

    def __init__(self):
        self.app = ApplicationBuilder().token(Config.TOKEN).build()
        self.profiles = None

    def load_profiles(self):
        self.profiles = ProfileManager(RES.DATABASE)

    def register_handlers(self):
        handler = Handlers(self.profiles)
        register(self.app)

    def run(self) -> None:
        self.app.run_polling()
