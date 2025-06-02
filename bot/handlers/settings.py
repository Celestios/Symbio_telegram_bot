from telegram import (
    Update
)
from telegram.ext import (
    ContextTypes
)
from ._utils import (
    push_menu,
    pop_menu,
    _del_res
)
from ._make_menus import (
    make_menu_keyboard
)
from .main_menu import start
from ..construct import (
    States,
    RES
)
from datetime import time as dt_time
from zoneinfo import ZoneInfo


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    msg = update.message
    reserve = context.bot_data.get('profile_manager').get(user_id).self_reserve
    sent = await _del_res(user_id,
                          msg,
                          RES.LABELS['13'],
                          context,
                          reply_markup=make_menu_keyboard("settings", reserve=reserve))
    context.user_data['settings'] = sent.message_id
    return push_menu(context, States.SETTINGS)


async def _reserve_notif_one(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ids = context.bot_data.get('profile_manager').user_ids_self_reserve()
    for uid in user_ids:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "📢 چهارشنبه شما بخیر باشه؛ یادآوری می‌کنم غذای سلف هفته رو رزرو کنی\n\n "
                '<a href="https://self.umz.ac.ir/">اینجا کلیک کن</a> *ـ^'
            ),
            parse_mode="HTML"
        )


async def _reserve_notif_two(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ids = context.bot_data.get('profile_manager').user_ids_self_reserve()
    for uid in user_ids:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "📢 پنج شنبه شما بخیر باشه؛ برای رزرو غذا امروز اخرین مهلتت هست؛ یادت نره هااا\n\n "
                '<a href="https://self.umz.ac.ir/">اینجا کلیک کن</a> *ـ^'
            ),
            parse_mode="HTML"
        )


def weekly_job(app):
    job_queue = app.job_queue
    notif_time_first = dt_time(hour=RES.NOTIF_TIME_H, minute=RES.NOTIF_TIME_M, tzinfo=ZoneInfo("Asia/Tehran"))
    job_queue.run_daily(
        callback=_reserve_notif_one,
        time=notif_time_first,
        days=(RES.NOTIF_TIME_D,),
        name="weekly_notification",
    )
    notif_time_second = dt_time(hour=RES.NOTIF_TIME_H, minute=RES.NOTIF_TIME_M, tzinfo=ZoneInfo("Asia/Tehran")
                                )
    job_queue.run_daily(
        callback=_reserve_notif_two,
        time=notif_time_second,
        days=(RES.NOTIF_TIME_D + 1,),
        name="second_weekly_notification",
    )


async def toggle_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    profile_manager = context.bot_data.get('profile_manager')
    profile = profile_manager.get(user_id)
    new_state = not profile.self_reserve
    profile.self_reserve = new_state
    text = 'یاداور روشن شد' if new_state else 'یاداور خاموش شد'
    await profile_manager.save(user_id)
    await _del_res(
        user_id,
        msg,
        text,
        context,
        reply_markup=make_menu_keyboard('settings', profile.self_reserve)
    )


async def set_scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    profile = context.bot_data.get('profile_manager').get(user_id)

    await _del_res(user_id,
                   msg,
                   RES.LABELS['14'],
                   context,
                   reply_markup=make_menu_keyboard("scale"))
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=str(profile),
        parse_mode='HTML'
    )
    context.user_data['scale_msg'] = sent
    return push_menu(context, States.SCALE)


async def change_scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user_id = update.effective_user.id
    msg = update.message
    sent_msg = user_data.get('scale_msg')
    profile_manager = context.bot_data.get('profile_manager')
    profile = profile_manager.get(user_id)
    if msg.text.strip() == RES.LABELS['15']:
        if profile.adjust_scale(True) is False:
            pass
    elif msg.text.strip() == RES.LABELS['16']:
        if profile.adjust_scale(False) is False:
            pass
    await profile_manager.save(user_id)
    sent = await _del_res(user_id, msg, str(profile), context, msg_id_edit=sent_msg.message_id)
    user_data['scale_msg'] = sent


async def go_back_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prev_state = pop_menu(context)
    if prev_state == States.SETTINGS:
        return await show_settings(update, context)
    elif prev_state == States.SCALE:
        return await set_scale(update, context)
    else:
        msg = update.message
        await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        return await start(update, context)


__all__ = [
    'show_settings',
    'weekly_job',
    'toggle_reserve',
    'set_scale',
    'change_scale',
    'go_back_setting'

]
