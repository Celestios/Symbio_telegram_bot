from telegram import (
    Update
)
from telegram.ext import (
    ContextTypes
)
from ._make_menus import (
    make_menu_inline
)
from ._utils import (
    _del_res,
    _outline_creds,
    decode_label,
    get_user_state,
    push_menu,
    pop_menu
)
from ..construct import (
    States,
    RES
)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, active=True):
    user_id = update.effective_user.id
    msg = update.message
    user_profile = context.bot_data.get('profile_manager').get(user_id)
    keyboard = make_menu_inline('edit_profile')
    text = (
        "<b>پروفایل من</b>\n"
        f"{user_profile}"
    )
    if active:
        sent = await _del_res(user_id, msg, text, context, reply_markup=keyboard)
        context.user_data['profile_msg'] = sent

    else:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    return get_user_state(context.user_data.get('user_type'))


async def _render_edit_profile(context: ContextTypes.DEFAULT_TYPE):
    msg = context.user_data.get('prof_edit_msg')
    user_id = msg.chat_id
    profile_manager = context.bot_data['profile_manager']
    profile = profile_manager.get(user_id)

    if profile is None:
        profile = profile_manager.add_profile(user_id, new=True)

    if profile.is_signed_up:
        keyboard = make_menu_inline(['creds_edit_options', 'profile_edit_general_options'])
    else:
        keyboard = make_menu_inline(['creds_edit_options', 'signup_general_options'])

    text = (
            _outline_creds(profile) +
            "\n\nدوست خوبم، هرکدوم از گزینه‌ها رو یکی‌یکی انتخاب کن و فرم بالا رو پر کن تا ثبت‌ نام بشی."
    )

    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=msg.message_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML")


async def on_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['prof_edit_msg'] = query.message
    await _render_edit_profile(context)
    return push_menu(context, States.CHOSEN_CRED)


async def _render_cred_edit(context: ContextTypes.DEFAULT_TYPE):
    msg = context.user_data.get('prof_edit_msg')
    user_id = msg.chat_id
    c_field = context.user_data.get('c_field')
    fa_name = RES.CREDS_FA.get(c_field, c_field)
    is_multi = c_field in RES.MULTI_FIELDS
    is_choose_able = c_field in RES.CHOOSE_FIELDS
    profile = context.bot_data.get('profile_manager').get(user_id)
    outline = _outline_creds(profile.get_creds())
    keyboard = make_menu_inline([c_field, 'back'])
    if is_multi:
        footnote = (
            "• میتونی هر چندتا که میخوای انتخاب کنی\n"
            "• وقتی تموم شد دکمه 'مرحله بعد' رو بزن"
        )
        action = "انتخاب یا تایپ کن"

    else:
        footnote = ""
        action = "انتخاب یا تایپ کن" if is_choose_able else "تایپ کن"

    text = (
        "<b>پروفایل من</b>\n"
        f"{outline}\n\n\n\n"
        f"<b>حالا لطفاً {fa_name} خودت رو {action}\n {footnote}</b>"
    )

    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=msg.message_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def on_cred_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, c_field = query.data.split(':')
    context.user_data['c_field'] = c_field
    await _render_cred_edit(context)

    return push_menu(context, States.GET_INFO)


async def _update_profile_field(context, user_id, c_field, value, from_message=False, message=None):
    profile_manager = context.bot_data.get('profile_manager')
    profile = profile_manager.get(user_id)
    is_multi = c_field in RES.MULTI_FIELDS

    # Convert value type for typed input
    if from_message and c_field in ('student_id', 'phone_number'):
        value = int(value)

    if is_multi:
        list_attr = getattr(profile, c_field)
        if value in list_attr:
            list_attr.remove(value)
        else:
            list_attr.append(value)
        await profile_manager.save(user_id)
        if from_message and message:
            await context.bot.delete_message(chat_id=user_id, message_id=message.message_id)
        await _render_cred_edit(context)
        return States.GET_INFO

    else:
        setattr(profile, c_field, value)
        await profile_manager.save(user_id)
        if from_message and message:
            await context.bot.delete_message(chat_id=user_id, message_id=message.message_id)
        await _render_edit_profile(context)
        return States.CHOSEN_CRED


async def edit_profile_get_info_typed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = update.effective_user.id
    c_field = context.user_data.get('c_field')
    value = msg.text.strip()
    return await _update_profile_field(context, user_id, c_field, value, from_message=True, message=msg)


async def edit_profile_get_info_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    c_field = context.user_data.get('c_field')
    _, raw_value = query.data.split(":")
    value = decode_label(raw_value, RES.LABEL_CALLBACK_MAP)
    return await _update_profile_field(context, user_id, c_field, value)


async def cancel_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    for var in ['prof_edit_msg', 'c_field', ]:
        try:
            del context.user_data[var]
        except KeyError:
            pass
    user_id = update.effective_user.id
    profile_manager = context.bot_data.get('profile_manager')
    profile_manager.delete_profile(user_id)
    await profile_manager.save(user_id)
    await query.edit_message_text(text="ثبت نام شما لغو شد", reply_markup=make_menu_inline('unregistered'))
    return States.UNREGISTERED


async def end_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()
    profile = context.bot_data.get('profile_manager').get(user_id)
    if profile.is_complete():
        for var in ['prof_edit_msg', 'c_field', ]:
            del context.user_data[var]
        profile.is_signed_up = True
        profile.save()
        recognize_user(user_id, context.user_data, profile)
        await show_profile(update, context, active=False)
        return get_user_state(context.user_data['user_type'])
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="اطلاعاتت کامل نشده هنوز"
        )
        return None


async def go_back_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prev_state = pop_menu(context)
    if prev_state == States.CHOSEN_CRED:
        return await on_edit_profile(update, context)
    elif prev_state == States.GET_INFO:
        return await on_cred_edit(update, context)
    else:
        return await show_profile(update, context, active=False)


# async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     msg = update.message
#     await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
#     return await start(update, context)
# async def on_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     query = update.callback_query
#     await query.answer()
#     await query.edit_message_reply_markup(reply_markup=None)
#     return
# async def on_y_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     await query.edit_message_reply_markup(reply_markup=None)
#     _, chat_id = query.data.split(':')
#     profile = PROFILE_MANAGER.get(chat_id)
#     profile.is_verified = True
#     await PROFILE_MANAGER.save(chat_id)
#     await about(update, context, user_id=chat_id)
#     await context.bot.send_message(
#         chat_id=chat_id,
#         text=(
#             "لطفا برای مشاهده منو دوباره ربات رو استارت بزن: /start"
#         )
#     )
#     return
# async def on_y_link(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str = None) -> None:
#     query = update.callback_query
#     await query.answer()
#     _, chat_id = query.data.split(':')
#
#     if not link:
#         await query.edit_message_reply_markup(reply_markup=None)
#
#     await context.bot.send_message(
#         chat_id=Config.GROUP_ID,
#         message_thread_id=Config.G_ID_TA,
#         text=link
#     )
#     await context.bot.send_message(
#         chat_id=chat_id,
#         text="لینک "
#              f"<a href='{link}'>خبر</a>"
#              " تایید شد.",
#         parse_mode="HTML"
#     )
# def _del_dict_items(dict, items_keys: set):
#     for key in items_keys:
#         del dict[key]
#     return


__all__ = [
    'show_profile',
    'on_edit_profile',
    'on_cred_edit',
    'edit_profile_get_info_typed',
    'edit_profile_get_info_button',
    'end_signup',
    'cancel_profile',
    'go_back_profile'
]
