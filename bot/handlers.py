import re
from telegram.ext import _application
from .utility import (
    json_key_update, find_creds, async_json_key_update, encode_label, decode_label
)
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    MessageEntity
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ApplicationBuilder,
    CallbackContext,
    filters
)
from .construct import Config, States, RES
from typing import Dict, List, Optional, Any
from datetime import time as dt_time
from zoneinfo import ZoneInfo
from collections import defaultdict

PROFILE_MANAGER = None
USER_MAP = None


def _list_to_dict(keys, values, placeholder="⬜⬜⬜"):
    return {
        key: values[i] if i < len(values) else placeholder
        for i, key in enumerate(keys)
    }


def _outline_creds(creds: dict | Profile) -> str:
    def is_blank(val):
        return (
                val is None
                or val == ''
                or val == 0
                or val == 0.0
                or (isinstance(val, str) and val.strip() == '')
                or (isinstance(val, list) and not val)
        )

    lines = []
    for key, fa_key in RES.CREDS_FA.items():
        value = creds.get(key)
        if is_blank(value):
            value = "⬜⬜⬜"
        elif isinstance(value, list):
            value = ', '.join(map(str, value))
        lines.append(f"\n<b>{fa_key}</b> : {value}")
    return ''.join(lines)


def apply_entities(text: str, entities: list[MessageEntity]) -> str:
    """
    Fully supports nested and overlapping Telegram entities.
    Converts entities to HTML using index-based insertion.
    """
    if not entities:
        return text

    tag_map = RES.TAGS_MAP
    insertions = defaultdict(list)

    for entity in entities:
        start = entity.offset
        end = start + entity.length

        if entity.type == 'text_link':
            insertions[start].append(f'<a href="{entity.url}">')
            insertions[end].append('</a>')
        elif entity.type in tag_map:
            open_tag, close_tag = tag_map[entity.type][0], tag_map[entity.type][1]
            insertions[start].append(open_tag)
            insertions[end].insert(0, close_tag)

    # Build final string
    result = []
    for i in range(len(text) + 1):
        if i in insertions:
            result.extend(insertions[i])
        if i < len(text):
            result.append(text[i])

    return ''.join(result)


async def _del_res(
        user_id,
        msg,
        text,
        context: ContextTypes.DEFAULT_TYPE,
        reply_markup=None,
        edit_message=False,
        msg_id_edit=None,
        parse_mode="HTML"
):
    # respond_and_delete:
    if edit_message:
        sent = await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=msg_id_edit,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup

        )
    else:
        sent = await context.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup

        )
    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    return sent


def register(app: _application.Application) -> None:
    labels = RES.LABELS
    show_temps_pattern = re.compile(f"^({'|'.join(map(re.escape, RES.TEMPS.keys()))})$")

    common_menu = [
        MessageHandler(filters.Regex(f"^{labels['12']}$"), show_profile),
        CallbackQueryHandler(on_edit_profile, pattern=f"^{labels['4']}$"),
        MessageHandler(filters.Regex(f"^{labels['13']}$"), show_settings),
        MessageHandler(filters.Regex(f"^{labels['25']}$"), content_creation),
        MessageHandler(filters.Regex(f"^{labels['21']}$"), edit_profile),
        MessageHandler(filters.Regex(f"^{labels['2']}$"), back_to_main),
        MessageHandler(filters.Regex(f"^{labels['30']}$"), about),
        MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
    ]
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.MAIN_MENU_STUDENT: common_menu,
            States.MAIN_MENU_ADMIN:
                [MessageHandler(filters.Regex(f"^{labels['24']}$"), export_profiles)] + common_menu,
            States.TEMPLATES: [
                MessageHandler(filters.Regex(f"^{labels['2']}$"), back_to_main),
                MessageHandler(filters.Regex(f"^{labels['26']}$"), content_temps),
                MessageHandler(filters.Regex(show_temps_pattern), show_temps),
                CallbackQueryHandler(on_edit_temp, show_temps_pattern),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_temp)
            ],
            States.SIGN_UP_STEPS: [
                CallbackQueryHandler(on_signup, pattern=f"^{labels['1']}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, signup_get_info_typed),
                CallbackQueryHandler(sign_up_cancel, pattern="^cancel_signup$"),
                CallbackQueryHandler(signup_get_info_button, pattern="^signup_info:"),
                CallbackQueryHandler(next_signup, pattern="^next_signup$")
            ],
            States.SETTINGS: [
                MessageHandler(filters.Regex(f"^{labels['14']}$"), set_scale),
                MessageHandler(filters.Regex(f"^{labels['2']}$"), back_to_main),
                MessageHandler(filters.Regex(f"^{labels['28']}|{labels['29']}$"), toggle_reserve)
            ],
            States.EDIT_PROFILE: [
                MessageHandler(filters.Regex(f"^{labels['22']}|{labels['23']}$"), show_options),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_option)
            ],
            States.SCALE: [
                MessageHandler(filters.Regex(
                    f"^({re.escape(labels['15'])}"
                    f"|{re.escape(labels['16'])})$"),
                    change_scale),
                MessageHandler(filters.Regex(f"^{labels['2']}$"), back_to_main)
                ,
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_y_link, pattern="^y_link:"))
    app.add_handler(CallbackQueryHandler(on_y_signup, pattern="^y_verify:"))
    app.add_handler(CallbackQueryHandler(on_no, pattern="^no$"))
    weekly_job(app)

    content_creation_conv = ConversationHandler(
        entry_points=['on_content_creation'],
        states={

        },
        fallbacks=['back']
    )
    settings_conv = ConversationHandler(
        entry_points=['on_settings'],
        states={

        },
        fallbacks=['back']
    )
    signup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_signup, pattern=f"^{labels['1']}$")],
        states={
            States.NEXT_STEP: [CallbackQueryHandler(next_signup, pattern="^next_signup$")],
            States.GET_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, signup_get_info_typed),
                              CallbackQueryHandler(signup_get_info_button, pattern="^signup_info:")]
        },
        fallbacks=[CallbackQueryHandler(sign_up_cancel, pattern="^cancel_signup$")]
    )
    common_hs = [
        settings_conv
    ]
    main_conv = ConversationHandler(
        entry_points=['start'],
        states={
            Admin: common_hs + [],
            Student: common_hs + [],
            Unregistered: signup_conv,

        },
        fallbacks=[]
    )


def weekly_job(app):
    job_queue = app.job_queue
    notification_time = dt_time(hour=RES.NOTIF_TIME, minute=0, tzinfo=ZoneInfo("Asia/Tehran"))
    job_queue.run_daily(
        callback=weekly_notification,
        time=notification_time,
        days=(3,),
        name="weekly_notification",
    )
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    return await start(update, context)
async def change_scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user_id = update.effective_user.id
    msg = update.message
    scale_msg = user_data.get('scale_msg')
    if scale_msg:
        scale_msg_id = scale_msg.id
        await context.bot.delete_message(chat_id=user_id, message_id=scale_msg_id)

    profile = PROFILE_MANAGER.get(user_id)
    if msg.text.strip() == RES.LABELS['15']:
        profile.adjust_scale(True)
    elif msg.text.strip() == RES.LABELS['16']:
        profile.adjust_scale(False)
    await PROFILE_MANAGER.save(user_id)
    sent = await _del_res(user_id, msg, str(profile), context)
    user_data['scale_msg'] = sent
    return States.SCALE
async def set_scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    await _del_res(user_id,
                   msg,
                   RES.LABELS['14'],
                   context,
                   reply_markup=make_menu_keyboard("scale"))
    return States.SCALE
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    msg = update.message
    sent = await _del_res(user_id,
                          msg,
                          RES.LABELS['13'],
                          context,
                          reply_markup=make_menu_keyboard("settings", user_id=user_id))
    context.user_data['settings'] = sent.message_id
    return States.SETTINGS
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    keyboard = make_menu_inline('edit_profile')  # not implemented yet
    text = (
        "<b>پروفایل من</b>\n"
        f"{PROFILE_MANAGER.get(user_id)}"
    )
    await _del_res(user_id, msg, text, context, reply_markup=None)
    return States.MAIN_MENU_STUDENT
async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    msg = update.message
    user_data = context.user_data
    pass
async def on_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_type = context.user_data.get('user_type')
    if user_type == 'admin' or user_type == 'student':
        # make an “empty” Profile for this user
        user_id = update.effective_user.id
        profile = PROFILE_MANAGER.get(user_id)
        msg_id = query.message.message_id
        context.user_data['profile'] = profile
        context.user_data['signup_msg_id'] = msg_id

        await context.bot.edit_message_reply_markup(
            message_id=msg_id,
            chat_id=user_id,
            reply_markup=make_menu_inline('prof_edit')
        )
        return
async def on_edit_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    context.user_data['temp_msg_id'] = query.message.message_id
    context.user_data['temp'] = query.data
    await context.bot.send_message(
        chat_id=user_id,
        text="قالب جدید رو بفرست ادمین جان!"
    )
    return
async def on_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return
async def on_y_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    _, chat_id = query.data.split(':')
    profile = PROFILE_MANAGER.get(chat_id)
    profile.is_verified = True
    await PROFILE_MANAGER.save(chat_id)
    await about(update, context, user_id=chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "لطفا برای مشاهده منو دوباره ربات رو استارت بزن: /start"
        )
    )
    return
async def on_y_link(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str = None) -> None:
    query = update.callback_query
    await query.answer()
    _, chat_id = query.data.split(':')

    if not link:
        await query.edit_message_reply_markup(reply_markup=None)

    await context.bot.send_message(
        chat_id=Config.GROUP_ID,
        message_thread_id=Config.G_ID_TA,
        text=link
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text="لینک "
             f"<a href='{link}'>خبر</a>"
             " تایید شد.",
        parse_mode="HTML"
    )




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    chat_id = update.effective_chat.id
    recognize_user(chat_id, user_data)
    user_data['started'] = True
    p = user_data.get('profile')
    first_name = getattr(p, 'first_name', '')
    last_name = getattr(p, 'last_name', '')
    USER_MAP = {
        'admin': {
            'text': "ادمین عزیز خوش اومدی",
            'markup': make_menu_keyboard("admin"),
            'return_obj': States.MAIN_MENU_ADMIN
        },
        'student': {
            'text': f"دانشجوی عزیز {first_name} {last_name} خوش آمدید",
            'markup': make_menu_keyboard("student"),
            'return_obj': States.MAIN_MENU_STUDENT
        },
        'unverified': {
            'text': "ادمین سرش شلوغه هنوز ثبت نامتو تایید نکرده!!",
            'markup': None,
            'return_obj': None
        },
        'unregistered': {
            'text': "دوست گرامی شما هنوز عضو نشده‌‌ای!",
            'markup': make_menu_inline("unregistered"),
            'return_obj': States.SIGN_UP_STEPS
        },
    }
    user_type = user_data.get('user_type', 'unregistered')
    cfg = USER_MAP.get(user_type)
    next_menu = cfg['return_obj']
    await context.bot.send_message(chat_id=chat_id,
                                   text=cfg['text'],
                                   reply_markup=cfg['markup'])
    return next_menu



def _del_dict_items(dict, items_keys:set):
    for key in items_keys:
        del dict[key]
    return
async def _render_signup_step(chat_id: int, msg_id: int, context):
    profile = context.user_data['profile']
    step = context.user_data['sign_up_step']
    c_field = RES.STEP_FIELDS[step]
    is_multi = c_field in RES.MULTI_FIELDS
    is_chosable = c_field in RES.CHOOSE_FIELDS
    fa_name = RES.CREDS_FA[c_field]

    # get dict for outline_creds
    creds_dict = _list_to_dict(RES.STEP_FIELDS, [
        profile.__dict__.get(k, "⬜⬜⬜") for k in RES.STEP_FIELDS
    ])
    outline = _outline_creds(creds_dict)

    # pick keyboard
    base_menu = f"signup_step:{step}"
    if is_multi:
        footnote = (
            "• میتونی هر چندتا که میخوای انتخاب کنی\n"
            "• وقتی تموم شد دکمه 'مرحله بعد' رو بزن"
        )
        keyboard = make_menu_inline(f"{base_menu}, next_signup, cancel_signup")
        action = "انتخاب یا تایپ کن"
    else:
        footnote = ""
        keyboard = make_menu_inline(f"{base_menu}, cancel_signup")
        if is_chosable:
            action = "انتخاب یا تایپ کن"
        else:
            action = "تایپ کن"

    text = (
        "<b>پروفایل من</b>\n"
        f"{outline}\n\n\n\n"
        f"<b>حالا لطفاً {fa_name} خودت رو {action}\n {footnote}</b>"
    )

    for row in keyboard.inline_keyboard:
        for btn in row:
            cb_data = btn.callback_data
            if not cb_data or len(cb_data.encode("utf-8")) > 64:
                print(f"INVALID: {cb_data}")
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return States.NEXT_STEP

async def on_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # make an “empty” Profile for this user
    user_id = update.effective_user.id
    profile = Profile(
        first_name="", last_name="", user_id=user_id,
        study_field="", student_id=0, email="",
        phone_number=0, degree="", university=""
    )

    context.user_data['profile'] = profile
    context.user_data['signup_step'] = 0
    context.user_data['signup_msg_id'] = query.message.message_id

    prompt = RES.CREDS_FA[RES.STEP_FIELDS[0]]
    keyboard = make_menu_inline('cancel_signup')
    await query.edit_message_text(
        text=f"\n سلااام! لطفاً <b>{prompt}</b> خودت رو وارد کن",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return States.GET_INFO
async def next_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data = context.user_data
    # just bump step
    user_data['sign_up_step'] += 1
    if user_data['sign_up_step'] >= 10:
        _del_dict_items(user_data, {'profile', 'signup_step', 'signup_msg_id'})
        await sign_up_end(update, context)

        return END
    else:
        await _render_signup_step(query.message.chat_id, query.message.message_id, context)
        return States.GET_INFO
async def signup_get_info_typed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    user_data = context.user_data
    user_id = update.effective_user.id
    signup_msg_id = user_data.get('signup_msg_id')
    profile = user_data.get('profile')
    step = user_data.get('sign_up_step')
    c_field = RES.STEP_FIELDS[step]
    is_multi = c_field in RES.MULTI_FIELDS
    # save the text
    value = msg.text.strip()

    if c_field in ('student_id', 'phone_number'):
        try:
            value = int(value)
        except ValueError:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Invalid input for {c_field},"
                     f" please enter a number.")
            return

    if is_multi:
        list_attr = getattr(profile, c_field)
        if value not in list_attr:
            list_attr.append(value)
    else:
        setattr(profile, c_field, value)
        user_data['sign_up_step'] += 1

    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)

    # render next
    await _render_signup_step(user_id, signup_msg_id, context)
async def signup_get_info_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg = query.message
    user_data = context.user_data
    user_id = update.effective_user.id
    signup_msg_id = user_data['signup_msg_id']
    profile = user_data['profile']
    step = user_data['sign_up_step']
    c_field = RES.STEP_FIELDS[step]
    is_multi = c_field in RES.MULTI_FIELDS

    # record the choice
    choice = query.data.split("signup_info:")[1]
    choice = decode_label(choice, RES.LABEL_CALLBACK_MAP)
    if is_multi:
        list_attr = getattr(profile, c_field)
        if choice not in list_attr:
            list_attr.append(choice)
    else:
        setattr(profile, c_field, choice)
        user_data['sign_up_step'] += 1

    # re‑render
    await _render_signup_step(user_id, signup_msg_id, context)
async def sign_up_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data = context.user_data
    user_id = update.effective_user.id

    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=user_data['signup_msg_id'],
        text=(
            "ثبت نام شما کنسل شد"
        ),
        reply_markup=make_menu_inline("unregistered")
    )
    return States.MAIN_MENU_STUDENT
async def sign_up_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = context.user_data
    profile = user_data['profile']
    PROFILE_MANAGER.add_profile(user_id, profile)
    await PROFILE_MANAGER.save(user_id)
    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=user_data['signup_msg_id'],
        text=(
            "تبریک میگم اطلاعات شما با موفقیت ثبت شد. منتظر تایید ادمین باش ^_*"
        )
    )
    admin_scale = PROFILE_MANAGER.get(Config.ADMIN_ID).scale
    profile.scale = admin_scale
    await context.bot.send_message(
        chat_id=Config.ADMIN_ID,
        text=(
            "ادمین عزیز یک نفر جدید به جمع ما پیوسته آیا تاییدش می‌کنی؟\n"
            "<b>اطلاعات فرد:</b>\n"
            f"{profile}\n"
            f'<a href="tg://user?id={user_id}">link to user</a>'
        ),
        parse_mode="HTML",
        reply_markup=make_menu_inline("user_verify", user_id=user_id)
    )
    profile.scale = 38
    return




async def weekly_notification(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ids = PROFILE_MANAGER.user_ids_self_reserve()
    for uid in user_ids:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "📢 چهارشنبه شما بخیر باشه؛ یادآوری می‌کنم غذای سلف هفته رو رزرو کنی\n\n "
                '<a href="https://self.umz.ac.ir/">اینجا کلیک کن</a> *ـ^'
            ),
            parse_mode="HTML"
        )


def recognize_user(user_id: int, user_data):
    user_data['profile'] = PROFILE_MANAGER.get(user_id)
    if user_id == Config.ADMIN_ID:
        user_data['user_type'] = 'admin'
    elif user_data['profile']:
        if user_data['profile'].is_verified:
            user_data['user_type'] = 'student'
        else:
            user_data['user_type'] = 'unverified'
    else:
        user_data['user_type'] = 'unregistered'

    return user_data['user_type']


async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    await _del_res(user_id,
                   msg,
                   RES.LABELS['21'],
                   context,
                   reply_markup=make_menu_keyboard("p_edit_options"))
    return States.EDIT_PROFILE


async def show_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    profile = PROFILE_MANAGER.get(user_id)
    if msg.text == RES.LABELS['22']:
        await _del_res(user_id,
                       msg,
                       RES.LABELS['22'],
                       context,
                       reply_markup=make_menu_keyboard("skills"))
        sent = await context.bot.send_message(chat_id=user_id, text=profile.skills, )
    elif msg.text == RES.LABELS['23']:
        await _del_res(user_id,
                       msg,
                       RES.LABELS['23'],
                       context,
                       reply_markup=make_menu_keyboard("interests"))
    return States.EDIT_PROFILE


async def export_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    PROFILE_MANAGER.export()
    await context.bot.send_document(chat_id=Config.ADMIN_ID,
                                    document=RES.EXPORT_PATH
                                    )


async def content_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    await _del_res(user_id,
                   msg,
                   RES.LABELS['25'],
                   context,
                   reply_markup=make_menu_keyboard('content_creation')
                   )
    return States.TEMPLATES


async def content_temps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    await _del_res(user_id,
                   msg,
                   RES.LABELS['26'],
                   context,
                   reply_markup=make_menu_keyboard('temps')
                   )
    return States.TEMPLATES


async def show_temps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    if user_id == Config.ADMIN_ID:
        keyboard = make_menu_inline('edit_temp', temp_name=msg.text)
    else:
        keyboard = None
    template = RES.TEMPS[msg.text]
    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    await context.bot.send_message(chat_id=user_id, text=msg.text + '⬇️')
    await context.bot.send_message(
        chat_id=user_id,
        text=template,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return


async def edit_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    user_data = context.user_data
    temp_msg_id = user_data['temp_msg_id']
    temp_name = user_data['temp']
    text = apply_entities(msg.text, list(msg.entities))
    RES.TEMPS[temp_name] = text
    await RES.update("temps", RES.TEMPS)
    await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=temp_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=make_menu_inline('edit_temp', temp_name=temp_name)
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=temp_name + " با موفقیت تغییر یافت! "
    )
    return


async def toggle_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    profile = PROFILE_MANAGER.get(user_id)
    new_state = not profile.self_reserve
    profile.self_reserve = new_state
    text = 'یاداور روشن شد' if new_state else 'یاداور خاموش شد'
    await PROFILE_MANAGER.save(user_id)
    await _del_res(
        user_id,
        msg,
        text,
        context,
        reply_markup=make_menu_keyboard('settings', user_id=user_id)
    )


def make_menu_keyboard(menu_type, user_id=None):
    if user_id:
        reserve = PROFILE_MANAGER.get(user_id).self_reserve
        reserve_button_name = '29' if reserve else '28'
    else:
        reserve_button_name = '1'

    temps = _reply_buttons(list(RES.TEMPS.keys()))
    temps.append([_reply_button('2')])
    menu_map = {
        'student':
            [
                [_reply_button('12'), _reply_button('25')],
                [_reply_button('13'), _reply_button('30')]
            ],
        'admin':
            [
                [_reply_button('12'), _reply_button('25')],
                [_reply_button('24'), _reply_button('13'), _reply_button('30')]
            ],
        'settings':
            [
                [_reply_button('14'), _reply_button(reserve_button_name)],
                [_reply_button('2')]
            ],
        'scale':
            [
                [_reply_button('15')],
                [_reply_button('16')],
                [_reply_button('2')]
            ],
        'p_edit_options':
            [
                [_reply_button('22')],
                [_reply_button('23')]
            ],
        'content_creation':
            [
                [_reply_button('26')],
                [_reply_button('2')]
            ],
        'skills': _reply_buttons('skills'),
        'interests': _reply_buttons('interests'),
        'temps': temps
    }

    buttons = menu_map.get(menu_type)
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)


def make_menu_inline(menu_types, user_id=None, temp_name=''):
    menu_map = {
        'admin':
            [

            ],
        'unregistered':
            [
                [_button('1', RES.LABELS['1'])]
            ],
        'sent_link':
            [
                [_button('10', f'y_link:{user_id}')],
                [_button('11', f'no')]
            ],
        'user_verify':
            [
                [_button('10', f'y_verify:{user_id}')],
                [_button('11', 'no')]
            ],
        'cancel_signup':
            [
                [_button('3', 'cancel_signup')]
            ],
        'next_signup':
            [
                [_button('20', 'next_signup')]
            ],
        'signup_step:2': _buttons('study_fields', 'signup_info'),
        'signup_step:4': _buttons('degrees', 'signup_info'),
        'signup_step:5': _buttons('universities', 'signup_info'),
        'signup_step:8': _buttons('interests', 'signup_info'),
        'signup_step:9': _buttons('skills', 'signup_info'),
        'edit_temp':
            [
                [_button('27', temp_name)]
            ],
        'edit_profile':
            [
                [_button('4', RES.LABELS['4'])]
            ],
        'prof_edit': _buttons(list(RES.CREDS_FA.values()), 'prof_edit_info')

    }
    buttons = []
    for menu_type in map(str.strip, menu_types.split(',')):
        buttons.extend(menu_map.get(menu_type, []))
    return InlineKeyboardMarkup(buttons)


def _reply_buttons(buttons_n):
    if isinstance(buttons_n, str):
        buttons_label = RES.LABELS[buttons_n]
    else:
        buttons_label = buttons_n
    buttons = []
    for label in buttons_label:
        buttons.append([KeyboardButton(label)])
    return buttons


def _reply_button(label):
    return KeyboardButton(RES.LABELS[label])


def _buttons(labels_name, base_tag: str) -> list[list[InlineKeyboardButton]]:
    buttons = []
    if isinstance(labels_name, str):
        labels = RES.LABELS[labels_name]
    else:
        labels = labels_name
    for label in labels:
        encoded_label = None
        if len(f"{base_tag}:{label}".encode("utf-8")) > 63:
            encoded_label = encode_label(label, RES.LABEL_CALLBACK_MAP)
        callback_data = f"{base_tag}:{encoded_label or label}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
    return buttons


def _button(label, callback_data):
    return InlineKeyboardButton(RES.LABELS[label], callback_data=callback_data)


async def save_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    user_id = user_id or update.effective_user.id
    text = (
        "سلام! 🙂‍↔️\n\n"
        "خوش اومدی به <b>انجمن</b>! برای استفاده بهتر از امکانات ربات، به بخش‌های زیر نگاهی بنداز:\n\n"
        "🍽️ <b>یادآور رزرو غذا</b>\n"
        f"هر چهارشنبه ساعت <code>{RES.NOTIF_TIME}</code> یک پیام دوستانه برات میاد تا یادت نره غذای هفته بعد رو رزرو کنی. "
        "اگه از سلف استفاده نمی‌کنی، می‌تونی این یادآور رو از <b>تنظیمات</b> خاموش کنی.\n\n"
        "📝 <b>تولید محتوا</b>\n"
        "به قسمت <b>تولید محتوا</b> سر بزن، قالب‌های آماده رو ببین و با استفاده از نکات خلاقانه نویسندگی، مطالب جذاب بنویس.\n\n"
        "👤 <b>ویرایش پروفایل</b>\n"
        "در بخش <b>پروفایل من</b> می‌تونی حوزه فعالیت و بقیهٔ جزئیات خودت رو به‌روز کنی تا همه‌چیز مطابق میلِ تو باشه.\n\n"
        "📅 <b>رویدادها</b>\n"
        "وارد بخش <b>رویدادها</b> شو تا رویدادهای نزدیک یا در حال برگزاری رو دنبال کنی یا توشون ثبت‌نام کنی (به‌زودی فعال می‌شه).\n\n"
        "🧑‍💼 <b>Admin: </b>"
        f"<a href='https://t.me/{Config.ADMIN_USERNAME}'>@{Config.ADMIN_USERNAME}</a>\n\n"
        "👷🏻 <b>Builder of SymBio: </b>"
        "<a href='https://t.me/sh_id'>@sh_id</a>\n\n"
        "💻 <b>GitHub link: </b>"
        "<a href='https://github.com/Celestios/Symbio_telegram_bot.git'>Symbio_telegram_bot</a>\n\n"
        "منتظر همراهیِ تو هستیم و امیدواریم لحظات خوبی با ربات داشته باشی! 🎉"
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
