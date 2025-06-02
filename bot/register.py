import re
from telegram.ext import _application
from telegram import (
    Update,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)
from bot.construct import (
    States,
    RES
)
from .handlers import *


def register(app: _application.Application) -> None:
    labels = RES.LABELS
    main_filter = filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{re.escape(labels['2'])}$")
    combined_keys = list(RES.TEMPS.keys()) + list(RES.TIPS.keys())
    send_content_pattern = re.compile(f"^({'|'.join(map(re.escape, combined_keys))})$")
    show_creds_options_pattern = f"^({re.escape(labels['2'])}|cred_edit_info:.+)$"


    content_creation_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{labels['25']}$"), on_content_creation)],
        states={
            States.CONTENT_OPTIONS: [
                MessageHandler(filters.Regex(f"^{labels['32']}|{labels['26']}$"), on_content_option),
            ],
            States.OPTION_LIST: [

                MessageHandler(filters.Regex(send_content_pattern), send_content),
                CallbackQueryHandler(on_edit_content, pattern=f"{labels['27']}"),

            ],
            States.EDIT_OPTION: [
                CallbackQueryHandler(editing_cancel, pattern=f"{labels['3']}"),
                MessageHandler(main_filter, edit_content)
            ]

        },
        fallbacks=[MessageHandler(filters.Regex(labels['2']), go_back_content)],
        map_to_parent={
            States.ADMIN: States.ADMIN,
            States.STUDENT: States.STUDENT,
            States.UNREGISTERED: States.UNREGISTERED
        }
    )
    settings_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(labels['13']), show_settings)],
        states={
            States.SETTINGS: [
                MessageHandler(filters.Regex(f"^{labels['14']}$"), set_scale),
                MessageHandler(filters.Regex(f"^{labels['28']}|{labels['29']}$"), toggle_reserve)
            ],
            States.SCALE: [
                MessageHandler(filters.Regex(f"^{labels['15']}|{labels['16']}$"), change_scale)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex(labels['2']), go_back_setting)],
        map_to_parent={
            States.ADMIN: States.ADMIN,
            States.STUDENT: States.STUDENT,
            States.UNREGISTERED: States.UNREGISTERED
        }
    )
    signup_or_profile_edit_conv = ConversationHandler(
                        entry_points=[
                            CallbackQueryHandler(on_edit_profile, pattern=f"^{labels['21']}|{labels['1']}$")
                        ],
                        states={
                            States.CHOSEN_CRED: [
                                CallbackQueryHandler(on_cred_edit, pattern="^edit_profile_info:"),
                                CallbackQueryHandler(back_to_profile, pattern=f"^{labels['4']}$")
                            ],
                            States.GET_INFO: [
                                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_get_info_typed),
                                CallbackQueryHandler(edit_profile_get_info_button, pattern=show_creds_options_pattern),
                                # CallbackQueryHandler(back_to_menu, pattern=f"^{labels['4']}$")
                            ],
                            States.FINALIZE: [
                                CallbackQueryHandler(end_signup, pattern=labels['31'])
                            ]

                        },
                        fallbacks=[],
                        map_to_parent={
                            States.ADMIN: States.ADMIN,
                            States.STUDENT: States.STUDENT,
                            States.UNREGISTERED: States.UNREGISTERED
                        })
    common_hs = [
        MessageHandler(filters.Regex(f"^{labels['12']}$"), show_profile),
        MessageHandler(filters.Regex(f"^{labels['30']}$"), about),
        content_creation_conv,
        settings_conv,
        signup_or_profile_edit_conv
    ]
    main_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            States.ADMIN: common_hs + [
                MessageHandler(filters.Regex(f"^{labels['24']}$"), export_profiles)
            ],
            States.STUDENT: common_hs + [],
            States.UNREGISTERED: [signup_or_profile_edit_conv],

        },
        fallbacks=[
        ]
    )
    app.add_handler(main_conv)
    weekly_job(app)



























