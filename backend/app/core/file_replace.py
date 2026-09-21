"""Replace a stored file whose name a database row points at.

Three handlers — member photo, club logo, activity cover — keep one file per
owner under a fixed stem (``photo.*``, ``logo.*``, ``cover.*``) and store its
URL on a row. Each used to delete the old file, write the new one, then commit
the row. A commit that failed rolled the row back to the old URL, whose file
had already been deleted two steps earlier (#259).

The order here is the one that leaves something valid whatever fails:

1. Write the new content to a temporary name beside the final one.
2. Commit the row naming the final file.
3. Move the temporary file into place — atomic, and an overwrite when the
   new file keeps the old name — then delete every other file on the stem.

A failed commit removes only the temporary file; the old file is still there
for the row to point at. A failed move after a successful commit is the one
window left open, and it is the same millisecond the previous code had.

Deleting has the same rule in the other direction: the row is cleared and
committed first, and the files go afterwards. The delete handlers used to
unlink first, so a failed commit left a row naming a file that was gone.
"""

import glob
import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4


def replace_file(
    storage_dir: Path,
    stem: str,
    ext: str,
    content: bytes,
    commit: Callable[[str], None],
) -> str:
    """Store ``content`` as ``<stem>.<ext>`` in ``storage_dir`` and return that name.

    ``commit`` is called with the final file name and must persist the row that
    references it — typically set the URL column and ``db.commit()``. Whatever
    it raises propagates after the temporary file has been removed.
    """
    storage_dir.mkdir(parents=True, exist_ok=True)
    final_name = f"{stem}.{ext}"
    final_path = storage_dir / final_name
    tmp_path = storage_dir / f".{stem}.{uuid4().hex}.tmp"

    with open(tmp_path, "wb") as f:
        f.write(content)
    try:
        commit(final_name)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    os.replace(tmp_path, final_path)
    remove_files(storage_dir, stem, keep=final_path)
    return final_name


def remove_files(storage_dir: Path, stem: str, keep: Path | None = None) -> None:
    """Delete every file on ``stem`` except ``keep``: the previous extension's
    file, and any temporary left by a process that died between its write and
    its commit. Call it after the row no longer references what is removed."""
    for old in glob.glob(str(storage_dir / f"{stem}.*")) + glob.glob(
        str(storage_dir / f".{stem}.*.tmp")
    ):
        if Path(old) != keep:
            Path(old).unlink(missing_ok=True)
