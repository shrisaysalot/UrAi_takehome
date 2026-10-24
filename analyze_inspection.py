import json

with open('data/inspection_report.json', encoding='utf-8') as f:
    info = json.load(f)

print("Page rect:", info["rect"])
print("Fonts:")
for font in info["fonts"]:
    print(" ", font)

print("\nLeft label x0 positions and frequencies:")
for x0, count in info["left_label_x0_freq"]:
    print(f"  x0 = {x0:5.1f} : {count:2d} occurrences")

print(f"\nHorizontal lines count: {len(info['horizontal_lines'])}")
for l in info["horizontal_lines"]:
    print(f"  y={l['y']:6.2f}, x0={l['x0']:6.2f}, x1={l['x1']:6.2f}, width={l.get('width')}")

# Let's inspect all words sorted by y then x
words = info["words"]
# Sort words primarily by y0, then x0
words_sorted = sorted(words, key=lambda w: (w["bbox"][1], w["bbox"][0]))
print(f"\nTotal words: {len(words)}")

# Let's group words into visual lines by comparing y-distance
lines = []
curr_line = []
for w in words_sorted:
    if not curr_line:
        curr_line.append(w)
    else:
        # Check vertical overlap or y center distance
        last_y_mid = (curr_line[-1]["bbox"][1] + curr_line[-1]["bbox"][3]) / 2.0
        w_y_mid = (w["bbox"][1] + w["bbox"][3]) / 2.0
        if abs(w_y_mid - last_y_mid) < 3.5: # on the same line
            curr_line.append(w)
        else:
            lines.append(curr_line)
            curr_line = [w]
if curr_line:
    lines.append(curr_line)

with open('data/inspection_summary.txt', 'w', encoding='utf-8') as out:
    out.write(f"Page rect: {info['rect']}\n")
    out.write("Fonts:\n")
    for font in info["fonts"]:
        out.write(f"  {font}\n")

    out.write("\nLeft label x0 positions and frequencies:\n")
    for x0, count in info["left_label_x0_freq"]:
        out.write(f"  x0 = {x0:5.1f} : {count:2d} occurrences\n")

    out.write(f"\nHorizontal lines count: {len(info['horizontal_lines'])}\n")
    for l in info["horizontal_lines"]:
        out.write(f"  y={l['y']:6.2f}, x0={l['x0']:6.2f}, x1={l['x1']:6.2f}, width={l.get('width')}\n")

    out.write(f"\nGrouped into {len(lines)} visual lines:\n")
    for idx, line in enumerate(lines):
        line_text = " | ".join([f"{w['text']} (x0={w['bbox'][0]:.1f}, x1={w['bbox'][2]:.1f})" for w in line])
        y_pos = line[0]["bbox"][1]
        out.write(f"Line {idx:2d} [y={y_pos:5.1f}]: {line_text}\n")

print("Saved inspection_summary.txt")
