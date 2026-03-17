"""Pagination utilities."""

from math import ceil

from pydantic import BaseModel
from sqlalchemy.orm import Query


class PageMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel):
    meta: PageMeta
    items: list


def paginate(query: Query, page: int = 1, per_page: int = 20) -> tuple[list, PageMeta]:
    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    total = query.count()
    total_pages = ceil(total / per_page) if total > 0 else 1

    items = query.offset((page - 1) * per_page).limit(per_page).all()

    meta = PageMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )

    return items, meta
