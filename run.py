from bot.core import TelegramBot
import logging


def main():
    logging.basicConfig(level=logging.INFO)
    bot = TelegramBot()
    bot.load_profiles()
    bot.register_handlers()
    bot.run()


if __name__ == "__main__":
    main()
