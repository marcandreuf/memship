"""No update schema accepts an explicit null for a boolean the API cannot
represent as one (#565).

The text-field version of this rule lives in `test_blank_text_fields.py`
(#285). Booleans were never covered, and they fail in a worse way. Where the
column is NOT NULL the write is refused and the request 500s with nothing
lost. Where the column is *nullable* the write commits, serialising the reply
then fails, and the row is left holding NULL -- which the list endpoint
validates through the same Response model, so one request makes the whole list
500 for every caller until somebody fixes the row by hand.

The requirement is derived rather than listed: if an update takes
``bool | None`` and the matching Response model declares a plain ``bool``, then
null is not a value the API can hand back, so it must not be one the API
accepts. A boolean added later is covered without touching this file.
"""

import importlib
import pkgutil
from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError

import app.domains


def _schema_models():
    for info in pkgutil.walk_packages(app.domains.__path__, "app.domains."):
        if "schemas" not in info.name.rsplit(".", 1)[-1]:
            continue
        module = importlib.import_module(info.name)
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj.__module__ == module.__name__
            ):
                yield obj


def _nullable_bool(info) -> bool:
    args = get_args(info.annotation)
    return bool in args and type(None) in args


def _fields():
    by_name = {m.__name__: m for m in _schema_models()}
    for name, model in sorted(by_name.items()):
        if not name.endswith("Update"):
            continue
        response = by_name.get(name[: -len("Update")] + "Response")
        if response is None:
            continue
        for field, info in model.model_fields.items():
            if not _nullable_bool(info):
                continue
            mirror = response.model_fields.get(field)
            if mirror is not None and mirror.annotation is bool:
                yield model, field


FIELDS = list(_fields())


def test_the_walk_finds_the_fields():
    """An anchor, so a walk that silently stops matching fails here rather
    than passing with nothing to check."""
    found = {f"{model.__name__}.{field}" for model, field in FIELDS}
    assert {
        "MembershipTypeUpdate.is_active",
        "MembershipTypeUpdate.issues_card",
        "GroupUpdate.is_active",
        "ActivityPriceUpdate.is_visible",
        "ContactUpdate.is_primary",
    } <= found, found


@pytest.mark.parametrize(
    "model,field", FIELDS, ids=[f"{m.__name__}.{f}" for m, f in FIELDS]
)
def test_an_update_cannot_null_a_boolean_the_response_returns_as_bool(model, field):
    with pytest.raises(ValidationError) as exc:
        model.model_validate({field: None})
    assert any(err["loc"][0] == field for err in exc.value.errors())


@pytest.mark.parametrize(
    "model,field", FIELDS, ids=[f"{m.__name__}.{f}" for m, f in FIELDS]
)
def test_omitting_it_is_still_how_a_partial_update_leaves_it_alone(model, field):
    """The guard must not turn a partial update into a full one. Validators run
    only on values the body carries, so an absent field is untouched."""
    model.model_validate({})
