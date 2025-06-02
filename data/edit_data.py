import argparse
import os
import json

EDIT_DATA_PATH = os.path.join("data", "database.json")

def json_read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def json_write(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def smart_parse(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value

def add_key_to_all_profiles(key: str, value):
    data = json_read(EDIT_DATA_PATH)
    for profile in data.values():
        profile[key] = value
    json_write(EDIT_DATA_PATH, data)
    print(f"✅ Key '{key}' with value '{value}' added to all profiles.")

def edit_existing_key(key: str, value):
    data = json_read(EDIT_DATA_PATH)
    updated = 0
    for profile in data.values():
        if key in profile:
            profile[key] = value
            updated += 1
    json_write(EDIT_DATA_PATH, data)
    print(f"✅ Updated '{key}' in {updated} profiles with value '{value}'.")

def rename_key_in_all_profiles(old_key: str, new_key: str):
    data = json_read(EDIT_DATA_PATH)
    renamed = 0
    for profile in data.values():
        if old_key in profile:
            profile[new_key] = profile.pop(old_key)
            renamed += 1
    json_write(EDIT_DATA_PATH, data)
    print(f"🔁 Renamed '{old_key}' to '{new_key}' in {renamed} profiles.")

def delete_key_in_all_profiles(key: str):
    data = json_read(EDIT_DATA_PATH)
    deleted = 0
    for profile in data.values():
        if key in profile:
            profile.pop(key)
            deleted += 1
    json_write(EDIT_DATA_PATH, data)
    print(f"🗑️ Deleted key '{key}' from {deleted} profiles.")

def show_profiles():
    data = json_read(EDIT_DATA_PATH)
    from pprint import pprint
    pprint(data)

def parse_args():
    parser = argparse.ArgumentParser(description="Manage profile data in database.json")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add-key", help="Add a key:value pair to all profiles")
    add_parser.add_argument("key", help="Key to add")
    add_parser.add_argument("value", type=smart_parse, help="Value to assign (supports int, bool, list, etc.)")

    edit_parser = subparsers.add_parser("edit-key", help="Edit a key's value in all profiles (if it exists)")
    edit_parser.add_argument("key", help="Key to edit")
    edit_parser.add_argument("value", type=smart_parse, help="New value")

    rename_parser = subparsers.add_parser("rename-key", help="Rename a key in all profiles")
    rename_parser.add_argument("old_key", help="Old key name")
    rename_parser.add_argument("new_key", help="New key name")

    delete_parser = subparsers.add_parser("delete-key", help="Delete a key from all profiles")
    delete_parser.add_argument("key", help="Key to delete")

    subparsers.add_parser("show", help="Display all profile data")

    return parser.parse_args()

def main():
    args = parse_args()
    if args.command == "add-key":
        add_key_to_all_profiles(args.key, args.value)
    elif args.command == "edit-key":
        edit_existing_key(args.key, args.value)
    elif args.command == "rename-key":
        rename_key_in_all_profiles(args.old_key, args.new_key)
    elif args.command == "delete-key":
        delete_key_in_all_profiles(args.key)
    elif args.command == "show":
        show_profiles()
    else:
        print("❌ Invalid command. Use --help for more information.")

if __name__ == "__main__":
    main()
