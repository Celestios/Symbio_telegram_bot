from bot.core import TelegramBot
import argparse
import logging


def main():
    parser = argparse.ArgumentParser(description="Run Telegram Bot with optional configurations.")
    parser.add_argument(
        "--updated",
        action="store_true",
        help="If set, notify all users about the update"
    )

    args = parser.parse_args()
    bot = TelegramBot(updated=args.updated)
    bot.load_profiles()
    bot.register_handlers()
    bot.run()


if __name__ == "__main__":
    main()
