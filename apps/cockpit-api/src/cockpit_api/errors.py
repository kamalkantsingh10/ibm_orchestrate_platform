"""RFC 7807 Problem Details — Story 2.2.

Demo profile: omits the bank-buyer scope's ``tenant_id`` and ``request_id``
extensions. If the bank-buyer scope revives, both fields get retro-fitted as
``Optional`` extensions to ``RFC7807Problem`` here.
"""

from __future__ import annotations

from pydantic import BaseModel


class RFC7807Problem(BaseModel):
    """A Problem Details object as defined by RFC 7807 § 3.1."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
