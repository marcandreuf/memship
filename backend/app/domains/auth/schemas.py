"""Auth request/response schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Use a simple regex instead of EmailStr to allow dev domains (.test, .local)
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=8)


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: Email
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: Email


class PasswordResetRequest(BaseModel):
    email: Email


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class RoleSummary(BaseModel):
    id: int
    slug: str
    name: str


class UserResponse(BaseModel):
    id: int
    email: str
    roles: list[RoleSummary] = []
    permissions: list[str] = []
    is_active: bool
    person_id: int
    first_name: str
    last_name: str
    member_id: int | None = None
    member_number: str | None = None
    gender: str | None = None
    photo_url: str | None = None
    email_verified: bool = False
    # Drives the portal's "awaiting approval" gate — None for staff accounts
    # that have no member record.
    member_status: str | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    message: str = "Login successful"


class MessageResponse(BaseModel):
    message: str
    reset_token: str | None = None
    # Dev-mode escape hatch, mirroring reset_token: surfaced only when no email
    # transport is configured so local setups can complete the flow.
    verification_token: str | None = None


class SsoProvidersResponse(BaseModel):
    """Which SSO providers are configured on this install."""

    google: bool = False
    apple: bool = False


class RegisterResponse(BaseModel):
    """Registration no longer logs the user in — it reports what happens next."""

    message: str
    email: str
    member_status: str
    requires_approval: bool
    email_verified: bool = False
    verification_token: str | None = None


class PermissionRead(BaseModel):
    key: str
    domain: str
    action: str
    reserved: bool
    label_key: str
    description_key: str


class RoleRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None = None
    is_system: bool
    permission_keys: list[str]
    assigned_user_count: int
    assignable: bool


class RoleCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    description: str | None = None
    permission_keys: list[str] = []


class RoleUpdate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    description: str | None = None
    permission_keys: list[str] | None = None


class UserRolesUpdate(BaseModel):
    role_ids: list[int]


class UserActiveUpdate(BaseModel):
    is_active: bool


class UserListItem(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool
    roles: list[RoleSummary]
