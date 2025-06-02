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
from ..construct import (
    States,
    RES,
    Config
)
from ._make_menus import make_menu_keyboard, make_menu_inline
from .main_menu import start


async def on_content_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    await _del_res(user_id,
                   msg,
                   RES.LABELS['25'],
                   context,
                   reply_markup=make_menu_keyboard('content_creation')
                   )
    return push_menu(context, States.CONTENT_OPTIONS)


async def on_content_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    if msg.text == RES.LABELS['32']:
        context.user_data['content_type'] = 'templates'
        text = RES.LABELS['26']
        keyboard_name = 'temps'
    else:
        # msg.text == RES.LABELS['26']
        context.user_data['content_type'] = 'writing_tips'
        text = RES.LABELS['32']
        keyboard_name = 'tips'

    await _del_res(user_id,
                   msg,
                   text,
                   context,
                   reply_markup=make_menu_keyboard(keyboard_name)
                   )
    return push_menu(context, States.OPTION_LIST)


async def go_back_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    prev_state = pop_menu(context)

    if prev_state == States.CONTENT_OPTIONS:
        return await on_content_creation(update, context)
    elif prev_state == States.OPTION_LIST:
        return await on_content_option(update, context)
    else:
        msg = update.message
        await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        return await start(update, context)


async def send_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    content_type = context.user_data['content_type']
    if user_id == Config.ADMIN_ID:
        keyboard = make_menu_inline('edit_content')
    else:
        keyboard = None
    if content_type == 'templates':
        text = RES.TEMPS[msg.text]
    else:
        text = RES.TIPS[msg.text]
    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    await context.bot.send_message(chat_id=user_id, text=msg.text + '⬇️')
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    context.user_data['content_sent'] = sent
    context.user_data['content_sent_name'] = msg.text
    return


async def on_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    sent = await context.bot.send_message(
        chat_id=user_id,
        text="قالب جدید رو بفرست ادمین جان!"
    )
    context.user_data['sent_new_content_ask'] = sent
    return States.EDIT_OPTION


async def edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    user_data = context.user_data
    content_type = context.user_data['content_type']
    sent_new_content_ask = context.user_data['sent_new_content_ask']
    sent_content = user_data['content_sent']
    sent_content_name = user_data['content_sent_name']
    text = apply_entities(msg.text, list(msg.entities))

    if content_type == 'templates':
        RES.TEMPS[sent_content_name] = text
        await RES.update("temps", RES.TEMPS)
    else:
        RES.TIPS[sent_content_name] = text
        await RES.update("tips", RES.TIPS)

    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    await context.bot.delete_message(chat_id=user_id, message_id=sent_new_content_ask.message_id)
    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=sent_content.message_id,
        text=text,
        parse_mode="HTML",
        reply_markup=make_menu_inline('edit_content')
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=sent_content_name + " با موفقیت تغییر یافت! "
    )
    return States.OPTION_LIST


async def editing_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


__all__ = [
    'on_content_creation',
    'on_content_option',
    'send_content',
    'on_edit_content',
    'edit_content',
    'editing_cancel',
    'go_back_content'

]
