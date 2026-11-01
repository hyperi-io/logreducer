#!/usr/bin/env python3
"""Build ``template_mining_quiet_golden.json.gz`` with the real drain3 0.9.11.

The reducer mines only the quiet lines (those that name no CRITICAL, FATAL or ERROR
level), so this golden holds what drain3 produces over each corpus's quiet lines alone,
under the five miner configurations of ``template_mining_golden.json.gz``. drain3 is the
frozen reference here and is never a dependency of logreducer. Run it offline, from the
repository root, in an isolated environment:

    uvx --python 3.14 --with drain3==0.9.11 python -I tests/testdata/build_quiet_golden.py

Before it writes anything it replays every corpus over ALL lines and checks the result
against ``template_mining_golden.json.gz``, so a drain3 setup that drifts from the one
that golden came from fails here and not in the test.
"""

import gzip
import hashlib
import json
import sys
from pathlib import Path

from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

TESTDATA = Path(__file__).resolve().parent
GOLDEN = TESTDATA / "template_mining_golden.json.gz"
OUT = TESTDATA / "template_mining_quiet_golden.json.gz"

# logreducer's BigDialConfig defaults for the fields the five configurations override.
DEFAULTS = {"max_clusters": 10_000, "drain_similarity": 0.4, "typed_masking": False}
LEVELS = ("CRITICAL", "FATAL", "ERROR")


def is_severe(line: str) -> bool:
    upper = line.upper()
    return any(level in upper for level in LEVELS)


def read_lines(name: str, limit: int) -> list[str]:
    """The first ``limit`` raw lines of a corpus, stripped and with blanks skipped."""
    lines = []
    with gzip.open(TESTDATA / f"{name}.log.gz", "rt", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def typed_masks() -> list[MaskingInstruction]:
    start = r"(?:(?<=[^A-Za-z0-9])|^)"
    end = r"(?:(?=[^A-Za-z0-9])|$)"
    hex4 = r"[0-9A-Fa-f]{1,4}"
    shapes = [
        (r"\d{1,3}(?:\.\d{1,3}){3}", "IP"),
        (r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}", "UUID"),
        (r"[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}", "MAC"),
        (
            rf"(?:{hex4}:){{7}}{hex4}"
            rf"|(?:{hex4}:){{1,6}}:(?:{hex4}(?::{hex4}){{0,5}})?"
            rf"|::(?:{hex4}(?::{hex4}){{0,6}})?",
            "IPV6",
        ),
        (r"0[xX][0-9A-Fa-f]{8,}|(?=\d*[A-Fa-f])[0-9A-Fa-f]{8,}", "HEX"),
        (r"[-+]?\d+", "NUM"),
    ]
    return [MaskingInstruction(f"{start}(?:{pattern}){end}", name) for pattern, name in shapes]


def mine(lines: list[str], options: dict) -> tuple[list[int], list[list], int]:
    """Cluster id per line, the [template, count] of every cluster ever created, and live clusters."""
    settings = {**DEFAULTS, **options}
    config = TemplateMinerConfig()
    config.drain_sim_th = settings["drain_similarity"]
    config.drain_depth = 4
    config.drain_max_clusters = settings["max_clusters"]
    config.masking_instructions = typed_masks() if settings["typed_masking"] else []
    miner = TemplateMiner(config=config)

    ids = []
    first_template: dict[int, str] = {}
    counts: dict[int, int] = {}
    for line in lines:
        result = miner.add_log_message(line)
        cluster_id = result["cluster_id"]
        ids.append(cluster_id)
        if cluster_id not in counts:
            first_template[cluster_id] = result["template_mined"]
        counts[cluster_id] = counts.get(cluster_id, 0) + 1

    patterns = []
    for cluster_id, count in counts.items():
        live = miner.drain.id_to_cluster.get(cluster_id)
        template = live.get_template() if live is not None else first_template[cluster_id]
        patterns.append([template, count])
    return ids, patterns, len(miner.drain.id_to_cluster)


def main() -> int:
    golden = json.loads(gzip.decompress(GOLDEN.read_bytes()))
    limit = golden["limit"]
    results: dict[str, dict] = {}
    for name in golden["results"]:
        lines = read_lines(name, limit)
        quiet = [line for line in lines if not is_severe(line)]
        results[name] = {}
        for label, options in golden["configs"].items():
            expected = golden["results"][name][label]
            ids, patterns, live = mine(lines, options)
            digest = hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()
            if digest != expected["assignments_sha256"] or live != expected["live_clusters"]:
                sys.exit(f"drain3 setup does not reproduce the golden for {name}/{label}")
            if sorted(patterns) != sorted(expected["patterns"]):
                sys.exit(f"drain3 patterns differ from the golden for {name}/{label}")

            _, quiet_patterns, quiet_live = mine(quiet, options)
            results[name][label] = {
                "lines": len(quiet),
                "live_clusters": quiet_live,
                "patterns": sorted(quiet_patterns),
            }

    payload = {"producer": "drain3 0.9.11", "limit": limit, "results": results}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    with OUT.open("wb") as handle, gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as gz:
        gz.write(raw)
    print(f"wrote {OUT.name}: {sum(len(v) for v in results.values())} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
