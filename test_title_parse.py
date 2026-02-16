import re

def test_parse(filename_stem):
    match = re.match(r'^(\[.*?\])?\s*(\d+\s*[\.\s]\s*)?(.*)$', filename_stem)
    channel_part = ""
    actual_title = filename_stem
    if match:
        channel_part = (match.group(1) or "").strip()
        actual_title = (match.group(3) or "").strip()
    
    image_title = actual_title
    bili_title = (f"{channel_part} {actual_title}").strip()
    return image_title, bili_title

test_cases = [
    "[Growing With The Flow] 42.uni advice w niamh  Ep. 41",
    "[Test Channel] 01. Welcome Episode",
    "Solo Episode title Ep. 5",
    "123. Just a number",
    "[Brand]No Space Title"
]

for tc in test_cases:
    img, bili = test_parse(tc)
    print(f"Original: {tc}")
    print(f"  -> Image: {img}")
    print(f"  -> Bili:  {bili}\n")
