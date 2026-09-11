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

    items = query.offset((page - 1) * per_page).limit(per_page).all()

    # A short page is the last one, so the total is already known: the rows
    # before it plus the rows on it. Only a full page needs the COUNT(*) to
    # tell whether more follow — which spares it on every list that fits in
    # one page (most of a club's) and on the last page of the ones that don't.
    # An empty page past the end still counts, since it says nothing about
    # how many rows precede it.
    if 0 < len(items) < per_page:
        total = (page - 1) * per_page + len(items)
    else:
        total = query.count()
    total_pages = ceil(total / per_page) if total > 0 else 1

    meta = PageMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )

    return items, meta
