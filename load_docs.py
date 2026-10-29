import re
import hashlib
from pathlib import Path

ROOT_DIR = Path("data/companion.home-assistant-master/docs")

FENCE = "`" * 3
MIN_SIZE = 200
MAX_SIZE = 2000   # placeholder, change it after the token check


def split_front_matter(text):
    if text.startswith("---"):
        parts = text.split("---", 2)
        label = parts[1]
        body = parts[2].strip()
        title = None
        for line in label.splitlines():
            line = line.strip()
            if line.startswith("title:"):
                title = line[len("title:"):].strip().strip('"\'')
                break
    else:
        title = None
        body = text
    return title, body


# body (actual Markdown content), rel_path, file_title (title of the whole file)
def split_into_chunks(body, rel_path, file_title):
    chunks = []                # start with an empty list
    parent = None              # the current level-2 heading
    heading_path = file_title  # intro text before any heading uses the file title
    lines = []
    in_code_block = False

    for line in body.splitlines():
        # entering or leaving a code block flips the switch
        if line.strip().startswith(FENCE):
            in_code_block = not in_code_block

        is_heading = (not in_code_block) and line.startswith(("# ", "## ", "### ", "#### "))

        if is_heading:
            # a new heading means the previous section is finished: save it
            text = "\n".join(lines).strip()
            if text:
                chunks.append({
                    "file": rel_path,
                    "title": file_title,
                    "heading": heading_path,
                    "text": text,
                })

            level = len(line) - len(line.lstrip("#"))
            name = line.lstrip("#").strip()
            if level <= 2:
                parent = name
                heading_path = name
            else:
                heading_path = f"{parent} > {name}" if parent else name
            lines = []
        else:
            lines.append(line)

    # the last section never meets a "next heading", so save it here
    text = "\n".join(lines).strip()
    if text:
        chunks.append({
            "file": rel_path,
            "title": file_title,
            "heading": heading_path,
            "text": text,
        })
    return chunks


def merge_small_chunks(chunks, min_size):
    merged = []
    for chunk in chunks:
        if merged:
            last = merged[-1]
            if len(last["text"]) < min_size and last["file"] == chunk["file"]:
                merged[-1] = {
                    "file": last["file"],
                    "title": last["title"],
                    "heading": last["heading"],
                    "text": last["text"] + "\n\n" + chunk["text"],
                }
                continue
        merged.append(chunk)
    return merged


def make_units(text):
    """Cut text into paragraphs. A code block always stays in one piece."""
    units, current, in_code = [], [], False
    for line in text.splitlines():
        if line.strip().startswith(FENCE):
            in_code = not in_code
        if line.strip() == "" and not in_code:
            if current:
                units.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        units.append("\n".join(current))
    return units


def pack_rows(rows, header, footer, max_size):
    """Group rows into pieces under max_size. Every piece gets the header."""
    pieces, current = [], []
    base = len(header) + len(footer)
    size = base
    for row in rows:
        if current and size + len(row) + 1 > max_size:
            pieces.append(header + "\n".join(current) + footer)
            current, size = [], base
        current.append(row)
        size += len(row) + 1
    if current:
        pieces.append(header + "\n".join(current) + footer)
    return pieces


def split_big_unit(unit, max_size):
    """One paragraph is too big: split a markdown table by rows, other text by lines."""
    if len(unit) <= max_size or FENCE in unit:
        return [unit]                      # small enough, or a code block: keep whole
    lines = unit.splitlines()
    if lines[0].startswith("|") and len(lines) > 2:
        header = "\n".join(lines[:2]) + "\n"   # column names + the |---| line
        return pack_rows(lines[2:], header, "", max_size)
    return pack_rows(lines, "", "", max_size)


def split_html_table(text, max_size):
    sections = re.findall(r"(<thead>.*?</thead>)\s*<tbody>(.*?)</tbody>", text, re.S)
    pieces = []
    for thead, tbody in sections:
        rows = re.findall(r"<tr>.*?</tr>", tbody, re.S)
        header = "<table>\n" + thead + "\n<tbody>\n"
        footer = "\n</tbody>\n</table>"
        pieces.extend(pack_rows(rows, header, footer, max_size))
    return pieces


def split_big_chunk(chunk, max_size):
    text = chunk["text"]
    if len(text) <= max_size:
        return [chunk]                     # not big, leave it alone

    if text.lstrip().startswith("<table"):
        pieces = split_html_table(text, max_size)
    else:
        units = []
        for unit in make_units(text):
            units.extend(split_big_unit(unit, max_size))
        pieces, current = [], ""
        for unit in units:
            if current and len(current) + 2 + len(unit) > max_size:
                pieces.append(current)
                current = unit
            else:
                current = current + "\n\n" + unit if current else unit
        if current:
            pieces.append(current)

    result = []
    for piece in pieces:
        new_chunk = dict(chunk)            # copy file, title, heading
        new_chunk["text"] = piece          # replace only the text
        result.append(new_chunk)
    return result


def make_chunk_id(chunk):
    """Same file + heading + text -> same ID on every run. Changed text -> new ID."""
    raw = chunk["file"] + "|" + chunk["heading"] + "|" + chunk["text"]
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_all_chunks(root_dir=ROOT_DIR, min_size=MIN_SIZE, max_size=MAX_SIZE):
    """Build, merge, split, and give every chunk an ID. Returns a list of dicts."""
    file_list = [p for p in root_dir.rglob("*") if p.suffix in (".md", ".mdx")]

    chunks = []
    for file_path in sorted(file_list):
        text = file_path.read_text(encoding="utf-8")
        title, body = split_front_matter(text)
        rel_path = file_path.relative_to(root_dir).as_posix()
        chunks.extend(split_into_chunks(body, rel_path, title or file_path.stem))

    chunks = merge_small_chunks(chunks, min_size)

    final_chunks = []
    for chunk in chunks:
        final_chunks.extend(split_big_chunk(chunk, max_size))

    seen = {}
    for chunk in final_chunks:
        base_id = make_chunk_id(chunk)
        count = seen.get(base_id, 0)       # 0 the first time we meet this ID
        seen[base_id] = count + 1
        chunk["id"] = base_id if count == 0 else f"{base_id}-{count}"
    return final_chunks


if __name__ == "__main__":
    all_chunks = load_all_chunks()
    text_lengths = [len(c["text"]) for c in all_chunks]
    print(len(all_chunks), "chunks")
    print("Min length:", min(text_lengths))
    print("Max length:", max(text_lengths))
    print("Avg length:", round(sum(text_lengths) / len(text_lengths)))