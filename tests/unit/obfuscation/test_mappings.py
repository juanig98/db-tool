from __future__ import annotations

import pytest

from db_tool.config.models import Settings
from db_tool.obfuscation.mappings import MappingStore


@pytest.fixture
def store(tmp_path):
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
    )
    return MappingStore(settings)


def test_returns_same_fake_for_same_input(store):
    counter = iter(range(100))
    fn = lambda: next(counter)
    v1 = store.get_or_create("real@example.com", "email", fn)
    v2 = store.get_or_create("real@example.com", "email", fn)
    assert v1 == v2
    assert v1 == "0"  # first call


def test_different_values_different_fake(store):
    call_count = [0]
    def fn():
        call_count[0] += 1
        return f"fake_{call_count[0]}"

    v1 = store.get_or_create("alice@x.com", "email", fn)
    v2 = store.get_or_create("bob@x.com", "email", fn)
    assert v1 != v2


def test_persists_across_instances(tmp_path):
    settings = Settings(state_dir=tmp_path / "state", mappings_dir=tmp_path / "mappings")
    s1 = MappingStore(settings)
    val = s1.get_or_create("real@x.com", "email", lambda: "persistent_fake")

    s2 = MappingStore(settings)
    retrieved = s2.get_or_create("real@x.com", "email", lambda: "should_not_be_called")
    assert retrieved == val == "persistent_fake"


def test_different_faker_types_independent(store):
    # same real value, different faker_type → can produce different results
    v_email = store.get_or_create("real_value", "email", lambda: "fake@fake.com")
    v_name = store.get_or_create("real_value", "name", lambda: "Fake Name")
    # they are stored independently
    assert v_email == "fake@fake.com"
    assert v_name == "Fake Name"


def test_clear_all(tmp_path):
    settings = Settings(state_dir=tmp_path / "state", mappings_dir=tmp_path / "mappings")
    store = MappingStore(settings)
    store.get_or_create("a@x.com", "email", lambda: "fa")
    store.get_or_create("b@x.com", "email", lambda: "fb")
    count = store.clear_all()
    assert count == 2

    # After clear, next call should generate fresh values
    store2 = MappingStore(settings)
    v = store2.get_or_create("a@x.com", "email", lambda: "fresh")
    assert v == "fresh"
