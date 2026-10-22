
from pathlib import Path
import json

PROJECT_DIR = Path(__file__).resolve().parents[2]
CHUNKS_PATH = PROJECT_DIR / "data" / "processed" / "chunks.jsonl"

with CHUNKS_PATH.open("r", encoding="utf-8") as file:
    chunks = [json.loads(line) for line in file if line.strip()]

print(f"Total chunks: {len(chunks)}")

# Inspect the first three chunks
for chunk in chunks[:3]:
    print("\n" + "=" * 50)
    print("Chunk ID:", chunk["chunk_id"])
    print("Source:", chunk["source_file"])
    print("Page:", chunk["page_number"])
    print("Characters:", chunk["char_count"])
    print("Text preview:")
    print(chunk["text"][:400])

# Check for duplicate chunk IDs
ids = [chunk["chunk_id"] for chunk in chunks]
print("\nUnique chunk IDs:", len(set(ids)))
print("Duplicate IDs:", len(ids) - len(set(ids)))

# Check whether adjacent chunks on the same page overlap
pair = next(
    (
        (a, b)
        for a, b in zip(chunks, chunks[1:])
        if a["page_number"] == b["page_number"]
        and b["chunk_index"] == a["chunk_index"] + 1
        and a["char_count"] == 1000
    ),
    None,
)

if pair:
    first, second = pair
    print("\nOverlap verification:")
    print("First chunk:", first["chunk_id"])
    print("Second chunk:", second["chunk_id"])
    print(
        "200-character overlap matches:",
        first["text"][-200:] == second["text"][:200]
    )
else:
    print("\nNo suitable adjacent chunk pair found.")
