"""Generate the file://-safe JavaScript search index from help HTML."""
import json
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELP_DIR = ROOT / "help"


class TopicText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.counts = defaultdict(int)
        self.text = defaultdict(list)

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            topic_id = dict(attrs).get("id")
            if topic_id:
                if self.current is not None:
                    raise ValueError("Help topic sections cannot be nested.")
                self.current = topic_id
                self.counts[topic_id] += 1

    def handle_endtag(self, tag):
        if tag == "section":
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.text[self.current].append(data)


def build_search_index():
    help_map = json.loads((HELP_DIR / "help-map.json").read_text(encoding="utf-8"))
    topics = help_map["topics"]
    ids = [topic["id"] for topic in topics]
    if len(ids) != len(set(ids)):
        raise ValueError("Help topic IDs must be unique.")

    by_page = defaultdict(list)
    for topic in topics:
        page, marker, anchor = topic["page"].partition("#")
        if not marker or anchor != topic["id"] or Path(page).is_absolute():
            raise ValueError(f"Invalid help target for {topic['id']}.")
        source = (HELP_DIR / page).resolve()
        try:
            source.relative_to(HELP_DIR.resolve())
        except ValueError as error:
            raise ValueError(f"Help target escapes the help directory: {topic['id']}.") from error
        if not source.is_file():
            raise FileNotFoundError(source)
        by_page[page].append(topic["id"])

    extracted = {}
    for page, topic_ids in by_page.items():
        parser = TopicText()
        parser.feed((HELP_DIR / page).read_text(encoding="utf-8"))
        for topic_id in topic_ids:
            if parser.counts[topic_id] != 1:
                raise ValueError(f"Expected one HTML section for {topic_id}.")
            body = " ".join(" ".join(parser.text[topic_id]).split())
            if not body:
                raise ValueError(f"Help section is empty: {topic_id}.")
            extracted[topic_id] = body

    index = [
        {
            "id": topic["id"],
            "title": topic["title"],
            "category": topic["category"],
            "page": topic["page"],
            "text": " ".join((topic["original_name"], extracted[topic["id"]])),
        }
        for topic in topics
    ]
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return "window.MINIJMP_HELP_INDEX = " + payload + ";\n"


if __name__ == "__main__":
    output = HELP_DIR / "assets" / "search-index.js"
    output.write_text(build_search_index(), encoding="utf-8")
