
from pathlib import Path
import fitz

project_dir = Path(__file__).resolve().parent
pdf_dir = project_dir / "data" / "raw"
pdf_files = list(pdf_dir.glob("*.pdf"))

if not pdf_files:
    raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

pdf_path = pdf_files[0]

with fitz.open(pdf_path) as document:
    print(f"PDF: {pdf_path.name}")
    print(f"Total pages: {len(document)}")

    for page_index in range(min(10, len(document))):
        page = document[page_index]
        extracted_text = page.get_text("text").strip()
        images = page.get_images(full=True)

        print(
            f"Page {page_index + 1}: "
            f"{len(extracted_text)} text characters, "
            f"{len(images)} embedded image(s)"
        )
