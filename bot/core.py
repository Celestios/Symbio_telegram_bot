#  start of something wonderful!
from telegram.ext import ApplicationBuilder
from .construct import Config, RES
from .handlers import register
from .profiles import ProfileManager


async def send_updated_msg(app):

    for usr_id in app.bot_data.get('profile_manager').user_ids():
        try:
            await app.bot.send_message(chat_id=usr_id,
                                       text=(
                                           "ربات آپدیت شد، برای استفاده دوباره استارت بزنید:  "
                                           "/start"))
        except error.BadRequest:
            print(f"chat {usr_id} not found to send updated message")


class TelegramBot:

    def __init__(self, updated=False):
        self.app = ApplicationBuilder().token(Config.TOKEN).build()
        self.updated = updated

    def load_profiles(self):
        self.app.bot_data['profile_manager'] = ProfileManager(RES.DATABASE)

    def register_handlers(self):
        register(self.app)

    async def post_run_actions(self, app):
        if self.updated:
            await send_updated_msg(app)


    def run(self) -> None:
        self.app.post_init = self.post_run_actions
        self.app.run_polling()
