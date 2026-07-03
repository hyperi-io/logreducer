"""Integrity checks for the committed real-log corpora (tests/testdata/).

Cheap, server-free guards: every manifest entry has its file, every file has a
manifest entry, and content hashes match - catching a rebuilt slice committed
without its manifest (or vice versa) before it ships.
"""

import gzip
import hashlib
import json
from pathlib import Path

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


def _manifest() -> list[dict]:
    return json.loads((TESTDATA / "manifest.json").read_text())


def test_every_manifest_entry_has_matching_file():
    for entry in _manifest():
        path = TESTDATA / f"{entry['name']}.log.gz"
        assert path.exists(), f"manifest lists {entry['name']} but {path.name} is missing"


def test_every_corpus_file_is_in_manifest():
    names = {e["name"] for e in _manifest()}
    on_disk = {p.name.removesuffix(".log.gz") for p in TESTDATA.glob("*.log.gz")}
    assert on_disk == names, f"manifest/disk mismatch: {on_disk.symmetric_difference(names)}"


def test_sha256_and_line_counts_match_manifest():
    for entry in _manifest():
        path = TESTDATA / f"{entry['name']}.log.gz"
        hasher = hashlib.sha256()
        lines = 0
        with gzip.open(path, "rb") as fh:
            for raw in fh:
                hasher.update(raw)
                lines += 1
        assert hasher.hexdigest() == entry["sha256"], f"{entry['name']}: content drifted from manifest sha256"
        assert lines == entry["lines"], f"{entry['name']}: {lines} lines vs manifest {entry['lines']}"
