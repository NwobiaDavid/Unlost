"""Create a folder of realistically messy sample files to try unlost on.

    npm run demo:files                 -> ~/unlost-demo
    node scripts/py.mjs scripts/make_demo.py D:\\somewhere\\else
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sidecar" / "tests"))
from conftest import make_docx, make_pdf, make_text_image, set_mtime  # noqa: E402


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "unlost-demo"
    root.mkdir(parents=True, exist_ok=True)

    make_pdf(root / "document(3).pdf", [
        "Motor Insurance Policy - Comprehensive Cover",
        "Insured vehicle: Toyota Corolla 2018, registration LSR 482 KJ",
        "Policy period: 01 Feb 2026 to 31 Jan 2027. Annual premium: N185,000.",
        "Report any accident or theft within 30 days to make a claim.",
    ])
    make_text_image(root / "IMG_4821.png", [
        "WEST AFRICAN EXAMINATIONS COUNCIL",
        "West African Senior School Certificate",
        "Candidate: Ada Obi   WAEC 2019",
        "English Language B3   Mathematics A1",
    ])
    make_text_image(root / "Screenshot 2026-05-02 091514.png", [
        "Booking confirmed - Air Peace",
        "Lagos (LOS) to Abuja (ABV)",
        "Fri 16 May 2026, 07:30   Seat 14C",
        "Booking reference: QX7P2M",
    ])
    make_docx(root / "Untitled.docx", [
        "INVOICE #2031",
        "Date: 12 March 2026",
        "Billed to: Brightpath Design Ltd",
        "Website redesign, 40 hours at $60",
        "Total due: $2,400",
    ])
    set_mtime(root / "Untitled.docx", 2026, 3, 12)
    make_pdf(root / "scan_0007.pdf", [
        "FEDERAL REPUBLIC OF NIGERIA - PASSPORT DATA PAGE",
        "Surname: OBI   Given names: ADA",
        "Date of issue: 04 JUN 2021   Date of expiry: 03 JUN 2031",
    ])
    for month in range(1, 13):
        name = f"scan00{month:02d}.txt" if month % 3 else f"WhatsApp Document 2025-{month:02d}-01.txt"
        (root / name).write_text(
            f"RENT RECEIPT\nReceived from Ada Obi the sum of N250,000 being rent for {month:02d}/2025.\n"
            f"Flat 3, 12 Allen Avenue, Ikeja. Landlord: Mr Bello.", "utf-8")
        set_mtime(root / name, 2025, month, 2)
    make_docx(root / "download (2).docx", [
        "Electricity bill - Ikeja Electric",
        "Billing period: August 2026",
        "Units used: 214 kWh   Amount payable: N48,150",
    ])
    set_mtime(root / "download (2).docx", 2026, 9, 3)
    (root / "notes.md").write_text("Grocery list: rice, beans, plantain, pepper, palm oil.", "utf-8")

    print(f"Demo files written to {root}")
    print("In unlost: Settings > Add folder > choose that folder (or pick it during onboarding).")


if __name__ == "__main__":
    main()
