"""``replace_file`` / ``remove_files`` — the ordering that keeps a row and its
file consistent whichever step fails (#259)."""

import pytest

from app.core.file_replace import remove_files, replace_file


def _files(storage_dir):
    return sorted(p.name for p in storage_dir.iterdir())


class TestReplaceFile:
    def test_writes_the_file_and_names_it(self, tmp_path):
        seen = []
        name = replace_file(tmp_path, "photo", "png", b"new", seen.append)

        assert name == "photo.png"
        assert seen == ["photo.png"]
        assert (tmp_path / "photo.png").read_bytes() == b"new"

    def test_the_previous_extension_is_removed_after_the_commit(self, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"old")
        during = []

        def commit(name):
            during.append(_files(tmp_path))

        replace_file(tmp_path, "photo", "png", b"new", commit)

        # At commit time the old file was still there, beside the temporary.
        assert "photo.jpg" in during[0]
        assert _files(tmp_path) == ["photo.png"]

    def test_a_failed_commit_keeps_the_old_file_and_drops_the_new_one(self, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"old")

        def commit(name):
            raise RuntimeError("connection lost")

        with pytest.raises(RuntimeError):
            replace_file(tmp_path, "photo", "png", b"new", commit)

        assert _files(tmp_path) == ["photo.jpg"]
        assert (tmp_path / "photo.jpg").read_bytes() == b"old"

    def test_a_failed_commit_on_the_same_name_leaves_the_old_content(self, tmp_path):
        """Replacing photo.png with photo.png used to overwrite in place; now
        the old bytes survive a failed commit."""
        (tmp_path / "photo.png").write_bytes(b"old")

        def commit(name):
            raise RuntimeError("connection lost")

        with pytest.raises(RuntimeError):
            replace_file(tmp_path, "photo", "png", b"new", commit)

        assert _files(tmp_path) == ["photo.png"]
        assert (tmp_path / "photo.png").read_bytes() == b"old"

    def test_a_stale_temporary_is_swept(self, tmp_path):
        (tmp_path / ".photo.deadbeef.tmp").write_bytes(b"crashed")

        replace_file(tmp_path, "photo", "png", b"new", lambda name: None)

        assert _files(tmp_path) == ["photo.png"]

    def test_creates_the_directory(self, tmp_path):
        target = tmp_path / "members" / "7"
        replace_file(target, "photo", "png", b"new", lambda name: None)
        assert (target / "photo.png").exists()


class TestRemoveFiles:
    def test_removes_every_file_on_the_stem_and_nothing_else(self, tmp_path):
        (tmp_path / "photo.png").write_bytes(b"")
        (tmp_path / "photo.jpg").write_bytes(b"")
        (tmp_path / ".photo.abc.tmp").write_bytes(b"")
        (tmp_path / "other.png").write_bytes(b"")

        remove_files(tmp_path, "photo")

        assert _files(tmp_path) == ["other.png"]

    def test_keep_is_left_alone(self, tmp_path):
        (tmp_path / "photo.png").write_bytes(b"")
        (tmp_path / "photo.jpg").write_bytes(b"")

        remove_files(tmp_path, "photo", keep=tmp_path / "photo.png")

        assert _files(tmp_path) == ["photo.png"]
