
from pathlib import Path
import json
import fitz  # PyMuPDF

# --------------------------------------------------
# Project paths
# --------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[2]

PDF_PATH = (
    PROJECT_DIR
    / "data"
    / "raw"
    / "brezza_warranty_manual.pdf"
)

OUTPUT_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "pages.jsonl"
)

# --------------------------------------------------
# Validate input PDF
# --------------------------------------------------
if not PDF_PATH.exists():
    raise FileNotFoundError(
        f"PDF not found: {PDF_PATH}"
    )

if not PDF_PATH.is_file():
    raise FileNotFoundError(
        f"PDF path is not a file: {PDF_PATH}"
    )

# Create output directory if it does not exist
OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)

# --------------------------------------------------
# Initialize counters
# --------------------------------------------------
empty_pages = []
total_characters = 0
pages_processed = 0
total_images = 0

print(f"Starting PDF extraction: {PDF_PATH.name}")

# --------------------------------------------------
# Extract PDF pages
# --------------------------------------------------
with fitz.open(PDF_PATH) as document:

    # Capture page count while document is open
    total_pages = document.page_count

    print(f"Total pages in PDF: {total_pages}")

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8"
    ) as output_file:

        for page_index in range(total_pages):

            # Human-readable page numbers start at 1
            page_number = page_index + 1

            # Load current page
            page = document.load_page(page_index)

            # Extract text
            text = page.get_text("text").strip()

            # Count embedded images on this page
            image_count = len(
                page.get_images(full=True)
            )

            # Prepare page-level record
            record = {
                "source_file": PDF_PATH.name,
                "page_number": page_number,
                "text": text,
                "char_count": len(text),
                "embedded_image_count": image_count,
            }

            # Write one JSON object per line
            output_file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                ) + "\n"
            )

            # Update statistics
            pages_processed += 1
            total_characters += len(text)
            total_images += image_count

            if not text:
                empty_pages.append(page_number)

            # Progress indicator every 25 pages
            if pages_processed % 25 == 0:
                print(
                    f"Processed {pages_processed}"
                    f"/{total_pages} pages..."
                )

# --------------------------------------------------
# Print final summary AFTER closing the PDF
# --------------------------------------------------
print("\n" + "=" * 50)
print("PDF EXTRACTION COMPLETED")
print("=" * 50)

print(f"PDF: {PDF_PATH.name}")
print(f"Pages in PDF: {total_pages}")
print(f"Pages processed: {pages_processed}")
print(f"Total extracted characters: {total_characters}")
print(f"Total embedded image references: {total_images}")
print(f"Pages with no extracted text: {len(empty_pages)}")
print(f"Empty-text page numbers: {empty_pages}")
print(f"Output saved to: {OUTPUT_PATH}")
print("=" * 50)
