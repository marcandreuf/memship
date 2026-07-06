"""Member card DTOs."""

from pydantic import BaseModel


class CardOrganization(BaseModel):
    name: str
    logo_url: str | None = None
    brand_color: str | None = None


class CardResponse(BaseModel):
    member_id: int
    full_name: str
    member_number: str
    status: str
    photo_url: str | None = None
    organization: CardOrganization
    token: str


class ScanRequest(BaseModel):
    token: str


class ScanResponse(BaseModel):
    member_id: int
    full_name: str
    member_number: str
    status: str
    photo_url: str | None = None


class AssignNumbersResponse(BaseModel):
    assigned: int
