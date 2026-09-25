"""No input schema accepts whitespace where it refuses an empty string (#285).

`min_length=1` reads as "required" but counts spaces as content, so "   " went
through every such field and was stored as a blank name, title or code. These
tests walk every schema under `app.domains` rather than listing fields, so a
field added later with the old `Field(min_length=1)` fails here.
"""

import importlib
import pkgutil

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import app.domains
from app.core.schema_types import NonBlank, NonBlankText


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


def _rejects(adapter: TypeAdapter, value) -> bool:
    try:
        adapter.validate_python(value)
    except ValidationError:
        return True
    return False


def _is_required_text(adapter: TypeAdapter) -> bool:
    """Refuses an empty string but takes an ordinary one — what `min_length=1`
    was meant to express."""
    return _rejects(adapter, "") and not _rejects(adapter, "x")


# Every required text field of every schema.
FIELDS = [
    (model, name, adapter)
    for model in _schema_models()
    for name, info in model.model_fields.items()
    for adapter in [TypeAdapter(info.rebuild_annotation())]
    if _is_required_text(adapter)
]


def test_the_walk_finds_the_fields():
    found = {f"{model.__name__}.{name}" for model, name, _ in FIELDS}
    assert {
        "MemberCreate.first_name",
        "SpaceUpdate.name",
        "ActivityConsentCreate.content",
        "RoleCreate.name",
    } <= found


@pytest.mark.parametrize(
    "model,name,adapter", FIELDS, ids=[f"{m.__name__}.{n}" for m, n, _ in FIELDS]
)
def test_a_required_text_field_refuses_whitespace(model, name, adapter):
    for blank in ("   ", "\t", " \n "):
        assert _rejects(adapter, blank), f"{model.__name__}.{name} accepts {blank!r}"


# Optional fields of a partial update. A required field (a full-replace PUT,
# like the organization address) refuses null by its type already.
UPDATE_FIELDS = [
    (model, name, adapter)
    for model, name, adapter in FIELDS
    if model.__name__.endswith("Update") and not model.model_fields[name].is_required()
]


@pytest.mark.parametrize(
    "model,name,adapter",
    UPDATE_FIELDS,
    ids=[f"{m.__name__}.{n}" for m, n, _ in UPDATE_FIELDS],
)
def test_an_update_cannot_null_a_required_text_field(model, name, adapter):
    """Omitting the field keeps the stored value; an explicit null would reach
    a NOT NULL column. Validators run only on values the body carries."""
    with pytest.raises(ValidationError) as exc:
        model.model_validate({name: None})
    assert any(err["loc"][0] == name for err in exc.value.errors())
    model.model_validate({})


def test_non_blank_strips():
    assert TypeAdapter(NonBlank(10)).validate_python("  Aina \t") == "Aina"


def test_non_blank_text_keeps_the_text_as_typed():
    text = "  1. Indented clause\n"
    assert TypeAdapter(NonBlankText(100)).validate_python(text) == text
    assert _rejects(TypeAdapter(NonBlankText(100)), " \n\t ")
