import pytest

from db_tool.config.models import Settings
from db_tool.state.manager import StateManager


@pytest.fixture
def manager(tmp_path):
    settings = Settings(
        state_dir=tmp_path / "state",
        mappings_dir=tmp_path / "mappings",
    )
    return StateManager(settings)


def test_batch_not_done_initially(manager):
    assert not manager.is_batch_done("src", "tgt", "users", 0)


def test_mark_and_check_batch_done(manager):
    manager.mark_batch_done("src", "tgt", "users", 0)
    assert manager.is_batch_done("src", "tgt", "users", 0)
    assert not manager.is_batch_done("src", "tgt", "users", 1)


def test_collection_not_complete_initially(manager):
    assert not manager.is_collection_complete("src", "tgt", "users")


def test_mark_collection_complete(manager):
    manager.mark_collection_complete("src", "tgt", "users")
    assert manager.is_collection_complete("src", "tgt", "users")


def test_state_persists_across_instances(tmp_path):
    settings = Settings(state_dir=tmp_path / "state", mappings_dir=tmp_path / "mappings")
    m1 = StateManager(settings)
    m1.mark_batch_done("src", "tgt", "col", 5)

    m2 = StateManager(settings)
    assert m2.is_batch_done("src", "tgt", "col", 5)


def test_clear_collection(manager):
    manager.mark_batch_done("src", "tgt", "users", 0)
    manager.mark_collection_complete("src", "tgt", "users")
    manager.clear_collection("src", "tgt", "users")
    assert not manager.is_batch_done("src", "tgt", "users", 0)
    assert not manager.is_collection_complete("src", "tgt", "users")


def test_clear_all(manager):
    manager.mark_collection_complete("src", "tgt", "col1")
    manager.mark_collection_complete("src", "tgt", "col2")
    count = manager.clear_all()
    assert count == 2
    assert not manager.is_collection_complete("src", "tgt", "col1")


def test_key_is_deterministic():
    k1 = StateManager.make_key("a", "b", "c")
    k2 = StateManager.make_key("a", "b", "c")
    k3 = StateManager.make_key("a", "b", "d")
    assert k1 == k2
    assert k1 != k3


def test_different_targets_have_different_state(manager):
    manager.mark_collection_complete("src", "tgt1", "users")
    assert manager.is_collection_complete("src", "tgt1", "users")
    assert not manager.is_collection_complete("src", "tgt2", "users")
