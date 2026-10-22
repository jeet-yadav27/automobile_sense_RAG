
import json
from pathlib import Path
import tiktoken

PROJECT_DIR = Path(__file__).resolve().parents[2]
CHUNKS_PATH = PROJECT_DIR / "data" / "processed" / "chunks.jsonl"

PRICE_PER_MILLION = 0.02
tokenizer = tiktoken.get_encoding("cl100k_base")

total_tokens = 0
total_chunks = 0
max_chunk_tokens = 0

with CHUNKS_PATH.open("r", encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        chunk = json.loads(line)
        token_count = len(tokenizer.encode(chunk["text"]))

        total_tokens += token_count
        total_chunks += 1
        max_chunk_tokens = max(max_chunk_tokens, token_count)

estimated_cost = (
    total_tokens / 1_000_000
) * PRICE_PER_MILLION

print("=" * 50)
print("EMBEDDING COST ESTIMATE")
print("=" * 50)
print(f"Total chunks: {total_chunks}")
print(f"Total tokens: {total_tokens:,}")
print(f"Average tokens per chunk: {total_tokens / total_chunks:.1f}")
print(f"Maximum tokens in one chunk: {max_chunk_tokens}")
print(f"Estimated cost (USD): ${estimated_cost:.6f}")
