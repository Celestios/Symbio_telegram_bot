import logging
import re
from openpyxl.worksheet.filters import Filters
from telegram.ext import _application
from .utility import log_calls, json_key_update, find_creds, find_link, async_json_key_update
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ApplicationBuilder,
    CallbackContext,
    filters
)
from .config import Config
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any


from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from itertools import islice

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
    _scale: int = 38

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

        header_line = (self._scale + 3) * "─"
        top_border = "╭" + "─" * self._scale + "╮"
        bottom_border = "╰" + "─" * self._scale + "╯"

        body = "\n".join(format_line(label, val) for label, val in sections)
        return f"{header_line}\n{top_border}\n{body}\n{bottom_border}"

    def adjust_scale(self, p):
        if p:
            self._scale += 1
        else:
            self._scale -= 1

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def has_skill(self, skill: str) -> bool:
        return skill in self.skills


class ProfileManager:
    WEIGHTS = json_key_update(Config.resources, 'uniqueness_weights')
    REQUIRED_FIELDS = json_key_update(Config.resources, 'required_fields_check')

    def __init__(self, profiles_dict: Dict[str, Dict[str, Any]]):
        self._path = Config.database
        self.profiles: Dict[str, Profile] = {
            uid: Profile(**data) for uid, data in profiles_dict.items()
        }

    def get(self, user_id: str) -> Optional[Profile]:
        return self.profiles.get(str(user_id))

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

    def add_profile(self, user_id: int, creds: Dict[str, Any]) -> bool:
        try:
            self.check_credentials(creds)
            self.profiles[str(user_id)] = Profile(user_id=user_id, **creds)
            return True
        except Exception as e:
            print(e)
            return False

    def delete_profile(self, user_id: int) -> bool:
        return bool(self.profiles.pop(str(user_id), None))

    async def save(self, user_id: str) -> None:
        profile = self.get(user_id)
        data = asdict(profile)
        await async_json_key_update(self._path, str(user_id), data)


class Handlers:
    def __init__(self, profiles):
        self.profiles = profiles
        self.button_labels = json_key_update(Config.resources, 'buttons')
        self.creds_fa = json_key_update(Config.resources, 'creds_fa')

    def register(self, app: _application.Application) -> None:
        app.add_handler(CommandHandler('start', self.start))
        app.add_handler(CallbackQueryHandler(self.on_signup, pattern="^signup$"))
        app.add_handler(CallbackQueryHandler(self.on_y_link, pattern="^y_link:"))
        app.add_handler(CallbackQueryHandler(self.on_y_signup, pattern="^y_verify:"))
        app.add_handler(CallbackQueryHandler(self.on_no, pattern="^no$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))

    # ─── HELPERS ──────────────────────────────────────────────────────────────────
    def recognize_user(self, user_id: int, user_data) -> None:

        user_data['profile'] = self.profiles.get(user_id)
        if user_id == Config.ADMIN_ID:
            user_data['user_type'] = 'admin'
        elif user_data['profile']:
            if user_data['profile'].is_verified:
                user_data['user_type'] = 'student'
            else:
                user_data['user_type'] = 'unverified'
        else:
            user_data['user_type'] = 'unregistered'

    # ─── MENUS ────────────────────────────────────────────────────────────────────
    def _button(self, label, callback_data):
        return InlineKeyboardButton(self.button_labels[label], callback_data=callback_data)

    def make_menu_inline(self, menu_type, user_id=None):
        menu_map = {
            'admin':
            [

            ],
            'unregistered':
            [
                [self._button('1', 'signup')]
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
            ]
        }

        buttons = menu_map.get(menu_type)
        return InlineKeyboardMarkup(buttons)

    def _reply_button(self, label):
        return KeyboardButton(self.button_labels[label])

    def make_menu_keyboard(self, menu_type, user_id=None):
        menu_map = {
            'student':
            [
                [self._reply_button('12')],
                [self._reply_button('13')]
            ],
            'settings':
            [
                [self._reply_button('14')]
            ],
            'scale':
            [
                [self._reply_button('15')],
                [self._reply_button('16')]
            ]
        }

        buttons = menu_map.get(menu_type)
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

    # ─── COMMANDS ─────────────────────────────────────────────────────────────────
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_data = context.user_data
        chat_id = update.effective_chat.id
        self.recognize_user(chat_id, user_data)

        if user_data['user_type'] == 'admin':

            await context.bot.send_message(text="ادمین عزیز خوش اومدی",
                                           chat_id=chat_id,
                                           reply_markup=self.make_menu_inline("admin"))
        elif user_data['user_type'] == 'student':

            first_name = user_data.get('profile').first_name
            last_name = user_data.get('profile').last_name
            await context.bot.send_message(
                text=
                (
                    f"دانشجوی عزیز"
                    f" {first_name}"
                    f" {last_name}"
                    f" خوش آمدید"
                ),
                chat_id=chat_id,
                reply_markup=self.make_menu_keyboard("student")
            )
        elif user_data['user_type'] == 'unverified':
            await context.bot.send_message(
                text=
                (
                    "ادمین سرش شلوغه هنوز ثبت نامتو تایید نکرده!!"
                )

            )
        else:

            await context.bot.send_message(
                text=("دوست گرامی شما هنوز عضو نشده‌‌ای!"
                      ),
                chat_id=chat_id,
                reply_markup=self.make_menu_inline("unregistered")
            )

    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pass

    # ─── CALLBACKS ────────────────────────────────────────────────────────────────
    async def on_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['action'] = 'signup'
        query = update.callback_query
        await query.answer()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "دوست خوبم برای ثبت نام، لطفا فرم زیر رو کامل کن و دوباره بفرست\n"
                "ℹ️ با کلیک روی "
                "copy code "
                "به راحتی کپی میشه\n"
                "```\n"
                "نام: \n"
                "نام خانوادگی: \n"
                "رشته: \n"
                "مقطع تحصیلی: \n"
                "محل تحصیل: \n"
                "شماره دانشجویی: \n"
                "شماره تماس: \n"
                "مهارت ها: \n"
                "ایمیل: \n"
                "علایق مطالعاتی: \n"
                "```\n"
                "• لازم نیست همه رو پر کنی\n"
                "• ترتیب مهم نیست\n"
                "• مهارت ها و علایق مختلف رو با  ،  جدا کن\n"
                "• زیاد سخت نگیر بعدا همیشه میتونی پروفایلتو ویرایش کنی"
            ),
            parse_mode="Markdown",
        )

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
        profile = self.profiles.get(chat_id)
        profile.is_verified = True
        return

    async def on_no(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # ─── MESSAGE HANDLERS ─────────────────────────────────────────────────────────
    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_data = context.user_data
        user_id = update.effective_user.id
        msg = update.message

        if not user_data:
            self.recognize_user(user_id, user_data)

        # sing up ------------------------------------------------------------------
        if user_data.get('action') == 'signup':
            creds = find_creds(msg.text, self.creds_fa)
            success = self.profiles.add_profile(user_id, creds)
            await self.profiles.save(user_id)
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=
                    (
                        "خب! اطلاعات شما ثبت شد؛ منتظر تایید ادمین باش!"
                    )

                )
                await context.bot.send_message(
                    chat_id=Config.ADMIN_ID,
                    text=

                    (
                        f"\nادمین عزیز یک نفر جدید به جمع ما پیوسته آیا تاییدش می‌کنی؟"
                        "<b>اطلاعات فرد:</b>"
                        +
                        f"{self.profiles.get(user_id)}"
                    ),
                    parse_mode="HTML",
                    reply_markup=self.make_menu_inline("user_verify", user_id=user_id)
                )

                return
        # sending link -------------------------------------------------------------
        # sent_link = find_link(msg.text)
        # if sent_link:
        #     if user_data.get("user_type") == "student":
        #         profile = user_data.get('profile')
        #         profile.link_queue.append(sent_link)
        #         await context.bot.send_message(
        #             text=(
        #                 f'<a href="tg://user?id={user_id}">{profile.first_name}{profile.last_name}</a>'
        #                 f' لینک خبر فرستاد:'
        #                 f'\n{sent_link}'
        #                 f'تایید؟'
        #             ),
        #             parse_mode="HTML",
        #             reply_markup=self.make_menu_inline("sent_link", user_id)
        #         )
        #         return
        #     elif user_data.get("user_type") == "admin":
        #         await self.on_y_link(update, context, link=sent_link)
        # show profile -------------------------------------------------------------
        elif msg.text == self.button_labels['12']:
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=
                (
                    "<b>پروفایل من</b>\n"
                    f"{self.profiles.get(user_id)}"
                ),
                parse_mode="HTML"
            )
        # settings ----------------------------------------------------------------
        elif msg.text == self.button_labels['13']:
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=".",
                reply_markup=self.make_menu_keyboard("settings")
            )
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        # set scale ---------------------------------------------------------------
        elif msg.text == self.button_labels['14']:
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=".",
                reply_markup=self.make_menu_keyboard("scale")
            )
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        # increase size
        elif msg.text == self.button_labels['15']:
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            profile = self.profiles.get(user_id)
            profile.adjust_scale(True)
            await self.profiles.save(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=
                (
                    str(profile)
                ),
                parse_mode="HTMl"
            )
        # decrease size
        elif msg.text == self.button_labels['16']:
            await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            profile = self.profiles.get(user_id)
            profile.adjust_scale(False)
            await self.profiles.save(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=
                (
                    str(profile)
                ),
                parse_mode="HTML"
            )
