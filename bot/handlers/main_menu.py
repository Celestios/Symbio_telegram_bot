from telegram import (
    Update
)
from telegram.ext import (
    ContextTypes
)
from ._utils import (
    recognize_user,
    get_user_text,
    get_user_state,
    push_menu
)
from ._make_menus import get_user_markup
from ..construct import (
    RES,
    Config
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user_id = update.effective_chat.id
    profile = context.bot_data.get('profile_manager').get(user_id)
    recognize_user(user_id, user_data, profile)
    user_type = user_data.get('user_type', 'unregistered')
    if user_data.get('started'):
        text = 'منوی اصلی'
    else:
        first_name = getattr(profile, 'first_name', '')
        last_name = getattr(profile, 'last_name', '')
        text = get_user_text(user_type, first_name, last_name)
        user_data['started'] = True

    await context.bot.send_message(chat_id=user_id,
                                   text=text,
                                   reply_markup=get_user_markup(user_type))
    state = get_user_state(user_type)
    return push_menu(context, state)


def prepare_borders(scale: int, title: str = '') -> dict:
    scale += 1
    title = f' {title} '
    padding = ((scale + 3) - len(title)) // 2
    top_border = f"╭{'─' * padding}{title}{'─' * padding}╮"
    bottom_border = f"╰{'─' * scale}╯"
    line = f"  {'─' * (scale + 1)}"
    return {
        "header": top_border,
        "bottom_border": bottom_border,
        "line": line
    }


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    user_id = user_id or update.effective_user.id
    scale = context.bot_data.get('profile_manager').get(user_id).scale
    borders = prepare_borders(scale, title='SymBio')
    text = (

        f"{borders['header']}\n"
        "| <b>سلام! 🙂‍↔️</b>\n"
        "| به <b>انجمن</b> خوش اومدی!\n"
        "| برای استفاده بهتر از امکانات ربات، به بخش‌های زیر نگاهی بنداز:\n"
        "\n"
        "| <b>🍽️ یادآور رزرو غذا</b>\n"
        f"| هر چهارشنبه ساعت <code>{RES.NOTIF_TIME_H}</code> پیام یادآوری می‌گیری\n"
        "| تا غذای هفته بعد رو یادت نره رزرو کنی.\n"
        "| اگه از سلف استفاده نمی‌کنی، از بخش <b>تنظیمات</b> غیرفعالش کن.\n"
        "\n"
        "| <b>📝 تولید محتوا</b>\n"
        "| به بخش تولید محتوا سر بزن، قالب‌های آماده رو ببین و\n"
        "| با نکات خلاقانه نویسندگی مطالب جذاب بنویس.\n"
        "\n"
        "| <b>👤 ویرایش پروفایل</b>\n"
        "| در بخش پروفایل من می‌تونی حوزه فعالیت و جزئیاتت رو\n"
        "| به‌روز کنی تا مطابق میلت باشه.\n"
        "\n"
        "| <b>📅 رویدادها</b>\n"
        "| وارد بخش رویدادها شو و رویدادهای فعال رو دنبال کن یا ثبت‌نام کن\n"
        "| (به‌زودی فعال می‌شه).\n"
        f"{borders['line']}\n"
        "\n"
        "  <b>🧑‍💼 Admin:</b> "
        f"<a href='https://t.me/{Config.ADMIN_USERNAME}'>@{Config.ADMIN_USERNAME}</a>\n"
        "  <b>👷🏻 Builder:</b> "
        "<a href='https://t.me/sh_id'>@sh_id</a>\n"
        "  <b>💻 GitHub:</b> "
        "<a href='https://github.com/Celestios/Symbio_telegram_bot.git'>Symbio_telegram_bot</a>\n"
        f"{borders['bottom_border']}\n"
        "منتظر همراهیِ تو هستیم و امیدواریم لحظات خوبی با ربات داشته باشی! 🎉"
    )

    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def export_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data.get('profile_manager').export()
    await context.bot.send_document(chat_id=Config.ADMIN_ID, document=RES.EXPORT_PATH)


__all__ = [
    'about',
    'start',
    'export_profiles'
]
