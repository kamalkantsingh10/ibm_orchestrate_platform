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

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from cockpit_api.db.session import get_session
from cockpit_api.deps.current_user import get_current_user
from cockpit_api.repositories.case_repo import CaseRepo
from cockpit_api.services import case_service
from cockpit_api.services.document_storage import (
    FileTooLargeError,
    InvalidFilenameError,
    NotAPDFError,
    delete_document,
    list_documents,
    write_pdf,
)

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
    dependencies=[Depends(get_current_user)],
    summary="Upload one or more PDF documents to a case",
    description=(
        "Accepts multipart/form-data with one or more files in the `files` "
        "field. Each file must be a valid PDF (magic-byte check) ≤ 10 MB. "
        "On success, returns the per-file metadata + the case's updated "
        "document_refs list."
    ),
)
async def upload_documents(
    case_id: CaseIdPath,
    files: list[UploadFile],
    session: Annotated[AsyncSession, Depends(get_session)],
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

        await CaseRepo.add_document_ref(session, case_id, doc.filename)
        stored.append(
            StoredDocumentResponse(
                filename=doc.filename,
                size_bytes=doc.size_bytes,
                uploaded_at=doc.uploaded_at,
            )
        )

    refreshed = await case_service.get_case(session, case_id)
    refs = list(refreshed.customer_metadata.extra.get("document_refs", []))
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
            )
            for d in docs
        ],
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
