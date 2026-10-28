import re   
from pathlib import Path

root_dir = Path("data/companion.home-assistant-master/docs")


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


# Load one file and separate the label from the content
text = (root_dir / "core" / "sensors.md").read_text(encoding="utf-8")
title, body = split_front_matter(text)

# Print the headings with their levels
print("TITLE:", title)
for line in body.splitlines():
    if line.startswith(("# ", "## ", "### ", "#### ")):
        level = len(line) - len(line.lstrip("#"))
        clean_line = line.lstrip("#").strip()
        print(level, clean_line)


FENCE = "`" * 3
#body (actual Markdown content), #rel_path, #file_title (title of the whole file )
def split_into_chunks(body, rel_path, file_title):
    chunks = [] # start with an empty list 
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




file_list = [p for p in root_dir.rglob("*") if p.suffix in (".md", ".mdx")]



all_chunks = []

for file_path in sorted(file_list):
    text = file_path.read_text(encoding="utf-8")
    title, body = split_front_matter(text)
    rel_path = file_path.relative_to(root_dir).as_posix()
    all_chunks.extend(split_into_chunks(body, rel_path, title or file_path.stem))




MIN_SIZE = 200

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

all_chunks = merge_small_chunks(all_chunks, MIN_SIZE)


MAX_SIZE = 2000   # placeholder, change it after you decide


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


final_chunks = []
for chunk in all_chunks:
    final_chunks.extend(split_big_chunk(chunk, MAX_SIZE))
all_chunks = final_chunks


print(len(file_list), "files ->", len(all_chunks), "chunks")


# 1. Create a list of text lengths for every chunk
text_lengths = [len(c['text']) for c in all_chunks]


# 2. Calculate the metrics
print("--Min Length--")
min_length = min(text_lengths)
print(min_length)
print("--Max Length--")
max_length = max(text_lengths)
print(max_length)
print("--Avg Length--")
avg_length = sum(text_lengths) / len(text_lengths)
print(avg_length)




sorted_chunks = sorted(all_chunks, key=lambda c: len(c["text"]))

# first five 
longest = sorted_chunks[-5:]
shortest = sorted_chunks[:5]
print("5 LONGEST")
for c in longest:
    info= len(c["text"]), c["file"], c["heading"]
    print(info)
    print(c["text"][:100])
print("5 SHORTEST")
for c in shortest:
    info=len(c["text"]), c["file"], c["heading"]
    print(info)
    print(c["text"][:100])
       