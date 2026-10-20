import json
from pathlib import Path

HELP_JSON = Path(__file__).resolve().with_name('help.json')
DEFAULT_LINK = 'https://minijmp.readthedocs.io/'


def help_link(key_str):
    # Read the JSON file
    try:
        with open(HELP_JSON, 'r', encoding='utf-8') as file:
            data = json.load(file)
        #  print(data)
        return data[key_str]["link"]
    except KeyError:
        return DEFAULT_LINK
    except BaseException:
        raise


def help_window(key_str):
    # Read the JSON file
    try:
        with open(HELP_JSON, 'r', encoding='utf-8') as file:
            data = json.load(file)
        #  print(data)
        return data[key_str]["window"]
    except KeyError:
        return ""
    except BaseException:
        raise


if __name__ == "__main__":
    print(help_link("Main Help Menu"))
    print(help_link("something"))
    print(help_window("Stats Summary Multi Datasets"))
