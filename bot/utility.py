import logging
import json
import os
import csv
import re
from functools import wraps
import aiofiles
import asyncio


def log_calls(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        log = logging.getLogger(fn.__name__)
        log.info(f"Entering --> {fn.__name__}")
        result = fn(*args, **kwargs)
        log.info(f"{fn.__name__} --> Exiting")
        return result
    return wrapper


def _convert_value(val):
    """
    - If val is a str containing ',' or '+', split into a list (and recursively convert items).
    - Else if val is a str of digits, convert to int.
    - Otherwise, leave it as-is.
    """
    if isinstance(val, str):
        # Split on commas or pluses
        if ',' in val or '+' in val:
            parts = re.split(r'[,+]', val)
            return [_convert_value(p.strip()) for p in parts if p.strip()]
        # Pure integer?
        if val.isdigit():
            return int(val)
    return val


def json_read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def json_write(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def json_key_update(path, key, value=None):
    data = {}
    if os.path.exists(path):
        data = json_read(path)
    if value is not None:
        data[key] = value
        json_write(path, data)
    else:
        return data[key]


# --- Async Read function ---
async def async_json_read(path):
    async with aiofiles.open(path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return json.loads(content)


# --- Async Write function ---
async def async_json_write(path, data):
    json_data = json.dumps(data, ensure_ascii=False, indent=2)
    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(json_data)


# --- Async key update function ---
async def async_json_key_update(path, key, value=None):
    data = {}
    if os.path.exists(path):
        data = await async_json_read(path)

    if value is not None:
        # Update the key-value pair
        data[key] = value
        await async_json_write(path, data)
    else:
        # Return the value associated with the key
        return data.get(key)  # Safer than directly accessing `data[key]`


def find_creds(text: str, creds_fa) -> dict | None:

    text = re.sub(r'\s*:\s*', ':', text)
    lines = text.strip().splitlines()

    extracted = {}
    reverse_map = {v: k for k, v in creds_fa.items()}

    for line in lines:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key in reverse_map:
            attr = reverse_map[key]
            extracted[attr] = _convert_value(value)

    if not extracted:
        return None
    return extracted


def find_link(text: str) -> str|None:
    p = r"(https?|ftp)://[^\s\"'>]+"
    match = re.search(p, text)
    if match:
        return match.group()
    return None


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


def is_persian_wednesday():
    today = jdatetime.date.today()
    return today.weekday() == 2  # 0 = Saturday, ..., 2 = Wednesday
