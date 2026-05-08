"""Generate per-case sample KYC PDFs — Story 3.8 / AC #8.

Originally created one PDF per filename and copied it across all three
demo cases — which leaked Vora's name into Ananya's PAN card and Shree's
address proof. This rewrite materialises **one PDF per (case, filename)
pair** into ``./fixtures/uploads/<case_id>/<filename>.pdf`` directly,
substituting the case's customer fixture into the document body so the
watsonx LLM extracts case-correct fields.

``./fixtures/sample_pdfs/`` is no longer the source of truth — the seed
script writes straight to the per-case upload dirs. The legacy
``sample-pdfs`` make target still works as a single-PDF dev aid but is no
longer referenced by ``seed-uploads``.

Run directly:
    poetry -C apps/cockpit-api run python tools/scripts/generate_sample_pdfs.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contracts.cases import Case, get_demo_case_fixtures
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# ─────────────────────────── per-case context ──────────────────────────────


def _ctx(case: Case) -> dict[str, Any]:
    """Flatten the case's fixture into a substitution dict."""
    extra = case.customer_metadata.extra
    return {
        "customer_name": case.customer_metadata.customer_name,
        "customer_type": case.customer_metadata.customer_type or "",
        "registration_number": extra.get("registration_number", ""),
        "incorporation_date": extra.get("incorporation_date", ""),
        "registered_address": extra.get(
            "registered_address",
            extra.get("residential_address", ""),
        ),
        "primary_contact_name": extra.get("primary_contact_name", ""),
        "pan": extra.get("pan", ""),
        "date_of_birth": extra.get("date_of_birth", ""),
        "annual_revenue_inr": extra.get("annual_revenue_inr"),
        "annual_income_inr": extra.get("annual_income_inr"),
    }


# ────────────────────── per-document body templates ────────────────────────
# Each template is a list of paragraphs. Template substitutions read from the
# context dict above. Every {customer_name} reference now resolves to the
# CASE's name, not a global default.


def _incorporation_certificate(c: dict[str, Any]) -> list[str]:
    return [
        "<b>CERTIFICATE OF INCORPORATION</b>",
        "Pursuant to sub-section (2) of section 7 of the Companies Act, 2013, "
        "the Registrar of Companies hereby certifies that:",
        f"<b>{c['customer_name'].upper()}</b> is incorporated on "
        f"{c['incorporation_date'] or 'a date in 2024'}, and that the company "
        "is limited by shares.",
        # Single-line labels for the smart-fixture / vision-LLM extractors.
        f"<b>Company name:</b> {c['customer_name']}",
        f"<b>Corporate Identification Number (CIN):</b> {c['registration_number']}",
        f"<b>Date of Incorporation:</b> {c['incorporation_date']}",
        f"<b>Registered Office:</b> {c['registered_address']}",
        "Issued under my hand at Mumbai.",
    ]


def _company_pan_card(c: dict[str, Any]) -> list[str]:
    # Companies get a synthetic CIN-derived PAN to avoid recycling Vora's.
    pan_stub = (c["registration_number"][:5] or "AAACX") + "1234R"
    return [
        "<b>INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA</b>",
        "Permanent Account Number Card",
        f"<b>Name:</b> {c['customer_name']}",
        f"<b>PAN:</b> {pan_stub}",
        f"<b>Date of Allotment:</b> shortly after {c['incorporation_date']}",
        "Signature of authorised signatory.",
    ]


def _individual_pan_card(c: dict[str, Any]) -> list[str]:
    return [
        "<b>INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA</b>",
        "Permanent Account Number Card",
        f"<b>Name:</b> {c['customer_name']}",
        f"<b>PAN:</b> {c['pan'] or 'AAFPX0000Q'}",
        f"<b>Date of Birth:</b> {c['date_of_birth']}",
        "Signature of authorised signatory.",
    ]


def _address_proof(c: dict[str, Any]) -> list[str]:
    return [
        "<b>ADDRESS VERIFICATION CERTIFICATE</b>",
        f"This is to certify that the address of <b>{c['customer_name']}</b> is:",
        # Single-line label so smart-fixture regex (and any future LLM
        # extractor) finds the value cleanly.
        f"<b>Address:</b> {c['registered_address']}",
        "Issued by: Mumbai Municipal Corporation",
        "Date of issue: shortly after onboarding.",
    ]


def _director_id(c: dict[str, Any]) -> list[str]:
    director_name = c["primary_contact_name"] or "Director (unnamed)"
    return [
        "<b>DIRECTOR IDENTIFICATION CERTIFICATE</b>",
        "<b>Director Identification Number (DIN):</b> 08234567",
        f"<b>Director Name:</b> {director_name}",
        f"<b>Company:</b> {c['customer_name']}",
        "Issued by the Ministry of Corporate Affairs, Government of India.",
    ]


def _ubo_declaration(c: dict[str, Any]) -> list[str]:
    return [
        "<b>ULTIMATE BENEFICIAL OWNER DECLARATION</b>",
        "We hereby declare the following ownership chain:",
        f"<b>{c['customer_name']}</b> (India) "
        "→ <b>Coastal Equity Partners Pte Ltd</b> (Singapore, 100%) "
        "→ <b>Anchor Trust Services (BVI)</b> (British Virgin Islands, 100%)",
        f"Effective date: {c['incorporation_date']}.",
    ]


def _shareholder_pattern(c: dict[str, Any]) -> list[str]:
    director_name = c["primary_contact_name"] or "Lead director"
    return [
        f"<b>SHAREHOLDER PATTERN — {c['customer_name']}</b>",
        f"5 shareholders on record. Majority owner: <b>{director_name} (62%)</b>. "
        "Remaining 38% split across 4 shareholders, none holding more than 15%.",
        "As filed with the Registrar of Companies.",
    ]


def _bank_statement(c: dict[str, Any]) -> list[str]:
    return [
        "<b>HDFC BANK — STATEMENT OF ACCOUNT</b>",
        f"<b>Account Holder:</b> {c['customer_name']}",
        "<b>Account Number:</b> 0123456789012",
        "<b>Period:</b> Q1 FY 2024-25 (April – June 2024)",
        "Opening balance: INR 12,40,000",
        "Closing balance: INR 18,75,000",
    ]


def _aadhaar(c: dict[str, Any]) -> list[str]:
    # Aadhaar last-4 is a fixed synthetic 4-digit number — NOT derived from
    # PAN (which the original demo bug picked up "567Q" because PAN ends
    # with a letter). The stub uses 4567; we keep that for continuity.
    last4 = "4567"
    return [
        "<b>AADHAAR — UNIQUE IDENTIFICATION AUTHORITY OF INDIA</b>",
        f"<b>Name:</b> {c['customer_name']}",
        f"<b>Aadhaar last 4 digits:</b> {last4}",
        f"<b>Date of Birth:</b> {c['date_of_birth']}",
    ]


def _income_proof(c: dict[str, Any]) -> list[str]:
    income = c["annual_income_inr"] or c["annual_revenue_inr"] or 0
    return [
        "<b>INCOME TAX RETURN — ASSESSMENT YEAR 2024-25</b>",
        f"<b>Name:</b> {c['customer_name']}",
        f"<b>PAN:</b> {c['pan'] or 'AAFPX0000Q'}",
        f"<b>Annual Income (INR):</b> {income:,}",
        "Filed: 31 July 2024.",
    ]


# Filename → builder. Companies and individuals share most filenames; we
# resolve PAN content based on customer_type so a company doesn't get an
# individual's PAN body and vice-versa.
_BUILDERS: dict[str, dict[str, Any]] = {
    "incorporation_certificate.pdf": {"company": _incorporation_certificate, "individual": None},
    "pan_card.pdf": {"company": _company_pan_card, "individual": _individual_pan_card},
    "address_proof.pdf": {"company": _address_proof, "individual": _address_proof},
    "director_id.pdf": {"company": _director_id, "individual": None},
    "ubo_declaration.pdf": {"company": _ubo_declaration, "individual": None},
    "shareholder_pattern.pdf": {"company": _shareholder_pattern, "individual": None},
    "bank_statement_q1.pdf": {"company": _bank_statement, "individual": _bank_statement},
    "aadhaar.pdf": {"company": None, "individual": _aadhaar},
    "income_proof.pdf": {"company": _income_proof, "individual": _income_proof},
}


def render_for_case(case: Case, uploads_root: Path) -> int:
    """Materialise every doc in the case's ``document_refs`` to disk."""
    case_dir = uploads_root / case.id
    case_dir.mkdir(parents=True, exist_ok=True)
    ctx = _ctx(case)
    customer_type = case.customer_metadata.customer_type or "company"

    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    count = 0
    for filename in case.customer_metadata.extra.get("document_refs", []):
        builders = _BUILDERS.get(filename)
        if builders is None:
            continue
        builder = builders.get(customer_type)
        if builder is None:
            # Fallback: pick whichever builder exists.
            builder = builders.get("company") or builders.get("individual")
            if builder is None:
                continue

        path = case_dir / filename
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            title=f"{case.customer_metadata.customer_name} — {filename}",
            author="KYC Cockpit demo",
        )
        flowables = []
        for text in builder(ctx):
            flowables.append(Paragraph(text, body))
            flowables.append(Spacer(1, 12))
        doc.build(flowables)
        count += 1
    return count


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    uploads_root = repo_root / "fixtures" / "uploads"
    fixtures = get_demo_case_fixtures(datetime.now(UTC))

    total = 0
    for case in fixtures:
        n = render_for_case(case, uploads_root)
        total += n
        print(f"  {case.id} ({case.customer_metadata.customer_name}): {n} files")
    print(f"Generated {total} per-case PDFs at {uploads_root}/<case_id>/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
