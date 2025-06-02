from telegram.ext import (
    ContextTypes
)
from telegram import (
    # Update,
    MessageEntity,
    # Message,
    # Bot
)
from ..profiles import Profile
from ..construct import (
    Config,
    States,
    RES
)


def recognize_user(user_id: int, user_data, profile):
    if user_id == Config.ADMIN_ID:
        user_data['user_type'] = 'admin'
    elif profile:
        if profile.is_signed_up:
            if profile.is_verified:
                user_data['user_type'] = 'student'
            else:
                user_data['user_type'] = 'unverified'
        else:
            user_data['user_type'] = 'incomplete_profile'
    else:
        user_data['user_type'] = 'unregistered'

    return user_data['user_type']


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


def get_user_text(role, first_name=None, last_name=None):
    texts = {
        'admin': "ادمین عزیز خوش اومدی",
        'student': f"دانشجوی عزیز {first_name} {last_name} خوش آمدید",
        'unverified': "ادمین سرش شلوغه هنوز ثبت نامتو تایید نکرده!!",
        'incomplete_profile': "مشخصات شما کامل نیست لطفا از طریق دکمه ثبت نام پروفایل خودت رو کامل کن",
        'unregistered': "دوست گرامی شما هنوز عضو نشده‌‌ای!"
    }
    return texts.get(role, "خطا: نقش نامعتبر است")


def get_user_state(role):
    states = {
        'admin': States.ADMIN,
        'student': States.STUDENT,
        'incomplete_profile': States.UNREGISTERED,
        'unregistered': States.UNREGISTERED,
    }
    return states.get(role)


def push_menu(context: ContextTypes.DEFAULT_TYPE, state):
    stack = context.user_data.setdefault('menu_stack', [])
    if not stack or stack[-1] != state:
        stack.append(state)
    return state


def pop_menu(context: ContextTypes.DEFAULT_TYPE):
    stack = context.user_data.get('menu_stack', [])
    if len(stack) > 1:
        stack.pop()
    return stack[-1] if stack else None


def encode_label(label: str, label_map) -> str:
    if label in label_map:
        return label_map[label]
    next_id = len(label_map)
    encoded = f"__enc_{next_id}"
    label_map[label] = encoded
    return encoded


def decode_label(label: str, label_map) -> str:
    if not label.startswith("__enc_"):
        return label
    for label_n, code in label_map.items():
        if code == label:
            return label_n
    raise ValueError(f"Unknown encoded callback data: {encoded}")


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

    if isinstance(creds, Profile):
        creds = creds.get_creds()

    lines = []
    for key, fa_key in RES.CREDS_FA.items():
        value = creds.get(key)
        if is_blank(value):
            value = "⬜⬜⬜"
        elif isinstance(value, list):
            value = ', '.join(map(str, value))
        lines.append(f"\n<b>{fa_key}</b> : {value}")
    return ''.join(lines)
