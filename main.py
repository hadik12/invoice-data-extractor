import argparse
import csv
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from extractor import SUPPORTED_SUFFIXES, ExtractionError, extract_invoice, make_client
from models import InvoiceData

CSV_COLUMNS = [
    "source_file",
    "vendor",
    "date",
    "invoice_number",
    "currency",
    "item_name",
    "quantity",
    "unit_price",
    "line_total",
    "invoice_total",
]


def append_to_csv(csv_path: Path, source: str, data: InvoiceData) -> None:
    is_new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if is_new:
            writer.writeheader()
        invoice_fields = {
            "source_file": source,
            "vendor": data.vendor,
            "date": data.date,
            "invoice_number": data.invoice_number,
            "currency": data.currency,
            "invoice_total": data.total,
        }
        if not data.line_items:
            writer.writerow(invoice_fields)
            return
        for item in data.line_items:
            writer.writerow(
                invoice_fields
                | {
                    "item_name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "line_total": round(item.quantity * item.unit_price, 2),
                }
            )


def print_invoice(source: str, data: InvoiceData, seconds: float) -> None:
    width = 66
    print("=" * width)
    print(f"{source}  ({seconds:.1f}s)")
    print("-" * width)
    print(f"Vendor  : {data.vendor or '?'}")
    print(f"Date    : {data.date or '?'}")
    print(f"Number  : {data.invoice_number or '?'}")
    print(f"{'Item':<38} {'Qty':>5} {'Price':>10} {'Sum':>10}")
    print("-" * width)
    for item in data.line_items:
        name = item.name if len(item.name) <= 38 else item.name[:35] + "..."
        line_total = item.quantity * item.unit_price
        print(f"{name:<38} {item.quantity:>5g} {item.unit_price:>10.2f} {line_total:>10.2f}")
    print("-" * width)
    total = f"{data.total:.2f}" if data.total is not None else "?"
    print(f"{'TOTAL':<38} {'':>5} {'':>10} {total:>10} {data.currency or ''}")
    print("=" * width)
    print()


def collect_inputs(args: argparse.Namespace) -> list[Path]:
    if args.batch:
        folder = Path(args.batch)
        if not folder.is_dir():
            sys.exit(f"Error: '{folder}' is not a directory")
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
        if not files:
            sys.exit(f"Error: no supported files ({', '.join(sorted(SUPPORTED_SUFFIXES))}) in '{folder}'")
        return files
    path = Path(args.input)
    if not path.is_file():
        sys.exit(f"Error: file '{path}' not found")
    return [path]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured data from invoice/receipt photos and PDFs using Gemini."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="path to a single .jpg/.png/.pdf file")
    source.add_argument("--batch", help="path to a folder — process every supported file in it")
    parser.add_argument("--output", default="invoices.csv", help="CSV file to append results to")
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv()
    client = make_client()
    files = collect_inputs(args)
    csv_path = Path(args.output)

    processed, failed = 0, []
    started = time.perf_counter()
    for path in files:
        t0 = time.perf_counter()
        try:
            data = extract_invoice(client, path)
        except ExtractionError as err:
            failed.append(path.name)
            print(f"[FAILED] {err}\n")
            continue
        print_invoice(path.name, data, time.perf_counter() - t0)
        append_to_csv(csv_path, path.name, data)
        processed += 1

    elapsed = time.perf_counter() - started
    print(f"Done: {processed}/{len(files)} file(s) in {elapsed:.1f}s -> {csv_path}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
