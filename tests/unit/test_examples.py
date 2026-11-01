"""The deployment recipes in examples/ install on the Python the package requires."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_example_images_meet_requires_python():
    requires = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    floor_match = re.fullmatch(r">=(\d+)\.(\d+)", requires)
    assert floor_match, requires
    floor = tuple(int(part) for part in floor_match.groups())
    images = re.findall(r"python:(\d+)\.(\d+)", (ROOT / "examples" / "README.md").read_text(encoding="utf-8"))

    assert images
    assert all((int(major), int(minor)) >= floor for major, minor in images), images
