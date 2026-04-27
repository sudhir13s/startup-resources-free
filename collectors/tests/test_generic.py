"""GenericCollector + catalog.yaml registry loading."""

from __future__ import annotations

from collectors import REGISTRY
from collectors.generic import GenericCollector, make_generic, make_many


def test_make_generic_returns_distinct_classes():
    a = make_generic(
        provider_id="aws-free",
        provider_name="AWS",
        category="cloud",
        source_url="https://aws.amazon.com/free/",
    )
    b = make_generic(
        provider_id="gcp-free",
        provider_name="GCP",
        category="cloud",
        source_url="https://cloud.google.com/free",
    )
    # Different classes -> the BaseCollector class-attribute lookup
    # gives the right metadata per registry row (no aliasing).
    assert type(a) is not type(b)
    assert a.provider_id == "aws-free"
    assert b.provider_id == "gcp-free"
    assert a.source_url != b.source_url


def test_generic_extract_fields_returns_seed_stub():
    c = make_generic(
        provider_id="x",
        provider_name="X",
        category="cloud",
        source_url="https://x.test/",
    )
    out = c.extract_fields("<html>anything</html>")
    assert out["id"] == "x"
    assert out["name"] == "X"
    assert out["category"] == "cloud"
    assert out["parse_confidence"] == "medium"


def test_generic_collector_class_subclass():
    c = make_generic(
        provider_id="a",
        provider_name="A",
        category="cloud",
        source_url="https://a.test/",
    )
    assert isinstance(c, GenericCollector)


def test_make_many_handles_multiple_rows():
    rows = [
        {
            "provider_id": "a",
            "provider_name": "A",
            "category": "cloud",
            "source_url": "https://a.test/",
        },
        {
            "provider_id": "b",
            "provider_name": "B",
            "category": "gpu",
            "source_url": "https://b.test/",
        },
    ]
    out = make_many(rows)
    assert len(out) == 2
    assert out[0].provider_id == "a"
    assert out[1].category == "gpu"


# ---------- REGISTRY surface ----------


def test_registry_loads_yaml_catalog():
    """Adding a row to catalog.yaml should land in REGISTRY automatically."""
    ids = {c.provider_id for c in REGISTRY.all()}
    # Hand-written collectors still present.
    assert {"vercel", "render", "groq"}.issubset(ids)
    # YAML rows registered.
    assert {"aws-free", "gcp-free", "azure-free", "supabase", "neon"}.issubset(ids)


def test_registry_does_not_double_register_hand_written():
    """Hand-written collectors must NOT also appear via the YAML catalog."""
    counts: dict[str, int] = {}
    for c in REGISTRY.all():
        counts[c.provider_id] = counts.get(c.provider_id, 0) + 1
    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert duplicates == {}, f"duplicate registrations: {duplicates}"


def test_registry_categories_match_provider_schema_enum():
    """Every registered category must be in the canonical enum so the
    seed-merge / DB layer doesn't reject records on insert."""
    valid = {
        "cloud",
        "hosting",  # legacy alias still OK
        "gpu",
        "ai-api",
        "database",
        "storage",
        "auth",
        "observability",
        "domain",
        "startup-credit",
        "grant",
        "accelerator",
        "perk",
        "oss",
        "learning",
    }
    for c in REGISTRY.all():
        assert c.category in valid, (
            f"unknown category {c.category!r} on {c.provider_id!r}"
        )


def test_registry_source_urls_are_https():
    for c in REGISTRY.all():
        assert c.source_url.startswith(("http://", "https://")), c.provider_id
