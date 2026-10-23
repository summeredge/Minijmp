import json
from pathlib import Path
import sys
import webbrowser

HELP_JSON = Path(__file__).resolve().with_name('help.json')
DEFAULT_LINK = 'https://minijmp.readthedocs.io/'
HELP_DIR = (Path(sys._MEIPASS) / 'help' if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parent.parent / 'help')


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


def open_help(topic_id=None, parent=None):
    """Open the offline help center or a topic selected by stable ID."""
    from tkinter import messagebox

    try:
        index_path = HELP_DIR / 'index.html'
        target_id = None
        if topic_id is not None:
            topics = json.loads((HELP_DIR / 'help-map.json').read_text(encoding='utf-8'))['topics']
            topic = next((item for item in topics
                          if item['id'] == topic_id
                          or topic_id in item.get('dialog_classes', [])), None)
            if topic is None:
                raise KeyError(topic_id)
            target_id = topic['id']
            page = (HELP_DIR / topic['page'].split('#', 1)[0]).resolve()
            try:
                page.relative_to(HELP_DIR.resolve())
            except ValueError as error:
                raise ValueError('帮助目标路径无效。') from error
            if not page.is_file():
                raise FileNotFoundError(page)
        if not index_path.is_file():
            raise FileNotFoundError(index_path)
        url = index_path.resolve().as_uri()
        if target_id:
            url += '#' + target_id
        if not webbrowser.open(url, new=2, autoraise=True):
            raise OSError('默认浏览器未能打开帮助页面。')
    except Exception as error:
        messagebox.showerror('帮助文档', f'无法打开离线帮助：{error}', parent=parent)
        return False
    return True


if __name__ == "__main__":
    print(help_link("Main Help Menu"))
    print(help_link("something"))
    print(help_window("Stats Summary Multi Datasets"))
