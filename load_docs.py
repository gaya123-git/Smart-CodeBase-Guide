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

def split_into_chunks(body, rel_path, file_title):
    chunks = []
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


# find every markdown file
file_list = [p for p in root_dir.rglob("*") if p.suffix in (".md", ".mdx")]

# run the pipeline on all of them
all_chunks = []
for file_path in sorted(file_list):
    text = file_path.read_text(encoding="utf-8")
    title, body = split_front_matter(text)
    rel_path = file_path.relative_to(root_dir).as_posix()
    all_chunks.extend(split_into_chunks(body, rel_path, title or file_path.stem))

print(len(file_list), "files ->", len(all_chunks), "chunks")