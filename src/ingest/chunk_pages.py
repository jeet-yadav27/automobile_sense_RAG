
from pathlib import Path
import json

PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = PROJECT_DIR / "data" / "processed" / "pages.jsonl"
OUTPUT_PATH = PROJECT_DIR / "data" / "processed" / "chunks.jsonl"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

if not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
    raise ValueError("Overlap must be smaller than chunk size.")

def split_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks


total_chunks = 0
skipped_pages = []

with INPUT_PATH.open("r", encoding="utf-8") as input_file:
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:

        for line in input_file:
            page = json.loads(line)

            page_number = page["page_number"]
            text = page["text"]

            if not text.strip():
                skipped_pages.append(page_number)
                continue

            page_chunks = split_text(
                text,
                chunk_size=CHUNK_SIZE,
                overlap=CHUNK_OVERLAP
            )

            for chunk_index, chunk_text in enumerate(page_chunks):

                record = {
                    "chunk_id": f"page_{page_number}_chunk_{chunk_index}",
                    "source_file": page["source_file"],
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "char_count": len(chunk_text)
                }

                output_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

                total_chunks += 1

print("=" * 50)
print("CHUNKING COMPLETED")
print("=" * 50)
print(f"Total chunks created: {total_chunks}")
print(f"Skipped empty pages: {skipped_pages}")
print(f"Output: {OUTPUT_PATH}")
