from types import SimpleNamespace

from tester_spin.app import TesterSpinApp as App
from tester_spin.app_current import CurrentTesterSpinApp


def test_thumbnail_batch_yields_and_cancels_obsolete_provider():
    loaded, scheduled = [], []
    obj = SimpleNamespace(
        _thumbnail_generation=2,
        tree=SimpleNamespace(exists=lambda _: True, item=lambda *a, **k: None),
        _load_tree_thumbnail=lambda path: loaded.append(path) or "image",
        after=lambda delay, callback: scheduled.append(callback),
    )
    obj._fill_tree_thumbnails = lambda generation, pending: App._fill_tree_thumbnails(obj, generation, pending)
    pending = iter([(str(i), str(i)) for i in range(40)])
    App._fill_tree_thumbnails(obj, 1, pending)
    assert not loaded and not scheduled
    App._fill_tree_thumbnails(obj, 2, pending)
    assert 0 < len(loaded) <= 12
    assert len(scheduled) == 1
    obj._thumbnail_generation = 3
    scheduled[0]()
    assert len(loaded) <= 12


def test_thumbnail_cache_invalidates_changed_or_deleted_file(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"first")
    stat = path.stat()
    obj = SimpleNamespace(_thumb_images={str(path): "cached"},
                          _thumb_signatures={str(path): (stat.st_mtime_ns, stat.st_size)})
    assert App._cached_tree_thumbnail(obj, str(path)) == "cached"
    path.write_bytes(b"replacement")
    assert App._cached_tree_thumbnail(obj, str(path)) == ""
    assert not obj._thumb_images
    path.unlink()
    assert App._cached_tree_thumbnail(obj, str(path)) == ""


def test_filter_changes_only_the_view():
    calls = []
    obj = SimpleNamespace(_apply_current_sort=lambda: calls.append("sort"),
                          _update_count_summary=lambda: calls.append("counts"))
    CurrentTesterSpinApp._filter_changed(obj)
    assert calls == ["sort", "counts"]
