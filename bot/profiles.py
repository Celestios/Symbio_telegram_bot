import pandas as pd
from .utility import async_json_key_update
from .construct import RES
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
import copy


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
    is_signed_up: bool = False
    is_verified: bool = False
    skills: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    scale: int = 38
    self_reserve: bool = True

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

    def is_complete(self) -> bool:
        for field_name, empty_value in required_fields_check.items():
            current_value = getattr(self, field_name)
            if current_value == empty_value:
                return False
        return True


    def get_creds(self):
        return {k: self.__dict__[k] for k in RES.CREDS_FA if k in self.__dict__}

    def adjust_scale(self, p):
        min_scale = 5
        max_scale = 50

        if p:
            self.scale = min(self.scale + 1, max_scale)
        else:
            self.scale = max(self.scale - 1, min_scale)

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

    def add_profile(self,
                    user_id: int,
                    creds: Dict[str, Any] | Profile | None = None,
                    new: bool = False
                    ) -> bool | Profile:
        try:
            if new:
                if creds is not None:
                    raise ValueError("Do not provide credentials when using new=True.")
                empty_creds = RES.REQUIRED_FIELDS.copy()
                empty_creds["user_id"] = user_id
                self.profiles[str(user_id)] = Profile(**empty_creds)
                return self.profiles[str(user_id)]

            if creds is None:
                raise ValueError("Credentials required unless new=True.")

            if isinstance(creds, dict):
                self.check_credentials(creds)
                self.profiles[str(user_id)] = Profile(user_id=user_id, **creds)

            elif isinstance(creds, Profile):
                self.check_credentials(creds.__dict__)
                self.profiles[str(user_id)] = creds

            return self.profiles[str(user_id)]

        except Exception as e:
            print(f"Failed to add profile for user {user_id}: {e}")
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
