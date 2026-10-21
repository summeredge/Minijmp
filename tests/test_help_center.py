import ast
import importlib.util
import json
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import help_link
from tools.build_help_index import build_search_index


ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT / "help"
VERIFIED_MINITAB_URLS = {
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/display-descriptive-statistics/interpret-the-results/key-results/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/normality-test/perform-the-analysis/select-a-test/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-sample-t/interpret-the-results/all-statistics-and-graphs/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-sample-z/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-variance/interpret-the-results/all-statistics/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-proportion/methods-and-formulas/methods-and-formulas/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/2-sample-t/before-you-start/data-considerations/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/2-proportions/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/paired-t/interpret-the-results/key-results/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/basic-statistics/how-to/2-variances/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistics/tables/supporting-topics/chi-square/what-is-a-chi-square-test/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistical-modeling/anova/how-to/one-way-anova/interpret-the-results/key-results/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistical-modeling/anova/supporting-topics/basics/perform-a-two-way-anova/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/statistical-modeling/regression/supporting-topics/basics/regression-analyses-in-minitab/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/graphs/graphs-in-minitab/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/graphs/graph-builder/boxplot/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/graphs/graph-builder/scatterplot/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/graphs/graph-builder/probability-plot/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/graphs/general-graph-options/labels-lines-and-annotations/fitted-distribution-lines/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/crossed-gage-r-r-study/interpret-the-results/key-results/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/nested-gage-r-r-study/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/normal-capability-analysis/methods-and-formulas/potential-capability/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/tolerance-intervals-normal-distribution/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/variables-charts-for-individuals/i-mr-chart/interpret-the-results/all-statistics-and-graphs/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/variables-charts-for-subgroups/xbar-r-chart/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/variables-charts-for-subgroups/xbar-s-chart/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/np-chart/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/p-chart/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/c-chart/before-you-start/overview/",
    "https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/attributes-charts/u-chart/before-you-start/overview/",
}


class PageInfo(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for name in ("href", "src"):
            if name in attrs:
                self.links.append((tag, name, attrs[name], attrs.get("target"), attrs.get("rel", "")))


def help_topics():
    return json.loads((HELP / "help-map.json").read_text(encoding="utf-8"))["topics"]


def test_menu_inventory_and_dialog_ids_match_the_source():
    topics = help_topics()
    app_tree = ast.parse((ROOT / "code" / "MiniJMP.py").read_text(encoding="utf-8"))
    app_class = next(node for node in app_tree.body
                     if isinstance(node, ast.ClassDef) and node.name == "Minijmp")
    methods = {node.name: node for node in app_class.body if isinstance(node, ast.FunctionDef)}
    workbook_tree = ast.parse((ROOT / 'code' / 'worksheets.py').read_text(encoding='utf-8'))
    workbook_class = next(node for node in workbook_tree.body
                          if isinstance(node, ast.ClassDef) and node.name == 'Worksheets')
    methods.update({node.name: node for node in workbook_class.body if isinstance(node, ast.FunctionDef)})
    menu_method = methods["createMenuBar"]
    menu_callbacks = {}
    for node in ast.walk(menu_method):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and key.value[:2].isdigit() and isinstance(value, ast.Dict)):
                command = next((v for k, v in zip(value.keys, value.values)
                                if isinstance(k, ast.Constant) and k.value == "cmd"), None)
                if isinstance(command, ast.Lambda) and isinstance(command.body, ast.Call):
                    command = command.body.func
                if isinstance(command, ast.Attribute) and isinstance(command.value, ast.Name) and command.value.id == "self":
                    menu_callbacks[command.attr] = key.value[2:]
    class_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "code").rglob("*.py")
    )
    seen_classes = set()

    for topic in topics:
        assert topic["status"] == "已实现"
        for source in topic["source"].split(";"):
            source_path = source.strip().split(":", 1)[0]
            assert (ROOT / source_path).is_file(), topic["id"]
        for dialog_class in topic["dialog_classes"]:
            assert dialog_class not in seen_classes
            seen_classes.add(dialog_class)
            assert f"class {dialog_class}(" in class_sources, dialog_class
            callback = topic["entry"].split(".", 1)[1].split("(", 1)[0]
            calls = {
                node.func.id for node in ast.walk(methods[callback])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            assert dialog_class in calls, (topic["id"], callback)
        if topic["menu"] in {"Stats", "Quality", "Plots"} or topic["id"] == "files.pi_import":
            callback = topic["entry"].split(".", 1)[1].split("(", 1)[0]
            assert callback in menu_callbacks, topic["id"]
            assert any("\u4e00" <= char <= "\u9fff" for char in menu_callbacks[callback]), topic["id"]
    assert len(seen_classes - {"PIImportDialog"}) == 48
    assert len(seen_classes) == 49


def test_generated_search_index_matches_every_nonempty_help_section():
    source = build_search_index()
    saved = (HELP / "assets" / "search-index.js").read_text(encoding="utf-8")
    assert source == saved
    prefix = "window.MINIJMP_HELP_INDEX = "
    assert saved.startswith(prefix) and saved.rstrip().endswith(";")
    index = json.loads(saved[len(prefix):].rstrip()[:-1])
    mapped = {topic["id"]: topic for topic in help_topics()}
    assert {item["id"] for item in index} == set(mapped)
    for item in index:
        assert item["page"] == mapped[item["id"]]["page"]
        assert item["text"].strip()


def test_local_html_assets_links_and_anchors_are_valid():
    topics = help_topics()
    topic_ids = {topic["id"] for topic in topics}
    pages = {}
    for path in HELP.rglob("*.html"):
        parser = PageInfo()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path.resolve()] = parser

    for path, parser in pages.items():
        for tag, attr, value, target, rel in parser.links:
            parsed = urlsplit(value)
            if parsed.scheme:
                assert tag == "a" and attr == "href", value
                assert value in VERIFIED_MINITAB_URLS, value
                assert parsed.netloc == "support.minitab.com"
                assert target == "_blank" and "noopener" in rel
                continue
            if not parsed.path:
                target_path = path
            else:
                target_path = (path.parent / unquote(parsed.path)).resolve()
            assert target_path.is_file(), (path, value)
            if parsed.fragment:
                anchor = unquote(parsed.fragment)
                if target_path == (HELP / "index.html").resolve():
                    assert anchor == "home" or anchor in topic_ids
                else:
                    assert anchor in pages[target_path].ids, (path, value)


def test_browser_search_is_local_and_contains_page_body_text():
    index_html = (HELP / "index.html").read_text(encoding="utf-8")
    app_js = (HELP / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'src="assets/search-index.js"' in index_html
    assert 'src="assets/app.js"' in index_html
    assert "fetch(" not in app_js and "XMLHttpRequest" not in app_js
    index = json.loads(build_search_index().split(" = ", 1)[1].rstrip()[:-1])
    assert all(item["text"] for item in index)


def test_main_and_dialog_help_entry_points_use_local_topics():
    app = (ROOT / "code" / "MiniJMP.py").read_text(encoding="utf-8")
    dialog = (ROOT / "code" / "dialog.py").read_text(encoding="utf-8")
    assert "帮助文档" in app and "在线帮助" not in app
    assert "self.main.bind('<F1>'" in app
    assert "self.main.bind('<F1>', self.help)" in dialog
    assert "open_help(self.__class__.__name__, parent=self.main)" in dialog


def test_open_help_resolves_home_and_dialog_class_alias(monkeypatch):
    opened = []
    monkeypatch.setattr(help_link.webbrowser, "open",
                        lambda url, **kwargs: opened.append((url, kwargs)) or True)
    assert help_link.open_help()
    assert help_link.open_help("DescribeDialog")
    assert opened[0][0].startswith("file:") and opened[0][0].endswith("help/index.html")
    assert opened[1][0].endswith("help/index.html#stats.describe")


def test_open_help_reports_missing_topic_and_browser_failure(monkeypatch):
    errors = []
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "showerror",
                        lambda title, message, **kwargs: errors.append((title, message)))
    monkeypatch.setattr(help_link.webbrowser, "open", lambda *args, **kwargs: False)
    assert not help_link.open_help("does-not-exist")
    assert "无法打开离线帮助" in errors[-1][1]
    assert not help_link.open_help()
    assert "浏览器未能打开" in errors[-1][1]


def test_open_help_checks_missing_target_without_crashing(monkeypatch, tmp_path):
    from tkinter import messagebox
    errors = []
    help_root = tmp_path / "help"
    help_root.mkdir()
    (help_root / "index.html").write_text("help", encoding="utf-8")
    (help_root / "help-map.json").write_text(json.dumps({"topics": [
        {"id": "missing", "page": "pages/missing.html#missing", "dialog_classes": []}
    ]}), encoding="utf-8")
    monkeypatch.setattr(help_link, "HELP_DIR", help_root)
    monkeypatch.setattr(messagebox, "showerror",
                        lambda title, message, **kwargs: errors.append(message))
    opened = []
    monkeypatch.setattr(help_link.webbrowser, "open", lambda *args, **kwargs: opened.append(args))
    assert not help_link.open_help("missing")
    assert "无法打开离线帮助" in errors[0]
    assert not opened


def test_open_help_rejects_targets_outside_the_help_directory(monkeypatch, tmp_path):
    from tkinter import messagebox
    errors = []
    help_root = tmp_path / "help"
    help_root.mkdir()
    (help_root / "index.html").write_text("help", encoding="utf-8")
    (help_root / "help-map.json").write_text(json.dumps({"topics": [
        {"id": "outside", "page": "../README.md#outside", "dialog_classes": []}
    ]}), encoding="utf-8")
    monkeypatch.setattr(help_link, "HELP_DIR", help_root)
    monkeypatch.setattr(messagebox, "showerror",
                        lambda title, message, **kwargs: errors.append(message))
    opened = []
    monkeypatch.setattr(help_link.webbrowser, "open", lambda *args, **kwargs: opened.append(args))
    assert not help_link.open_help("outside")
    assert "路径无效" in errors[0]
    assert not opened


def test_help_paths_stay_relative_after_project_relocation(monkeypatch, tmp_path):
    relocated = tmp_path / "relocated"
    (relocated / "code").mkdir(parents=True)
    shutil.copy2(ROOT / "code" / "help_link.py", relocated / "code" / "help_link.py")
    shutil.copytree(HELP, relocated / "help")
    spec = importlib.util.spec_from_file_location("relocated_help_link", relocated / "code" / "help_link.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    opened = []
    monkeypatch.setattr(module.webbrowser, "open",
                        lambda url, **kwargs: opened.append(url) or True)
    assert module.open_help("DescribeDialog")
    assert opened[0].endswith("help/index.html#stats.describe")
    assert str(relocated).replace("\\", "/") in opened[0]


def test_pi_import_topic_is_unique_searchable_and_available_offline(monkeypatch):
    topics = help_topics()
    assert len(topics) == 77
    assert len({topic['id'] for topic in topics}) == len(topics)
    topic, = [item for item in topics if item['id'] == 'files.pi_import']
    assert topic['entry'] == 'MiniJMP.import_pi_data'
    assert topic['dialog_classes'] == ['PIImportDialog']
    assert topic['page'] == 'pages/operations.html#files.pi_import'
    page = (HELP / topic['page'].split('#')[0]).read_text(encoding='utf-8')
    parser = PageInfo()
    parser.feed(page)
    assert topic['id'] in parser.ids
    assert ('a', 'href', '#files.pi_import', None, '') in parser.links
    index = json.loads(build_search_index().split(' = ', 1)[1].rstrip()[:-1])
    item, = [item for item in index if item['id'] == topic['id']]
    for text in ['PIReader.exe', 'config.txt', 'PI SDK', '插值历史数据', '取消', 'Timestamp']:
        assert text in item['text']
    opened = []
    monkeypatch.setattr(help_link.webbrowser, 'open', lambda url, **kw: opened.append(url) or True)
    assert help_link.open_help(topic['id'])
    assert opened == [(HELP / 'index.html').resolve().as_uri() + '#files.pi_import']
