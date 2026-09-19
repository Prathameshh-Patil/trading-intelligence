"""Wire shapes. Mirrored by `packages/contracts/types.ts` -- change both."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["user", "admin"]
Status = Literal["pending", "approved", "rejected", "suspended"]
Tier = Literal["core", "core_journal"]


class Me(BaseModel):
    id: int
    email: str
    role: Role
    status: Status
    created_at: datetime


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: Me


class SessionInfo(BaseModel):
    family_id: str
    created_at: datetime
    last_used_at: datetime | None
    user_agent: str | None
    ip: str | None
    current: bool


class Release(BaseModel):
    is_public: bool
    can_preview: bool


class SetRelease(BaseModel):
    is_public: bool


class LicenceKey(BaseModel):
    """S5's `GET /api/v1/keys/mine` response, as frozen."""

    key: str
    tier: Tier
    created_at: datetime


class Activation(BaseModel):
    """Whether the desktop app has ever validated the key -- S5's shape is
    frozen, so this rides on its own route rather than as a fourth field."""

    activated: bool
    last_validated_at: datetime | None


class ValidateResponse(BaseModel):
    """S3, verbatim: `valid: false` is a 200."""

    valid: bool
    tier: Tier | None
    expires_at: datetime | None
    reason: Literal["expired", "revoked", "unknown"] | None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str
    plan: str
    method: str
    amount: int
    currency: str
    reference: str
    proof_name: str
    proof_url: str
    status: str
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class TicketIn(BaseModel):
    email: EmailStr | None = None
    category: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10_000)


class TicketReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    created_at: datetime
    from_staff: bool


class TicketOut(BaseModel):
    id: int
    ref: str
    email: str
    category: str
    subject: str
    body: str
    status: str
    created_at: datetime
    replies: list[TicketReplyOut]


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class WaitlistIn(BaseModel):
    email: EmailStr


class WaitlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    created_at: datetime


class KeySummary(BaseModel):
    id: int
    user_id: int
    email: str
    prefix: str
    tier: Tier
    status: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    last_validated_at: datetime | None


class UserOut(BaseModel):
    id: int
    email: str
    role: Role
    status: Status
    created_at: datetime
    last_login_at: datetime | None
    approved_at: datetime | None
    approved_by: str | None
    rejection_reason: str | None
    admin_note: str | None
    key: KeySummary | None
    payments_count: int
    open_tickets: int


class UserDetail(UserOut):
    payments: list[PaymentOut]
    tickets: list[TicketOut]
    sessions: list[SessionInfo]


class ApproveResponse(BaseModel):
    user: UserOut
    key: LicenceKey
    minted: bool


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class NoteIn(BaseModel):
    note: str = Field(max_length=4000)


class RoleIn(BaseModel):
    role: Role


class PromoteIn(BaseModel):
    email: EmailStr


class Stats(BaseModel):
    pending: int
    approved: int
    rejected: int
    suspended: int
    active_keys: int
    validations_24h: int
    open_tickets: int
    waitlist: int
    signups_7d: int
    live_admins: int


class AuditOut(BaseModel):
    id: int
    actor: str | None
    action: str
    target_type: str
    target_id: str
    detail: dict | None
    ip: str | None
    created_at: datetime


# --- alerts -------------------------------------------------------------
# Mirrored by `packages/contracts/alerts.ts`.

AlertTier = Literal["breaking", "signal", "analysis"]


class AlertIn(BaseModel):
    tier: AlertTier
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10_000)
    symbol: str | None = Field(default=None, max_length=32)
    expires_at: datetime | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tier: AlertTier
    title: str
    body: str
    symbol: str | None
    created_at: datetime
    expires_at: datetime | None
