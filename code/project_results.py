"""Plain-data snapshots for project reports and completed Matplotlib figures."""

import io
import math
from numbers import Integral, Real

from PIL import Image

from stat_table import StatTable


def _cell(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        return number if math.isfinite(number) else None
    return str(value)


def report_block(value, end):
    if not isinstance(value, StatTable):
        return {"text": str(value) + end}
    return {"text": str(value), "end": end, "title": value.title,
            "headers": list(value.headers), "display": [list(row) for row in value.display],
            "values": [[_cell(cell) for cell in row] for row in value.values],
            "number_formats": list(value.number_formats)}


def restore_block(block):
    if set(block) == {"text"} and isinstance(block["text"], str):
        return block["text"], ""
    keys = {"text", "end", "title", "headers", "display", "values", "number_formats"}
    if (set(block) != keys or not isinstance(block["text"], str)
            or not isinstance(block["end"], str)
            or not isinstance(block["values"], list)
            or any(not isinstance(row, list) or any(
                type(cell) not in (str, int, float, bool, type(None))
                or (type(cell) is float and not math.isfinite(cell)) for cell in row
            ) for row in block["values"])):
        raise ValueError("统计结果表结构无效。")
    return StatTable(block["text"], block["title"], block["headers"], block["values"],
                     display=block["display"], number_formats=block["number_formats"]), block["end"]


def figure_png(figure):
    width, height = figure.get_size_inches()
    dpi = min(110., 2300. / max(width, height))
    with io.BytesIO() as stream:
        figure.savefig(stream, format="png", dpi=dpi)
        return stream.getvalue()


def png_image(data, *, verify=False):
    with Image.open(io.BytesIO(data), formats=["PNG"]) as image:
        if image.width * image.height > 6_000_000:
            raise ValueError("工程图形超过 600 万像素。")
        if verify:
            image.verify()
            return None
        return image.convert("RGB")


def write_results(archive, records):
    entries = []
    for i, record in enumerate(records, 1):
        metadata = {key: value for key, value in record.items() if key != "png"}
        if "png" in record:
            path = f"results/figure_{i:04d}.png"
            archive.writestr(path, record["png"])
            metadata["image"] = path
        entries.append(metadata)
    return entries


def read_results(archive, entries, paths, sheet_names):
    if not isinstance(entries, list):
        raise ValueError("无效的工程结果列表。")
    for i, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("无效的工程结果。")
        source = entry.get("source")
        if (source is not None and (not isinstance(source, str) or source not in sheet_names)
                or not all(isinstance(entry.get(k), str) for k in ("title", "time", "source_label"))
                or not isinstance(entry.get("blocks"), list)):
            raise ValueError("无效的工程结果来源或内容。")
        for block in entry["blocks"]:
            if not isinstance(block, dict):
                raise ValueError("无效的工程报告内容。")
            restore_block(block)
        columns = entry.get("columns", [])
        parameters = entry.get("parameters", {})
        if (not isinstance(columns, list) or not all(isinstance(col, str) for col in columns)
                or not isinstance(parameters, dict)
                or not all(isinstance(value, str) for value in parameters.values())):
            raise ValueError("无效的分析历史参数。")
        image_path = entry.pop("image", None)
        if image_path is not None:
            if image_path != f"results/figure_{i:04d}.png" or image_path in paths:
                raise ValueError("无效的工程图形路径。")
            paths.add(image_path)
            entry["png"] = archive.read(image_path)
            png_image(entry["png"], verify=True)
    return entries
