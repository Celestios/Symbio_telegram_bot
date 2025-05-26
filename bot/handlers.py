import logging
import re
from openpyxl.worksheet.filters import Filters
from telegram.ext import _application
from .utility import (
    log_calls, json_key_update, find_creds,
    find_link, async_json_key_update, json_read, encode_label, decode_label
)
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    MessageEntity,
    error
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
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from itertools import islice
from datetime import time as dt_time
from zoneinfo import ZoneInfo
from collections import defaultdict


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


@dataclass
class Profile:
    first_name: str
    last_name: str
    user_id: int
    study_field: str
    student_id: int
    email: str
    phone_number: int
    degree: str
    university: str
    is_verified: bool = False
    skills: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    scale: int = 38
    self_reserve: bool = False

    def __str__(self) -> str:
        sections = [
            ("نام", self.full_name()),
            ("رشته تحصیلی", self.study_field),
            ("شماره دانشجویی", self.student_id),
            ("ایمیل", self.email),
            ("شماره تماس", self.phone_number),
            ("مقطع تحصیلی", self.degree),
            ("دانشگاه", self.university),
            ("مهارت ها", ", ".join(self.skills)),
            ("علایق", ", ".join(self.interests)),
        ]

        def format_line(label, value):
            return f"| <b>{label}</b> : {value}"

        header_line = (self.scale + 3) * "─"
        top_border = "╭" + "─" * self.scale + "╮"
        bottom_border = "╰" + "─" * self.scale + "╯"

        body = "\n".join(format_line(label, val) for label, val in sections)
        return f"{header_line}\n{top_border}\n{body}\n{bottom_border}"

    def get_creds(self):
        return {k: self.__dict__[k] for k in h if CREDS_FA in self.__dict__}

    def adjust_scale(self, p):
        if p:
            self.scale += 2
        else:
            self.scale -= 2

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def has_skill(self, skill: str) -> bool:
        return skill in self.skills


class ProfileManager:

    def __init__(self, profiles_dict: Dict[str, Dict[str, Any]]):
        self.profiles_dict = profiles_dict
        self._path = RES.DATABASE_PATH
        self.profiles: Dict[str, Profile] = {
            uid: Profile(**data) for uid, data in profiles_dict.items()
        }

    def get(self, user_id: str | int) -> Optional[Profile]:
        if isinstance(user_id, int):
            user_id = str(user_id)
        return self.profiles.get(user_id)

    def credentials_exist(self, creds: Dict[str, Any]) -> bool:
        def match_score(profile: Profile) -> float:
            score = 0.0
            for attr, weight in self.WEIGHTS.items():
                a = str(creds[attr]).lower().strip()
                b = str(getattr(profile, attr)).lower().strip()
                if a == b:
                    score += weight
                    if score >= 1.0:
                        break
            return score

        return any(match_score(p) >= 1.0 for p in self.profiles.values())

    @staticmethod
    def _normalize_list_field(value: Any, field_name: str) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        raise TypeError(f"Field '{field_name}' must be a list or comma-separated string")

    def check_credentials(self, creds: Dict[str, Any]):
        if self.credentials_exist(creds):
            raise ValueError("Profile already exists")

        # normalize both list fields in one pass
        creds["skills"] = self._normalize_list_field(creds.get("skills"), "skills")
        creds["interests"] = self._normalize_list_field(creds.get("interests"), "interests")

        # generic type validation
        for field_name, expected in self.REQUIRED_FIELDS.items():
            expected = type(expected)
            val = creds.get(field_name)
            if not isinstance(val, expected):
                raise TypeError(f"Field '{field_name}' must be {expected.__name__}, got {type(val).__name__}")

    def add_profile(self, user_id: int, creds: Dict[str, Any] | Profile) -> bool:
        try:
            if isinstance(creds, dict):
                self.check_credentials(creds)
                self.profiles[str(user_id)] = Profile(user_id=user_id, **creds)
            elif isinstance(creds, Profile):
                self.profiles[str(user_id)] = creds
            return True
        except Exception as e:
            print(e)
            return False

    def delete_profile(self, user_id: int) -> bool:
        return bool(self.profiles.pop(str(user_id), None))

    async def save(self, user_id: str | int) -> None:
        if isinstance(user_id, int):
            user_id = str(user_id)
        profile = self.get(user_id)
        data = asdict(profile)
        await async_json_key_update(RES.DATABASE_PATH, user_id, data)

    def export(self):
        data = self.profiles_dict
        flat_data = []
        for _, user_info in data.items():
            record = user_info.copy()
            # Convert lists to comma-separated strings
            record["skills"] = ", ".join(record.get("skills", []))
            record["interests"] = ", ".join(record.get("interests", []))
            flat_data.append(record)

        df = pd.DataFrame(flat_data)
        df = df.reindex(columns=RES.CREDS_FA.keys())
        df.to_excel(RES.EXPORT_PATH, index=False, engine='openpyxl')

    def user_ids_self_reserve(self):
        return [
            user_id for user_id, data in self.profiles_dict.items()
            if data.get("is_verified") and data.get("self_reserve") is True
        ]

    def user_ids(self):
        return [
            user_id for user_id, data in self.profiles_dict.items()
            if data.get("is_verified")
        ]


class Handlers:

    def __init__(self, profiles):
        self.profile_manager: ProfileManager = profiles
        self.user_map = {}

    def register(self, app: _application.Application) -> None:
        labels = RES.LABELS
        show_temps_pattern = re.compile(f"^({'|'.join(map(re.escape, RES.TEMPS.keys()))})$")
        conv = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                States.MAIN_MENU_STUDENT: [
                    MessageHandler(filters.Regex(f"^{labels['12']}$"), self.show_profile),
                    CallbackQueryHandler(self.on_edit_profile, pattern=f"^{labels['4']}$"),
                    MessageHandler(filters.Regex(f"^{labels['13']}$"), self.show_settings),
                    MessageHandler(filters.Regex(f"^{labels['21']}$"), self.edit_profile),
                    MessageHandler(filters.Regex(f"^{labels['25']}$"), self.content_creation),
                    MessageHandler(filters.Regex(f"^{labels['2']}$"), self.back_to_main),
                    MessageHandler(filters.Regex(f"^{labels['30']}$"), self.about),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_message)
                ],
                States.MAIN_MENU_ADMIN: [
                    MessageHandler(filters.Regex(f"^{labels['12']}$"), self.show_profile),
                    CallbackQueryHandler(self.on_edit_profile, pattern=f"^{labels['4']}$"),
                    MessageHandler(filters.Regex(f"^{labels['13']}$"), self.show_settings),
                    MessageHandler(filters.Regex(f"^{labels['25']}$"), self.content_creation),
                    MessageHandler(filters.Regex(f"^{labels['24']}$"), self.export_profiles),
                    MessageHandler(filters.Regex(f"^{labels['2']}$"), self.back_to_main),
                    MessageHandler(filters.Regex(f"^{labels['30']}$"), self.about),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_message)
                ],
                States.TEMPLATES: [
                    MessageHandler(filters.Regex(f"^{labels['2']}$"), self.back_to_main),
                    MessageHandler(filters.Regex(f"^{labels['26']}$"), self.content_temps),
                    MessageHandler(filters.Regex(show_temps_pattern), self.show_temps),
                    CallbackQueryHandler(self.on_edit_temp, show_temps_pattern),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.edit_temp)
                ],
                States.SIGN_UP_STEPS: [
                    CallbackQueryHandler(self.on_signup, pattern=f"^{labels['1']}$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.sign_up_input),
                    CallbackQueryHandler(self.sign_up_cancel, pattern="^cancel_signup$"),
                    CallbackQueryHandler(self.sign_up_button_input, pattern="^signup_info:"),
                    CallbackQueryHandler(self.next_signup, pattern="^next_signup$")
                ],
                States.SETTINGS: [
                    MessageHandler(filters.Regex(f"^{labels['14']}$"), self.set_scale),
                    MessageHandler(filters.Regex(f"^{labels['2']}$"), self.back_to_main),
                    MessageHandler(filters.Regex(f"^{labels['28']}|{labels['29']}$"), self.toggle_reserve)
                ],
                States.EDIT_PROFILE: [
                    MessageHandler(filters.Regex(f"^{labels['22']}|{labels['23']}$"), self.show_options),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_option)
                ],
                States.SCALE: [
                    MessageHandler(filters.Regex(
                        f"^({re.escape(labels['15'])}"
                        f"|{re.escape(labels['16'])})$"),
                        self.change_scale),
                    MessageHandler(filters.Regex(f"^{labels['2']}$"), self.back_to_main)
                    ,
                ],
            },
            fallbacks=[CommandHandler("start", self.start)],
            per_message=False
        )

        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(self.on_y_link, pattern="^y_link:"))
        app.add_handler(CallbackQueryHandler(self.on_y_signup, pattern="^y_verify:"))
        app.add_handler(CallbackQueryHandler(self.on_no, pattern="^no$"))
        self.weekly_job(app)

    async def send_updated_msg(self, app):
        for usr_id in self.profile_manager.user_ids():
            try:
                await app.bot.send_message(chat_id=usr_id,
                                           text=(
                                               "ربات آپدیت شد، برای استفاده دوباره استارت بزنید:"
                                               "/start"))
            except error.BadRequest:
                print(f"chat {usr_id} not found to send updated message")

    # ─── HELPERS ──────────────────────────────────────────────────────────────────
    def recognize_user(self, user_id: int, user_data):

        user_data['profile'] = self.profile_manager.get(user_id)
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

    @staticmethod
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

    @staticmethod
    def _list_to_dict(keys, values, placeholder="⬜⬜⬜"):
        return {
            key: values[i] if i < len(values) else placeholder
            for i, key in enumerate(keys)
        }

    async def _render_signup_step(self, chat_id: int, msg_id: int, context):
        profile = context.user_data['profile']
        step = context.user_data['sign_up_step']
        c_field = RES.STEP_FIELDS[step]
        is_multi = c_field in RES.MULTI_FIELDS
        is_chosable = c_field in RES.CHOOSE_FIELDS
        fa_name = RES.CREDS_FA[c_field]

        # get dict for outline_creds
        creds_dict = self._list_to_dict(RES.STEP_FIELDS, [
            profile.__dict__.get(k, "⬜⬜⬜") for k in RES.STEP_FIELDS
        ])
        outline = self._outline_creds(creds_dict)

        # pick keyboard
        base_menu = f"signup_step:{step}"
        if is_multi:
            footnote = (
                "• میتونی هر چندتا که میخوای انتخاب کنی\n"
                "• وقتی تموم شد دکمه 'مرحله بعد' رو بزن"
            )
            keyboard = self.make_menu_inline(f"{base_menu}, next_signup, cancel_signup")
            action = "انتخاب یا تایپ کن"
        else:
            footnote = ""
            keyboard = self.make_menu_inline(f"{base_menu}, cancel_signup")
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

    def weekly_job(self, app):
        job_queue = app.job_queue
        notification_time = dt_time(hour=RES.NOTIF_TIME, minute=0, tzinfo=ZoneInfo("Asia/Tehran"))
        job_queue.run_daily(
            callback=self.weekly_notification,
            time=notification_time,
            days=(3,),
            name="weekly_notification",
        )

    # ─── BACKGROUND_TASKS ─────────────────────────────────────────────────────────
    async def weekly_notification(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_ids = self.profile_manager.user_ids_self_reserve()
        for uid in user_ids:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "📢 چهارشنبه شما بخیر باشه؛ یادآوری می‌کنم غذای سلف هفته رو رزرو کنی\n\n "
                    '<a href="https://self.umz.ac.ir/">اینجا کلیک کن</a> *ـ^'
                ),
                parse_mode="HTML"
            )

    # ─── MENUS ────────────────────────────────────────────────────────────────────
    def _button(self, label, callback_data):
        return InlineKeyboardButton(RES.LABELS[label], callback_data=callback_data)

    def _buttons(self, labels_name, base_tag: str) -> list[list[InlineKeyboardButton]]:
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

    def make_menu_inline(self, menu_types, user_id=None, temp_name=''):
        menu_map = {
            'admin':
                [

                ],
            'unregistered':
                [
                    [self._button('1', RES.LABELS['1'])]
                ],
            'sent_link':
                [
                    [self._button('10', f'y_link:{user_id}')],
                    [self._button('11', f'no')]
                ],
            'user_verify':
                [
                    [self._button('10', f'y_verify:{user_id}')],
                    [self._button('11', 'no')]
                ],
            'cancel_signup':
                [
                    [self._button('3', 'cancel_signup')]
                ],
            'next_signup':
                [
                    [self._button('20', 'next_signup')]
                ],
            'signup_step:2': self._buttons('study_fields', 'signup_info'),
            'signup_step:4': self._buttons('degrees', 'signup_info'),
            'signup_step:5': self._buttons('universities', 'signup_info'),
            'signup_step:8': self._buttons('interests', 'signup_info'),
            'signup_step:9': self._buttons('skills', 'signup_info'),
            'edit_temp':
                [
                    [self._button('27', temp_name)]
                ],
            'edit_profile':
                [
                    [self._button('4', RES.LABELS['4'])]
                ],
            'prof_edit': self._buttons(list(RES.CREDS_FA.values()), 'prof_edit_info')

        }
        buttons = []
        for menu_type in map(str.strip, menu_types.split(',')):
            buttons.extend(menu_map.get(menu_type, []))
        return InlineKeyboardMarkup(buttons)

    def _reply_button(self, label):
        return KeyboardButton(RES.LABELS[label])

    def _reply_buttons(self, buttons_n):
        if isinstance(buttons_n, str):
            buttons_label = RES.LABELS[buttons_n]
        else:
            buttons_label = buttons_n
        buttons = []
        for label in buttons_label:
            buttons.append([KeyboardButton(label)])
        return buttons

    def make_menu_keyboard(self, menu_type, user_id=None):
        if user_id:
            reserve = self.profile_manager.get(user_id).self_reserve
            reserve_button_name = '29' if reserve else '28'
        else:
            reserve_button_name = '1'

        temps = self._reply_buttons(list(RES.TEMPS.keys()))
        temps.append([self._reply_button('2')])
        menu_map = {
            'student':
                [
                    [self._reply_button('12'), self._reply_button('25')],
                    [self._reply_button('13'), self._reply_button('30')]
                ],
            'admin':
                [
                    [self._reply_button('12'), self._reply_button('25')],
                    [self._reply_button('24'), self._reply_button('13'), self._reply_button('30')]
                ],
            'settings':
                [
                    [self._reply_button('14'), self._reply_button(reserve_button_name)],
                    [self._reply_button('2')]
                ],
            'scale':
                [
                    [self._reply_button('15')],
                    [self._reply_button('16')],
                    [self._reply_button('2')]
                ],
            'p_edit_options':
                [
                    [self._reply_button('22')],
                    [self._reply_button('23')]
                ],
            'content_creation':
                [
                    [self._reply_button('26')],
                    [self._reply_button('2')]
                ],
            'skills': self._reply_buttons('skills'),
            'interests': self._reply_buttons('interests'),
            'temps': temps
        }

        buttons = menu_map.get(menu_type)
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

    # ─── COMMANDS ─────────────────────────────────────────────────────────────────
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_data = context.user_data
        chat_id = update.effective_chat.id
        self.recognize_user(chat_id, user_data)
        user_data['started'] = True
        p = user_data.get('profile')
        first_name = getattr(p, 'first_name', '')
        last_name = getattr(p, 'last_name', '')
        self.user_map = {
            'admin': {
                'text': "ادمین عزیز خوش اومدی",
                'markup': self.make_menu_keyboard("admin"),
                'return_obj': States.MAIN_MENU_ADMIN
            },
            'student': {
                'text': f"دانشجوی عزیز {first_name} {last_name} خوش آمدید",
                'markup': self.make_menu_keyboard("student"),
                'return_obj': States.MAIN_MENU_STUDENT
            },
            'unverified': {
                'text': "ادمین سرش شلوغه هنوز ثبت نامتو تایید نکرده!!",
                'markup': None,
                'return_obj': None
            },
            'unregistered': {
                'text': "دوست گرامی شما هنوز عضو نشده‌‌ای!",
                'markup': self.make_menu_inline("unregistered"),
                'return_obj': States.SIGN_UP_STEPS
            },
        }
        user_type = user_data.get('user_type', 'unregistered')
        cfg = self.user_map.get(user_type)
        next_menu = cfg['return_obj']
        await context.bot.send_message(chat_id=chat_id,
                                       text=cfg['text'],
                                       reply_markup=cfg['markup'])
        return next_menu

    # ─── CALLBACKS ────────────────────────────────────────────────────────────────
    async def on_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_type = context.user_data.get('user_type')
        if user_type == 'unregistered':
            # make an “empty” Profile for this user
            user_id = update.effective_user.id
            profile = Profile(
                first_name="", last_name="", user_id=user_id,
                study_field="", student_id=0, email="",
                phone_number=0, degree="", university=""
            )

            context.user_data['profile'] = profile
            context.user_data['sign_up_step'] = 0
            context.user_data['signup_msg_id'] = query.message.message_id

            prompt = RES.CREDS_FA[RES.STEP_FIELDS[0]]
            keyboard = self.make_menu_inline('cancel_signup')
            msg = await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=query.message.message_id,
                text=f"\n سلااام! لطفاً <b>{prompt}</b> خودت رو وارد کن",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return States.SIGN_UP_STEPS

        else:
            return

    async def sign_up_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            reply_markup=self.make_menu_inline("unregistered")
        )
        return States.MAIN_MENU_STUDENT

    async def sign_up_button_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await self._render_signup_step(user_id, signup_msg_id, context)

    async def next_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        # just bump step
        context.user_data['sign_up_step'] += 1
        if context.user_data['sign_up_step'] >= 10:
            await self.sign_up_end(update, context)
            return ConversationHandler.END
        else:
            await self._render_signup_step(query.message.chat_id, query.message.message_id, context)
            return States.SIGN_UP_STEPS

    async def sign_up_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data = context.user_data
        profile = user_data['profile']
        self.profile_manager.add_profile(user_id, profile)
        await self.profile_manager.save(user_id)
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=user_data['signup_msg_id'],
            text=(
                "تبریک میگم اطلاعات شما با موفقیت ثبت شد. منتظر تایید ادمین باش ^_*"
            )
        )
        admin_scale = self.profile_manager.get(Config.ADMIN_ID).scale
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
            reply_markup=self.make_menu_inline("user_verify", user_id=user_id)
        )
        profile.scale = 38
        return

    async def on_y_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, link: str = None) -> None:

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

    async def on_y_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        _, chat_id = query.data.split(':')
        profile = self.profile_manager.get(chat_id)
        profile.is_verified = True
        await self.profile_manager.save(chat_id)
        await self.about(update, context, user_id=chat_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "لطفا برای مشاهده منو دوباره ربات رو استارت بزن: /start"
            )
        )
        return

    async def on_no(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        return

    async def on_edit_temp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def on_edit_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_type = context.user_data.get('user_type')
        if user_type == 'admin' or user_type == 'student':
            # make an “empty” Profile for this user
            user_id = update.effective_user.id
            profile = self.profile_manager.get(user_id)
            msg_id = query.message.message_id
            context.user_data['profile'] = profile
            context.user_data['signup_msg_id'] = msg_id

            await context.bot.edit_message_reply_markup(
                message_id=msg_id,
                chat_id=user_id,
                reply_markup=self.make_menu_inline('prof_edit')
            )
            return

    # ─── MESSAGE HANDLERS ─────────────────────────────────────────────────────────
    async def unknown_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        msg = update.message
        user_data = context.user_data
        pass

    async def handle_signup(self, user_id, msg, context: ContextTypes.DEFAULT_TYPE) -> None:
        creds = find_creds(msg.text, CREDS_FA)
        success = self.profile_manager.add_profile(user_id, creds)
        await self.profile_manager.save(user_id)
        if success:
            await context.bot.send_message(
                chat_id=user_id,
                text=
                (
                    "خب! اطلاعات شما ثبت شد؛ منتظر تایید ادمین باش!"
                )

            )

            text = self._outline_creds(self.profile_manager.get(user_id))
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=

                (
                        f"ادمین عزیز یک نفر جدید به جمع ما پیوسته آیا تاییدش می‌کنی؟"
                        "\n"
                        "\n"
                        "\n<b>اطلاعات فرد:</b>"
                        +
                        text
                ),
                parse_mode="HTML",
                reply_markup=self.make_menu_inline("user_verify", user_id=user_id)
            )

            return

    @staticmethod
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

    async def sign_up_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message

        user_data = context.user_data
        user_id = update.effective_user.id
        signup_msg_id = user_data.get('signup_msg_id')
        profile = user_data['profile']
        step = user_data['sign_up_step']
        c_field = RES.STEP_FIELDS[step]
        is_multi = c_field in RES.MULTI_FIELDS

        # save the text
        value = msg.text.strip()
        if is_multi:
            list_attr = getattr(profile, c_field)
            if value not in list_attr:
                list_attr.append(value)
        else:
            # cast ints if needed
            if c_field in ('student_id', 'phone_number'):
                value = int(value)
            setattr(profile, c_field, value)
            user_data['sign_up_step'] += 1

        await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)

        # render next
        await self._render_signup_step(user_id, signup_msg_id, context)

    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        keyboard = self.make_menu_inline('edit_profile')  # not implemented yet
        text = (
            "<b>پروفایل من</b>\n"
            f"{self.profile_manager.get(user_id)}"
        )
        await self._del_res(user_id, msg, text, context, reply_markup=None)
        return States.MAIN_MENU_STUDENT

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        msg = update.message
        sent = await self._del_res(user_id,
                                   msg,
                                   RES.LABELS['13'],
                                   context,
                                   reply_markup=self.make_menu_keyboard("settings", user_id=user_id))
        context.user_data['settings'] = sent.message_id
        return States.SETTINGS

    async def set_scale(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        await self._del_res(user_id,
                            msg,
                            RES.LABELS['14'],
                            context,
                            reply_markup=self.make_menu_keyboard("scale"))
        return States.SCALE

    async def change_scale(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = context.user_data
        user_id = update.effective_user.id
        msg = update.message
        scale_msg = user_data.get('scale_msg')
        if scale_msg:
            scale_msg_id = scale_msg.id
            await context.bot.delete_message(chat_id=user_id, message_id=scale_msg_id)

        profile = self.profile_manager.get(user_id)
        if msg.text.strip() == RES.LABELS['15']:
            profile.adjust_scale(True)
        elif msg.text.strip() == RES.LABELS['16']:
            profile.adjust_scale(False)
        await self.profile_manager.save(user_id)
        sent = await self._del_res(user_id, msg, str(profile), context)
        user_data['scale_msg'] = sent
        return States.SCALE

    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        return await self.start(update, context)

    async def edit_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        await self._del_res(user_id,
                            msg,
                            RES.LABELS['21'],
                            context,
                            reply_markup=self.make_menu_keyboard("p_edit_options"))
        return States.EDIT_PROFILE

    async def show_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        profile = self.profile_manager.get(user_id)
        if msg.text == RES.LABELS['22']:
            await self._del_res(user_id,
                                msg,
                                RES.LABELS['22'],
                                context,
                                reply_markup=self.make_menu_keyboard("skills"))
            sent = await context.bot.send_message(chat_id=user_id, text=profile.skills, )
        elif msg.text == RES.LABELS['23']:
            await self._del_res(user_id,
                                msg,
                                RES.LABELS['23'],
                                context,
                                reply_markup=self.make_menu_keyboard("interests"))
        return States.EDIT_PROFILE

    async def save_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message

    async def export_profiles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.profile_manager.export()
        await context.bot.send_document(chat_id=Config.ADMIN_ID,
                                        document=RES.EXPORT_PATH
                                        )

    async def content_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message

        await self._del_res(user_id,
                            msg,
                            RES.LABELS['25'],
                            context,
                            reply_markup=self.make_menu_keyboard('content_creation')
                            )
        return States.TEMPLATES

    async def content_temps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        await self._del_res(user_id,
                            msg,
                            RES.LABELS['26'],
                            context,
                            reply_markup=self.make_menu_keyboard('temps')
                            )
        return States.TEMPLATES

    async def show_temps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message

        if user_id == Config.ADMIN_ID:
            keyboard = self.make_menu_inline('edit_temp', temp_name=msg.text)
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

    async def edit_temp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            reply_markup=self.make_menu_inline('edit_temp', temp_name=temp_name)
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=temp_name + " با موفقیت تغییر یافت! "
        )
        return

    async def toggle_reserve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        msg = update.message
        profile = self.profile_manager.get(user_id)
        new_state = not profile.self_reserve
        profile.self_reserve = new_state
        text = 'یاداور روشن شد' if new_state else 'یاداور خاموش شد'
        await self.profile_manager.save(user_id)
        await self._del_res(
            user_id,
            msg,
            text,
            context,
            reply_markup=self.make_menu_keyboard('settings', user_id=user_id)
        )

    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
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
