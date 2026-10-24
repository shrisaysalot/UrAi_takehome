import fitz
import json
import unicodedata

doc = fitz.open(r"data/balance_sheet_page4.pdf")
page = doc[0]

info = {
    "page_count": len(doc),
    "rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
    "drawings_count": len(page.get_drawings()),
    "images_count": len(page.get_images()),
    "fonts": page.get_fonts(),
}

blocks = page.get_text("blocks")
info["blocks_count"] = len(blocks)

# Detailed words
words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
info["words_count"] = len(words)

# Group words by lines/blocks and check coordinates
# get_text words
word_records = []
for w in words:
    word_records.append({
        "bbox": [round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2)],
        "text": w[4],
        "block": w[5],
        "line": w[6],
        "word": w[7]
    })
info["words"] = word_records

# Horizontal lines
drawings = page.get_drawings()
h_lines = []
rect_drawings = []
for d in drawings:
    for item in d.get("items", []):
        if item[0] == "l":
            p1, p2 = item[1], item[2]
            if abs(p1.y - p2.y) < 1.0:
                h_lines.append({
                    "y": round(p1.y, 2),
                    "x0": round(min(p1.x, p2.x), 2),
                    "x1": round(max(p1.x, p2.x), 2),
                    "color": d.get("color"),
                    "width": d.get("width")
                })
        elif item[0] == "re":
            rect_drawings.append({
                "rect": [round(coord, 2) for coord in item[1]],
                "fill": d.get("fill"),
                "color": d.get("color")
            })

info["horizontal_lines"] = h_lines
info["rect_drawings_count"] = len(rect_drawings)
info["rect_drawings_sample"] = rect_drawings[:10]

# Analysis of text x0 positions (indentation analysis)
x_positions = {}
for w in word_records:
    # only consider Japanese labels on the left half (e.g. x0 < 300)
    if w["bbox"][0] < 300 and any('\u4e00' <= char <= '\u9fff' or '\u3040' <= char <= '\u30ff' for char in w["text"]):
        x_rounded = round(w["bbox"][0], 1)
        x_positions[x_rounded] = x_positions.get(x_rounded, 0) + 1

info["left_label_x0_freq"] = sorted(x_positions.items(), key=lambda x: x[0])

with open("data/inspection_report.json", "w", encoding="utf-8") as f:
    json.dump(info, f, ensure_ascii=False, indent=2)

print("Saved inspection report.")
