import stat

import pytest

import bot.media as media
from bot.media import MediaEntry, MediaError, delete_media_entry, format_bytes, list_media_entries


@pytest.fixture
def movie_root(tmp_path, monkeypatch):
    root = tmp_path / "Movie"
    root.mkdir()
    monkeypatch.setenv("QB_CATEGORY_MOVIE_PATH", str(root))
    monkeypatch.setenv("QB_CATEGORY_TV_PATH", str(tmp_path / "TV"))
    monkeypatch.setenv("QB_CATEGORY_OTHERS_PATH", str(tmp_path / "Others"))
    return root


def test_list_media_entries_reports_files_folders_and_recursive_sizes(movie_root):
    (movie_root / "z-last.mkv").write_bytes(b"1234")
    series = movie_root / "Series"
    (series / "Season 1").mkdir(parents=True)
    (series / "Season 1" / "episode.mkv").write_bytes(b"123456")

    entries = list_media_entries("Movie")

    assert [entry.name for entry in entries] == ["Series", "z-last.mkv"]
    assert entries[0] == MediaEntry("Series", "Series", "folder", 6)
    assert entries[1] == MediaEntry("z-last.mkv", "z-last.mkv", "file", 4)


def test_list_media_entries_rejects_unknown_category(movie_root):
    with pytest.raises(media.MediaCategoryError):
        list_media_entries("Music")


def test_list_media_entries_reports_missing_root(tmp_path, monkeypatch):
    monkeypatch.setenv("QB_CATEGORY_MOVIE_PATH", str(tmp_path / "missing"))

    with pytest.raises(media.MediaError, match="does not exist"):
        list_media_entries("Movie")


def test_delete_media_entry_removes_file(movie_root):
    target = movie_root / "unwanted.mkv"
    target.write_bytes(b"content")

    deleted = delete_media_entry("Movie", "unwanted.mkv")

    assert deleted.kind == "file"
    assert not target.exists()


def test_delete_media_entry_recursively_removes_non_empty_folder(movie_root):
    series = movie_root / "Series"
    (series / "Season 1").mkdir(parents=True)
    (series / "Season 1" / "episode.mkv").write_bytes(b"episode")
    (series / "poster.jpg").write_bytes(b"poster")

    deleted = delete_media_entry("Movie", "Series")

    assert deleted.kind == "folder"
    assert not series.exists()


def test_delete_media_entry_never_deletes_outside_root(movie_root, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")

    with pytest.raises(media.MediaError):
        delete_media_entry("Movie", "../outside.txt")

    assert outside.exists()


def test_delete_media_entry_unlinks_symlink_without_following_target(movie_root, tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    (target / "keep.mkv").write_bytes(b"keep")
    link = movie_root / "linked-folder"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform")

    deleted = delete_media_entry("Movie", "linked-folder")

    assert deleted.kind == "symlink"
    assert not link.exists()
    assert (target / "keep.mkv").exists()


def test_delete_media_entry_handles_read_only_file(movie_root):
    target = movie_root / "readonly.mkv"
    target.write_bytes(b"content")
    original_mode = target.stat().st_mode
    try:
        target.chmod(stat.S_IREAD)
        delete_media_entry("Movie", "readonly.mkv")
        assert not target.exists()
    finally:
        if target.exists():
            target.chmod(original_mode)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (1024, "1.0 KiB"),
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
    ],
)
def test_format_bytes(value, expected):
    assert format_bytes(value) == expected
