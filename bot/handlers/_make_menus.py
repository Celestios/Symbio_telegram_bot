from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from typing import (Union, List, Optional)
from ..construct import RES
from ._utils import (
    encode_label,
    # decode_label
)


def make_menu_keyboard(menu_type, reserve=False):

    reserve_button_name = '29' if reserve else '28'

    temps = _reply_buttons(list(RES.TEMPS.keys()))
    tips = _reply_buttons(list(RES.TIPS.keys()))
    temps.append([_reply_button('2')])
    tips.append([_reply_button('2')])
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
                [_reply_button('26'), _reply_button('32')],
                [_reply_button('2')]

            ],
        'skills': _reply_buttons('skills'),
        'interests': _reply_buttons('interests'),
        'temps': temps,
        'tips': tips
    }

    buttons = menu_map.get(menu_type)
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)


def make_menu_inline(menu_types, user_id=None):
    if isinstance(menu_types, str):
        menu_types = [menu_types]
    labels = RES.LABELS
    menu_map = {
        'admin':
            [

            ],
        'unregistered':
            [
                [_button('1', labels['1'])]
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
        'study_field': _buttons('study_fields', 'cred_edit_info'),
        'degree': _buttons('degrees', 'cred_edit_info'),
        'university': _buttons('universities', 'cred_edit_info'),
        'interests': _buttons('interests', 'cred_edit_info'),
        'skills': _buttons('skills', 'cred_edit_info'),
        'back':
            [
                [_button('2', RES.LABELS['2'])]
            ],
        'edit_content':
            [
                [_button('27', labels['27'])]
            ],
        'edit_profile':
            [
                [_button('21', labels['21'])]
            ],
        'creds_edit_options': _buttons(
            list(RES.CREDS_FA.values()),
            'edit_profile_info',
            columns=3,
            custom_callback_data=list(RES.CREDS_FA.keys())
        ),
        'signup_general_options': _buttons(
            [labels['31'], labels['3']],
            base_tag='',
            columns=2,
            custom_callback_data=[labels['31'], labels['3']]
        ),
        'profile_edit_general_options':
            [
                [_button('2', labels['2'])]
            ]
    }
    buttons = []
    for menu_type in menu_types:
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


def _buttons(
        labels_name: Union[str, List[str]],
        base_tag: str = '',
        columns: int = 1,
        custom_callback_data: Optional[List[str]] = None
) -> List[List[InlineKeyboardButton]]:
    labels = RES.LABELS[labels_name] if isinstance(labels_name, str) else labels_name
    buttons, row = [], []

    for i, label in enumerate(labels):
        # Determine callback data
        if custom_callback_data and i < len(custom_callback_data):
            cb_value = custom_callback_data[i]
        else:
            raw_cb = f"{base_tag}:{label}"
            cb_value = encode_label(label, RES.LABEL_CALLBACK_MAP) if len(raw_cb.encode('utf-8')) > 63 else label
        if base_tag:
            callback_data = f"{base_tag}:{cb_value}"
        else:
            callback_data = cb_value
        row.append(InlineKeyboardButton(label, callback_data=callback_data))

        if 0 < columns == len(row):
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return buttons


def _button(label, callback_data):
    return InlineKeyboardButton(RES.LABELS[label], callback_data=callback_data)


def get_user_markup(role):
    markups = {
        'admin': make_menu_keyboard("admin"),
        'student': make_menu_keyboard("student"),
        'incomplete_profile': make_menu_inline("unregistered"),
        'unregistered': make_menu_inline("unregistered"),
    }
    return markups.get(role)

