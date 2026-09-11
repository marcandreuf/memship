"""paginate only runs COUNT(*) when the page it fetched cannot tell it the total."""

from app.core.pagination import paginate


class _Query:
    """Stands in for a SQLAlchemy Query over ``rows``; records COUNT calls."""

    def __init__(self, rows):
        self.rows = rows
        self.counts = 0
        self._offset = 0
        self._limit = None

    def offset(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        return self.rows[self._offset : self._offset + self._limit]

    def count(self):
        self.counts += 1
        return len(self.rows)


def test_a_short_first_page_needs_no_count():
    q = _Query(list(range(7)))
    items, meta = paginate(q, page=1, per_page=20)
    assert items == list(range(7))
    assert (meta.total, meta.total_pages) == (7, 1)
    assert q.counts == 0


def test_a_short_later_page_derives_the_total_from_its_offset():
    q = _Query(list(range(45)))
    items, meta = paginate(q, page=3, per_page=20)
    assert items == list(range(40, 45))
    assert (meta.total, meta.total_pages) == (45, 3)
    assert q.counts == 0


def test_a_full_page_counts_because_more_may_follow():
    q = _Query(list(range(40)))
    items, meta = paginate(q, page=1, per_page=20)
    assert len(items) == 20
    assert (meta.total, meta.total_pages) == (40, 2)
    assert q.counts == 1


def test_an_empty_page_counts_because_it_says_nothing_about_the_total():
    q = _Query(list(range(5)))
    items, meta = paginate(q, page=3, per_page=20)
    assert items == []
    assert (meta.total, meta.total_pages) == (5, 1)
    assert q.counts == 1


def test_an_empty_table_reports_one_page_of_nothing():
    q = _Query([])
    items, meta = paginate(q)
    assert items == []
    assert (meta.total, meta.total_pages) == (0, 1)


def test_per_page_is_clamped():
    q = _Query(list(range(500)))
    items, meta = paginate(q, page=1, per_page=1000)
    assert len(items) == 100
    assert meta.per_page == 100
    _, meta = paginate(_Query([1]), page=0, per_page=0)
    assert (meta.page, meta.per_page) == (1, 1)
