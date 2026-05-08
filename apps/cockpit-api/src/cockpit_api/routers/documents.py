"""Document upload router — Story 3.8.

Endpoints:
* ``POST /v1/cases/{case_id}/documents`` — multipart upload (one or more
  PDFs); persists to ``./fixtures/uploads/<case_id>/<filename>``; updates
  the case's ``customer_metadata.extra.document_refs`` list.
* ``GET /v1/cases/{case_id}/documents`` — list uploaded files with metadata.
* ``DELETE /v1/cases/{case_id}/documents/{filename}`` — remove a file +
  its document_refs entry.

The case canvas's upload zone (Story 3.8 § AC5) drives all three.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from contracts.ledger import (
    ActorType,
    EvidenceAttachedPayload,
    LedgerEntry,
)
from contracts.sse import SseEvent
from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from cockpit_api.db.session import get_session
from cockpit_api.deps.current_user import get_current_user
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services import case_service, ledger_service
from cockpit_api.services.document_storage import (
    DocumentKind,
    FileTooLargeError,
    InvalidFilenameError,
    NotAPDFError,
    delete_document,
    delete_evidence,
    get_document_path,
    get_evidence_path,
    list_documents,
    list_evidence,
    write_evidence,
    write_pdf,
)
from cockpit_api.services.sse_registry import publish_safe

router = APIRouter(prefix="/v1/cases", tags=["documents"])

_CASE_ID_PATH = Path(
    pattern=r"^case_[0-9A-HJKMNP-TV-Z]{26}$",
    description="Case ID (`case_<ULID>`)",
)
CaseIdPath = Annotated[str, _CASE_ID_PATH]


# ───────────────────────────── response models ────────────────────────────


class StoredDocumentResponse(BaseModel):
    """One document on disk, surfaced through the API."""

    filename: str
    size_bytes: int = Field(ge=0)
    uploaded_at: datetime
    # Story 8.6 — SHA-256 hex digest of the file contents. Empty string
    # for documents persisted before Story 8.6 landed (no retro-hash).
    sha256: str = ""


class UploadResponse(BaseModel):
    """Reply to a successful POST."""

    case_id: str
    uploaded: list[StoredDocumentResponse]
    document_refs: list[str]


class ListResponse(BaseModel):
    """Reply to GET /documents."""

    case_id: str
    items: list[StoredDocumentResponse]


# ───────────────────────────── routes ──────────────────────────────────────


@router.post(
    "/{case_id}/documents",
    response_model=UploadResponse,
    summary="Upload one or more PDF documents (intake) or evidence files to a case",
    description=(
        "Accepts multipart/form-data with one or more files in the `files` "
        "field. With the default `kind=intake`, each file must be a valid "
        "PDF (magic-byte check) ≤ 10 MB and is added to the case's "
        "intake document_refs. With `kind=evidence` (Story 8.5), the MIME "
        "whitelist widens to PDF / PNG / JPG / TXT / EML and the file lands "
        "under `case_<id>/evidence/`; Story 8.6 also appends a "
        "`case.evidence_attached` ledger entry carrying the SHA-256."
    ),
)
async def upload_documents(
    case_id: CaseIdPath,
    files: list[UploadFile],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[object, Depends(get_current_user)],
    kind: DocumentKind = "intake",
    ingest_method: Literal["drop", "clipboard", "email_paste", "unspecified"] = "unspecified",
) -> UploadResponse:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required (field name: files)",
        )

    # 404 if case missing.
    await case_service.get_case(session, case_id)

    stored: list[StoredDocumentResponse] = []
    for upload in files:
        body = await upload.read()
        try:
            if kind == "evidence":
                # Story 8.5 — wider MIME whitelist, persists under
                # `case_<id>/evidence/`. No magic-byte sniff (extension
                # is the source of truth in demo scope).
                doc = write_evidence(case_id, upload.filename or "", body)
            else:
                doc = write_pdf(case_id, upload.filename or "", body)
        except InvalidFilenameError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except FileTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except NotAPDFError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(exc),
            ) from exc

        if kind == "intake":
            # Evidence uploads are not added to `customer_metadata.extra
            # .document_refs` — that list drives intake fan-out. Evidence
            # is queried separately via `GET /evidence`.
            await CaseRepo.add_document_ref(session, case_id, doc.filename)
        else:
            # Story 8.6 / AC #2 — write a `case.evidence_attached`
            # ledger entry per evidence file. Hash is the integrity
            # anchor; user_id ties the attachment to the request actor.
            user_id = getattr(user, "id", "user_analyst")
            try:
                await ledger_service.get_ledger_writer().append(
                    LedgerEntry(
                        id=f"led_{ULID()!s}",
                        actor_type=ActorType.OFFICER,
                        actor_id=user_id,
                        case_id=case_id,
                        action="case.evidence_attached",
                        payload=EvidenceAttachedPayload(
                            filename=doc.filename,
                            sha256=doc.sha256,
                            size_bytes=doc.size_bytes,
                            ingest_method=ingest_method,
                        ),
                        recorded_at=datetime.now(UTC),
                    )
                )
            except Exception:  # noqa: BLE001
                # Loud-fail logging would normally go here; for the
                # demo we let the upload succeed even if the ledger
                # write is transient. The Audit Trail Timeline will
                # surface the gap.
                import logging

                logging.getLogger(__name__).exception(
                    "documents.evidence_ledger_failed case=%s file=%s",
                    case_id,
                    doc.filename,
                )
        stored.append(
            StoredDocumentResponse(
                filename=doc.filename,
                size_bytes=doc.size_bytes,
                uploaded_at=doc.uploaded_at,
                sha256=doc.sha256,
            )
        )

    refreshed = await case_service.get_case(session, case_id)
    refs = list(refreshed.customer_metadata.extra.get("document_refs", []))
    # Story 4.6 — fan-out so the cockpit-ui invalidates document queries.
    # Story 8.5 — evidence uploads use the same fan-out signal so the
    # EvidenceShelf invalidates alongside the Documents panel.
    await publish_safe(
        case_id,
        SseEvent(event="case.documents_changed", data={"case_id": case_id, "kind": kind}),
    )
    return UploadResponse(case_id=case_id, uploaded=stored, document_refs=refs)


@router.get(
    "/{case_id}/documents",
    response_model=ListResponse,
    dependencies=[Depends(get_current_user)],
    summary="List the case's uploaded documents",
)
async def list_case_documents(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListResponse:
    await case_service.get_case(session, case_id)
    docs = list_documents(case_id)
    return ListResponse(
        case_id=case_id,
        items=[
            StoredDocumentResponse(
                filename=d.filename,
                size_bytes=d.size_bytes,
                uploaded_at=d.uploaded_at,
                sha256=d.sha256,
            )
            for d in docs
        ],
    )


@router.get(
    "/{case_id}/documents/{filename}/download",
    # No auth: the cockpit-ui opens these via <a href> / new tab where the
    # browser cannot send the X-Cockpit-Demo-User header. The fixture-only
    # demo accepts that trade-off; bank-buyer scope re-attaches auth via
    # signed URLs (FR43, deferred).
    summary="Download a stored document as application/pdf",
    description=(
        "Story 4 hardening — returns the case's PDF straight from "
        "``./fixtures/uploads/<case_id>/<filename>`` so the analyst can "
        "preview the file the agents have been reading. 404 if the file "
        "isn't on disk; 400 on a malformed filename."
    ),
)
async def download_case_document(
    case_id: CaseIdPath,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    await case_service.get_case(session, case_id)
    try:
        path = get_document_path(case_id, filename)
    except InvalidFilenameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {filename!r} not found for case {case_id!r}",
        )
    return FileResponse(
        path=path,
        media_type="application/pdf",
        # ``inline`` so the browser previews instead of forcing a download.
        # The user-supplied filename is sanitized by ``get_document_path``.
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ─── Story 8.5 — evidence routes ──────────────────────────────────────────


@router.get(
    "/{case_id}/evidence",
    response_model=ListResponse,
    dependencies=[Depends(get_current_user)],
    summary="List the case's attached evidence (Story 8.5)",
)
async def list_case_evidence(
    case_id: CaseIdPath,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListResponse:
    await case_service.get_case(session, case_id)
    docs = list_evidence(case_id)
    return ListResponse(
        case_id=case_id,
        items=[
            StoredDocumentResponse(
                filename=d.filename,
                size_bytes=d.size_bytes,
                uploaded_at=d.uploaded_at,
                sha256=d.sha256,
            )
            for d in docs
        ],
    )


@router.get(
    "/{case_id}/evidence/{filename}/download",
    summary="Download an attached evidence file (Story 8.5)",
    description=(
        "Returns the evidence file straight from "
        "``./fixtures/uploads/<case_id>/evidence/<filename>``. The "
        "EvidenceShelf opens these via <a href> in a new tab; same "
        "no-auth trade-off as Story 3.8's intake download route."
    ),
)
async def download_case_evidence(
    case_id: CaseIdPath,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    await case_service.get_case(session, case_id)
    try:
        path = get_evidence_path(case_id, filename)
    except InvalidFilenameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {filename!r} not found for case {case_id!r}",
        )
    # Mime-by-extension; the cockpit-ui only needs `application/octet-stream`
    # to open in a new tab. Browsers sniff content for image/text rendering.
    return FileResponse(path=path)


@router.delete(
    "/{case_id}/evidence/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
    summary="Delete an attached evidence file (Story 8.5)",
)
async def delete_case_evidence(
    case_id: CaseIdPath,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await case_service.get_case(session, case_id)
    try:
        removed = delete_evidence(case_id, filename)
    except InvalidFilenameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {filename!r} not found for case {case_id!r}",
        )
    await publish_safe(
        case_id,
        SseEvent(event="case.documents_changed", data={"case_id": case_id, "kind": "evidence"}),
    )


@router.delete(
    "/{case_id}/documents/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
    summary="Delete an uploaded document and its document_refs entry",
)
async def delete_case_document(
    case_id: CaseIdPath,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await case_service.get_case(session, case_id)
    try:
        removed = delete_document(case_id, filename)
    except InvalidFilenameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {filename!r} not found for case {case_id!r}",
        )
    await CaseRepo.remove_document_ref(session, case_id, filename)
    # Story 4.6 — fan-out so the cockpit-ui invalidates document queries.
    await publish_safe(
        case_id,
        SseEvent(event="case.documents_changed", data={"case_id": case_id}),
    )
