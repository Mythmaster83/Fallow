from larder.achievements import ProgressStore
from larder.store import open_store


def test_sample_pantry_loads_even_if_progress_created_the_file_first(tmp_path):
    db = tmp_path / "fallow.db"
    ProgressStore(db).load()  # the nav bar reads progress before any page opens the pantry
    assert db.exists()
    assert len(open_store(db).list_items()) > 0


def test_existing_pantry_is_not_reseeded(tmp_path):
    db = tmp_path / "fallow.db"
    store = open_store(db)
    first = store.list_items()[0]
    store.delete(first.id)
    assert first.id not in {i.id for i in open_store(db).list_items()}
