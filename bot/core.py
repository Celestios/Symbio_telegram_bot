#  start of something wonderful!
import logging
from telegram.ext import ApplicationBuilder
from .construct import Config
from .handlers import *
from .handlers import register
from .utility import json_read


class TelegramBot:
    logging.info('TelegramBot')

    def __init__(self, updated=False):
        self.app = ApplicationBuilder().token(Config.TOKEN).build()
        self.updated = updated
        self.handlers = None
        self.profiles = None

    def load_profiles(self):
        self.profiles = ProfileManager(RES.DATABASE)

    def register_handlers(self):
        self.handlers = Handlers(self.profiles)
        register(self.app)

    async def post_run_actions(self):
        if self.updated:
            await self.handlers.send_updated()

    def run(self) -> None:
        self.app.post_init = post_run_actions
        self.app.run_polling()
