from dotenv import load_dotenv
from enum import Enum, auto
import os
from .utility import json_read, async_json_write


load_dotenv()


class Config:
    TOKEN = os.getenv("TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
    GROUP_ID = int(os.getenv("GROUP_ID"))
    G_ID_TA = os.getenv("G_TOPIC_ID_A")
    G_ID_TB = os.getenv("G_TOPIC_ID_B")


class RES:
    DATABASE_PATH = "./data/database.json"
    EXPORT_PATH = "./data/users_data.xlsx"
    DATABASE = json_read(DATABASE_PATH)
    _RESOURCE: dict = json_read("./data/resources.json")
    TEMPS: dict = _RESOURCE.get("temps")
    TIPS: dict = _RESOURCE.get("writing_tips")
    WEIGHTS = _RESOURCE.get("uniqueness_weights")
    REQUIRED_FIELDS = _RESOURCE.get("required_fields_check")
    CREDS_FA = _RESOURCE.get("creds_fa")
    LABELS: dict = _RESOURCE.get("buttons")
    TAGS_MAP: dict = _RESOURCE.get("tags_map")
    NOTIF_TIME_H = 11
    NOTIF_TIME_D = 3
    NOTIF_TIME_M = 0
    LABEL_CALLBACK_MAP = {}
    STEP_FIELDS = list(CREDS_FA.keys())
    MULTI_FIELDS = {"skills", "interests"}
    CHOOSE_FIELDS = {"skills", "interests", "study_field", "degree", "university"}

    @classmethod
    async def update(cls, key, value):
        if key == "temps":
            cls.TEMPS = value
        elif key == "tips":
            cls.TIPS = value

        await async_json_write("./data/resources.json", cls._RESOURCE)


class States(Enum):
    START = auto()
    MAIN_MENU_ADMIN = auto()
    MAIN_MENU_STUDENT = auto()
    SETTINGS = auto()
    SCALE = auto()
    SIGN_UP_STEPS = auto()
    EDIT_PROFILE = auto()
    OPTION_LIST = auto()
    CHOSEN_CRED = auto()
    NEXT_STEP = auto()
    GET_INFO = auto()
    ADMIN = auto()
    STUDENT = auto()
    UNREGISTERED = auto()
    END = auto()
    CONTENT_OPTIONS = auto()
    WRITING_TIPS = auto()
    FINALIZE = auto()
    EDIT_OPTION = auto()