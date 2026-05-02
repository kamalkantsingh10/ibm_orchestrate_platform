"""Generate sample KYC PDFs for the demo — Story 3.8 / AC #8.

Creates plausible-looking (but fake) PDFs at
``./fixtures/sample_pdfs/<filename>.pdf`` matching the filenames in
the demo's pinned case fixtures (incorporation_certificate.pdf,
pan_card.pdf, address_proof.pdf, etc.).

Re-run via ``make seed-uploads`` (which also copies them per-case).

Run directly:
    poetry -C apps/cockpit-api run python tools/scripts/generate_sample_pdfs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Per-filename canned content. Mirrors the FixtureDocAILLM extractions in
# apps/agents/src/agents/adapters/doc_ai/fixture.py so a watsonx-mode run
# against these PDFs has a reasonable chance of extracting the same fields
# the fixture mode would surface.

_DOCS: dict[str, list[str]] = {
    "incorporation_certificate.pdf": [
        "<b>CERTIFICATE OF INCORPORATION</b>",
        "Pursuant to sub-section (2) of section 7 of the Companies Act, 2013, "
        "the Registrar of Companies hereby certifies that:",
        "<b>VORA CAPITAL HOLDINGS PRIVATE LIMITED</b> is incorporated on this "
        "twenty-second day of August, two thousand and twenty-four, "
        "and that the company is limited by shares.",
        "<b>Corporate Identification Number (CIN):</b> U67120MH2024PTC444789",
        "<b>Date of Incorporation:</b> 22 August 2024",
        "<b>Registered Office:</b> Suite 402, Sea Breeze Heights, "
        "Bandra West, Mumbai 400050, Maharashtra, India",
        "Issued under my hand at Mumbai this twenty-second day of August, 2024.",
    ],
    "pan_card.pdf": [
        "<b>INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA</b>",
        "Permanent Account Number Card",
        "<b>Name:</b> Vora Capital Holdings Pvt Ltd",
        "<b>PAN:</b> AAFCV1234R",
        "<b>Date of Allotment:</b> 25 August 2024",
        "Signature of authorised signatory.",
    ],
    "address_proof.pdf": [
        "<b>ADDRESS VERIFICATION CERTIFICATE</b>",
        "This is to certify that the registered office of "
        "<b>Vora Capital Holdings Pvt Ltd</b> is located at:",
        "Suite 402, Sea Breeze Heights, Bandra West, Mumbai — 400050",
        "Issued by: Mumbai Municipal Corporation",
        "Date of issue: 30 August 2024",
    ],
    "director_id.pdf": [
        "<b>DIRECTOR IDENTIFICATION CERTIFICATE</b>",
        "<b>Director Identification Number (DIN):</b> 08234567",
        "<b>Director Name:</b> Devansh Vora",
        "<b>Company:</b> Vora Capital Holdings Pvt Ltd",
        "Issued by the Ministry of Corporate Affairs, Government of India.",
    ],
    "ubo_declaration.pdf": [
        "<b>ULTIMATE BENEFICIAL OWNER DECLARATION</b>",
        "We hereby declare the following ownership chain:",
        "<b>Vora Capital Holdings Pvt Ltd</b> (India) "
        "→ <b>Coastal Equity Partners Pte Ltd</b> (Singapore, 100%) "
        "→ <b>Anchor Trust Services (BVI)</b> (British Virgin Islands, 100%)",
        "Effective date: 22 August 2024.",
    ],
    "shareholder_pattern.pdf": [
        "<b>SHAREHOLDER PATTERN — Vora Capital Holdings Pvt Ltd</b>",
        "5 shareholders on record. Majority owner: <b>Devansh Vora (62%)</b>. "
        "Remaining 38% split across 4 shareholders, none holding more than 15%.",
        "As filed with the Registrar of Companies on 25 August 2024.",
    ],
    "bank_statement_q1.pdf": [
        "<b>HDFC BANK — STATEMENT OF ACCOUNT</b>",
        "<b>Account Holder:</b> Vora Capital Holdings Pvt Ltd",
        "<b>Account Number:</b> 0123456789012",
        "<b>Period:</b> Q1 FY 2024-25 (April – June 2024)",
        "Opening balance: INR 12,40,000",
        "Closing balance: INR 18,75,000",
    ],
    "aadhaar.pdf": [
        "<b>AADHAAR — UNIQUE IDENTIFICATION AUTHORITY OF INDIA</b>",
        "<b>Name:</b> Ananya Iyer",
        "<b>Aadhaar last 4 digits:</b> 4567",
        "<b>Date of Birth:</b> 04 November 1985",
    ],
    "income_proof.pdf": [
        "<b>INCOME TAX RETURN — ASSESSMENT YEAR 2024-25</b>",
        "<b>Name:</b> Ananya Iyer",
        "<b>PAN:</b> AAFPI4567Q",
        "<b>Annual Income (INR):</b> 24,000,000",
        "Filed: 31 July 2024",
    ],
}


def render(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]

    count = 0
    for filename, paragraphs in _DOCS.items():
        path = output_dir / filename
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            title=filename,
            author="KYC Cockpit demo",
        )
        flowables = []
        for text in paragraphs:
            flowables.append(Paragraph(text, body))
            flowables.append(Spacer(1, 12))
        doc.build(flowables)
        count += 1
    return count


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "fixtures" / "sample_pdfs"
    n = render(output_dir)
    print(f"Generated {n} sample PDFs at {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
