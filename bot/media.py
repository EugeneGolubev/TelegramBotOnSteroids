"""Filesystem helpers for browsing and removing managed media entries."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from bot.config import get_settings


MEDIA_CATEGORIES = ("Movie", "TV", "Others")


class MediaError(RuntimeError):
    """Base error for safe media-folder operations."""


class MediaCategoryError(MediaError):
    """Raised when a category is not one of the configured media roots."""


class MediaFolderError(MediaError):
    """Raised when a configured media root cannot be read."""


class MediaItemError(MediaError):
    """Raised when a media entry cannot be safely removed."""


@dataclass(frozen=True)
class MediaEntry:
    """A direct child of one managed media folder."""

    name: str
    relative_path: str
    kind: str
    size_bytes: int


def _is_link(path: Path) -> bool:
    """Detect symbolic links and Windows junctions without following them."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _media_root(category: str) -> Path:
    if category not in MEDIA_CATEGORIES:
        raise MediaCategoryError("Unknown media category.")

    raw_path = get_settings().qb_category_paths.get(category)
    if not raw_path:
        raise MediaFolderError("The media folder is not configured.")

    try:
        return Path(raw_path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise MediaFolderError("The media folder path is invalid.") from exc


def _directory_size(path: Path) -> int:
    """Return recursive content size without following symbolic links."""
    total = 0
    try:
        entries = os.scandir(path)
    except OSError:
        return 0

    with entries:
        for entry in entries:
            try:
                child = Path(entry.path)
                if _is_link(child):
                    continue
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += _directory_size(child)
            except OSError:
                # A single inaccessible child should not hide the rest of a
                # media folder from the user.
                continue
    return total


def _entry_from_path(path: Path) -> MediaEntry:
    try:
        info = path.lstat()
    except OSError as exc:
        raise MediaItemError("A media entry could not be inspected.") from exc

    if _is_link(path):
        return MediaEntry(path.name, path.name, "symlink", info.st_size)
    if stat.S_ISDIR(info.st_mode):
        return MediaEntry(path.name, path.name, "folder", _directory_size(path))
    return MediaEntry(path.name, path.name, "file", info.st_size)


def list_media_entries(category: str) -> list[MediaEntry]:
    """List direct children of a configured media category."""
    root = _media_root(category)
    if not root.exists() or not root.is_dir():
        raise MediaFolderError("The media folder does not exist or is unavailable.")

    try:
        entries = [_entry_from_path(child) for child in root.iterdir()]
    except OSError as exc:
        raise MediaFolderError("The media folder could not be read.") from exc

    return sorted(entries, key=lambda entry: entry.name.casefold())


def _relative_child(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise MediaItemError("The selected media entry is invalid.")

    relative = Path(relative_path)
    if relative.is_absolute() or len(relative.parts) != 1:
        raise MediaItemError("Only direct media entries can be removed.")
    if relative.parts[0] in {".", ".."}:
        raise MediaItemError("The selected media entry is invalid.")

    candidate = root / relative
    if candidate.parent.resolve(strict=False) != root:
        raise MediaItemError("The selected media entry is outside the media folder.")

    # Resolve normal files/folders to protect against a renamed or replaced
    # entry escaping through a link. Links themselves are handled separately
    # and can only be unlinked, never followed.
    try:
        if not _is_link(candidate):
            candidate.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise MediaItemError("The selected media entry is outside the media folder.") from exc
    return candidate


def _make_writable(path: Path) -> None:
    """Clear a read-only bit so deletion also works on Windows mounts."""
    try:
        mode = path.stat(follow_symlinks=False).st_mode
        os.chmod(path, mode | stat.S_IWRITE)
    except OSError:
        # The original deletion error is more useful to the caller.
        return


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        _make_writable(path)
        path.unlink()


def _remove_link(path: Path) -> None:
    """Remove a link itself, including a Windows directory junction."""
    if path.is_symlink():
        _unlink(path)
        return
    try:
        path.rmdir()
    except PermissionError:
        _make_writable(path)
        path.rmdir()


def _remove_tree(path: Path) -> None:
    """Recursively remove a tree without traversing symbolic links."""
    try:
        entries = os.scandir(path)
    except PermissionError:
        _make_writable(path)
        entries = os.scandir(path)

    with entries:
        for entry in entries:
            child = Path(entry.path)
            try:
                if _is_link(child):
                    _remove_link(child)
                elif entry.is_dir(follow_symlinks=False):
                    _remove_tree(child)
                else:
                    _unlink(child)
            except FileNotFoundError:
                continue

    try:
        path.rmdir()
    except PermissionError:
        _make_writable(path)
        path.rmdir()


def delete_media_entry(category: str, relative_path: str) -> MediaEntry:
    """Delete a file, link, or folder below one configured media root.

    Folders are removed recursively. The selected root itself can never be
    selected because ``relative_path`` must identify one direct child.
    """
    root = _media_root(category)
    if not root.exists() or not root.is_dir():
        raise MediaFolderError("The media folder does not exist or is unavailable.")

    candidate = _relative_child(root, relative_path)
    try:
        entry = _entry_from_path(candidate)
    except MediaItemError:
        raise
    except OSError as exc:
        raise MediaItemError("The selected media entry could not be inspected.") from exc

    try:
        if entry.kind == "folder":
            _remove_tree(candidate)
        elif entry.kind == "symlink":
            _remove_link(candidate)
        else:
            _unlink(candidate)
    except FileNotFoundError as exc:
        raise MediaItemError("The selected media entry no longer exists.") from exc
    except PermissionError as exc:
        raise MediaItemError("The selected media entry could not be removed due to permissions or a file lock.") from exc
    except OSError as exc:
        raise MediaItemError("The selected media entry could not be removed.") from exc

    return entry


def format_bytes(value: int) -> str:
    """Format a byte count for a compact Telegram card."""
    size = max(0, float(value))
    units = ("B", "KiB", "MB", "GB", "TiB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size:.0f} B"
        size /= 1024
    return "0 B"
