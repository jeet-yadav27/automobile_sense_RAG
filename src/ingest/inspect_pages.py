
from pathlib import Path
import json

PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_DIR / "data" / "processed" / "pages.jsonl"

if not INPUT_PATH.exists():
    raise FileNotFoundError(f"File not found: {INPUT_PATH}")

record_count = 0

with INPUT_PATH.open("r", encoding="utf-8") as file:
    for line in file:
        record = json.loads(line)
        record_count += 1

        if record_count <= 3:
            print(f"\n--- Record {record_count} ---")
            print("Source:", record["source_file"])
            print("Page:", record["page_number"])
            print("Characters:", record["char_count"])
            print("Images:", record["embedded_image_count"])
            print("Text preview:", record["text"][:300])

print(f"\nTotal valid JSONL records: {record_count}")
