#!/usr/bin/env python3
"""Build the committed real-log test corpora for logreducer's integration tests.

Downloads REAL public log datasets (never synthetic), deterministically cleanses
PII, truncates to a committable slice, gzips each, and writes ``manifest.json``.
Run by a maintainer offline; the gzipped slices + manifest are committed and CI
uses them directly (no network in CI).

    python tests/testdata/build.py            # build any missing datasets
    python tests/testdata/build.py --force     # re-download and rebuild all

Design notes:
* RAW lines are preserved (only PII tokens are rewritten) - converting to JSON
  would escape/normalise away the exact messiness we want to test (odd bytes,
  long lines, multi-line records).
* Cleansing is a DETERMINISTIC map (same real value -> same fake value), so the
  repetition structure survives and the reducer still finds the patterns.
* Slices are the FIRST N lines (contiguous, reproducible, temporal-order intact).
* Datasets are redistributed under their own licences (see manifest + NOTICE);
  LogHub sets come from the Zenodo CC-BY-4.0 records, not the download-only CFDR
  originals.

Stdlib only - no third-party deps.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import ipaddress
import json
import re
import sys
import tarfile
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
USER_AGENT = "logreducer-testdata-builder/1.0 (https://github.com/hyperi-io/logreducer)"

# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------
# archive: how to open the download - "tar" | "zip" | "gz" | "raw"
# member_hint: filename (or suffix) of the log inside an archive; falls back to
#   the largest ``*.log`` (or largest file) if not found.
# cleanse: "full" (IP/IPv6/email/MAC + extras) | "light" (extras only) | "none"
# target_lines: first-N physical lines kept in the committed slice.
DATASETS: list[dict] = [
    {
        "name": "loghub_linux",
        "domain": "os-syslog",
        "format": "syslog: 'Mmm _D HH:MM:SS host daemon[pid]: msg'",
        "url": "https://zenodo.org/records/8196385/files/Linux.tar.gz",
        "archive": "tar",
        "member_hint": "Linux.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "target_lines": 25000,
    },
    {
        "name": "loghub_mac",
        "domain": "os-kernel",
        "format": "syslog, very high template diversity (IPv6/MAC/hex)",
        "url": "https://zenodo.org/records/8196385/files/Mac.tar.gz",
        "archive": "tar",
        "member_hint": "Mac.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "extra_sub": [
            (r"[A-Za-z0-9-]*MacBook-Pro", "host1"),
            (r"calvisitor-[0-9-]+", "host2"),
            (r"authorMacBook-Pro", "host1"),
        ],
        "target_lines": 40000,
    },
    {
        "name": "loghub_openssh",
        "domain": "security-auth",
        "format": "syslog sshd auth, repetitive failed-login (brute force)",
        "url": "https://zenodo.org/records/8196385/files/SSH.tar.gz",
        "archive": "tar",
        "member_hint": "OpenSSH.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "target_lines": 50000,
    },
    {
        "name": "loghub_openstack",
        "domain": "cloud-infra",
        "format": "nova: long lines, [req-UUID user tenant] request context",
        "url": "https://zenodo.org/records/8196385/files/OpenStack.tar.gz",
        "archive": "tar",
        "member_hint": "OpenStack.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "target_lines": 30000,
    },
    {
        "name": "loghub_hadoop",
        "domain": "bigdata",
        "format": "mapreduce, ',mmm' timestamps, multi-line Java stack traces",
        "url": "https://zenodo.org/records/8196385/files/Hadoop.zip",
        "archive": "zip",
        "concat_all": True,
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "extra_sub": [
            (r"MININT-[A-Z0-9]+\.fareast\.corp\.microsoft\.com", "host1.example.com"),
            (r"msra-sa-\d+", "host2"),
            (r"\bmsrabi\b", "user1"),
        ],
        "target_lines": 40000,
    },
    {
        "name": "loghub_proxifier",
        "domain": "desktop-network",
        "format": "bracketed '[MM.DD HH:MM:SS] program - host:port', ultra-regular",
        "url": "https://zenodo.org/records/8196385/files/Proxifier.tar.gz",
        "archive": "tar",
        "member_hint": "Proxifier.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "full",
        "target_lines": 21000,
    },
    {
        "name": "loghub_healthapp",
        "domain": "mobile-app",
        "format": "pipe-delimited 'YYYYMMDD-HH:MM:SS:mmm|Component|pid|msg'",
        "url": "https://zenodo.org/records/8196385/files/HealthApp.tar.gz",
        "archive": "tar",
        "member_hint": "HealthApp.log",
        "license": "CC-BY-4.0",
        "citation": "LogHub (Zhu et al., ISSRE 2023), Zenodo 10.5281/zenodo.8196385",
        "cleanse": "light",
        "target_lines": 40000,
    },
    {
        "name": "ita_calgary_http",
        "domain": "web-access",
        "format": "1990s web access log (pre-anonymised host ids)",
        "url": "https://ita.ee.lbl.gov/traces/calgary_access_log.gz",
        "archive": "gz",
        "license": "Internet Traffic Archive - freely redistributable",
        "citation": "The Internet Traffic Archive (ita.ee.lbl.gov), Calgary-HTTP",
        "cleanse": "none",
        "target_lines": 50000,
    },
    {
        "name": "ita_nasa_http",
        "domain": "web-access",
        "format": "1995 NASA Apache access log (real hosts/IPs)",
        "url": "https://ita.ee.lbl.gov/traces/NASA_access_log_Jul95.gz",
        "archive": "gz",
        "license": "Internet Traffic Archive - freely redistributable",
        "citation": "The Internet Traffic Archive (ita.ee.lbl.gov), NASA-HTTP",
        "cleanse": "full",
        "cleanse_hosts": True,
        "target_lines": 50000,
    },
    {
        "name": "elastic_nginx_json",
        "domain": "structured-json",
        "format": "one JSON object per line (nginx)",
        "url": "https://raw.githubusercontent.com/elastic/examples/master/Common%20Data%20Formats/nginx_json_logs/nginx_json_logs",
        "archive": "raw",
        "license": "Apache-2.0",
        "citation": "elastic/examples (Apache-2.0)",
        "cleanse": "full",
        "target_lines": 51000,
    },
    {
        "name": "secrepo_auth",
        "domain": "security-auth",
        "format": "linux auth.log, SSH failed logins",
        "url": "https://www.secrepo.com/auth.log/auth.log.gz",
        "archive": "gz",
        "license": "CC-BY-4.0",
        "citation": "Security Repo by Mike Sconzo (secrepo.com), CC-BY-4.0",
        "cleanse": "full",
        "target_lines": 50000,
    },
]

# ---------------------------------------------------------------------------
# Deterministic PII cleansing
# ---------------------------------------------------------------------------

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Candidate hex-colon runs, validated with ipaddress in the callback. A loose
# regex + strict parse catches COMPRESSED forms (2603:1036::2) that a
# groups-count regex misses, while the parse rejects clock times (09:00:55).
# The lookarounds stop mid-word matches (C++ "Type2::prePCIWake" scope tokens).
_IPV6_CANDIDATE = re.compile(r"(?<![\w.:])[0-9A-Fa-f:]{3,45}(?![\w.:])")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Colon AND dash separated MACs (Mac system logs use 84-41-67-32-db-e1).
_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}\b")
# A leading FQDN host token (start of a web-access-log line): word.word.tld<space>.
_LEADING_HOST = re.compile(r"^([A-Za-z][A-Za-z0-9.-]*\.[A-Za-z]{2,})(\s)")


class Cleanser:
    """Map each distinct real PII token to a stable synthetic one.

    Same input -> same output (a per-run dict), so a line's identifiers stay
    consistent across the file and the reducer still sees the real repetition.
    """

    def __init__(self) -> None:
        self._ip: dict[str, str] = {}
        self._ip6: dict[str, str] = {}
        self._email: dict[str, str] = {}
        self._mac: dict[str, str] = {}
        self._host: dict[str, str] = {}

    def _ipv4(self, m: re.Match[str]) -> str:
        real = m.group(0)
        # Skip obvious non-addresses (version strings caught by the loose regex).
        octets = real.split(".")
        if any(int(o) > 255 for o in octets):
            return real
        if real not in self._ip:
            n = len(self._ip) + 1
            self._ip[real] = f"10.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"
        return self._ip[real]

    def _ipv6(self, m: re.Match[str]) -> str:
        real = m.group(0)
        # Strict validation: only rewrite genuine IPv6 addresses. This rejects
        # clock times (09:00:55 - not parseable), bare '::' noise, and anything
        # the loose candidate regex over-matched.
        if ":" not in real:
            return real
        try:
            if not isinstance(ipaddress.ip_address(real), ipaddress.IPv6Address):
                return real
        except ValueError:
            return real
        if real not in self._ip6:
            self._ip6[real] = f"2001:db8::{len(self._ip6) + 1:x}"
        return self._ip6[real]

    def _email_sub(self, m: re.Match[str]) -> str:
        real = m.group(0)
        if real not in self._email:
            self._email[real] = f"user{len(self._email) + 1}@example.com"
        return self._email[real]

    def _mac_sub(self, m: re.Match[str]) -> str:
        real = m.group(0)
        if real not in self._mac:
            n = len(self._mac) + 1
            self._mac[real] = f"02:00:00:{(n >> 16) & 255:02x}:{(n >> 8) & 255:02x}:{n & 255:02x}"
        return self._mac[real]

    def _host_sub(self, m: re.Match[str]) -> str:
        real = m.group(1)
        if real not in self._host:
            self._host[real] = f"host{len(self._host) + 1}.example.com"
        return self._host[real] + m.group(2)

    def clean(self, line: str, extra: list[tuple[re.Pattern[str], str]], hosts: bool = False) -> str:
        # A leading FQDN host token (web-access logs) -> hostN.example.com. Done
        # first, anchored, so it never touches domains inside request URLs.
        if hosts:
            line = _LEADING_HOST.sub(self._host_sub, line, count=1)
        # MAC before IPv6 (both use hex/colon shapes); IPv4/email are unambiguous.
        line = _MAC.sub(self._mac_sub, line)
        line = _IPV6_CANDIDATE.sub(self._ipv6, line)
        line = _IPV4.sub(self._ipv4, line)
        line = _EMAIL.sub(self._email_sub, line)
        for pattern, repl in extra:
            line = pattern.sub(repl, line)
        return line


# ---------------------------------------------------------------------------
# Download + extract
# ---------------------------------------------------------------------------


def _download(url: str, dest: Path) -> None:
    """Download to a temp name and rename on success (atomic).

    A dropped connection must not leave a truncated blob that the next run
    treats as a valid cache hit.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - trusted dataset hosts
    print(f"  downloading {url}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(partial, "wb") as out:  # noqa: S310 - trusted hosts
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)


def _raw_lines(spec: dict, blob: Path) -> Iterator[str]:
    """Yield decoded text lines from the downloaded blob per its archive type."""
    archive = spec["archive"]
    if archive == "tar":
        with tarfile.open(blob, "r:gz") as tf:
            member = _pick_tar_member(tf, spec.get("member_hint"))
            fh = tf.extractfile(member)
            assert fh is not None
            yield from _decode(fh)
    elif archive == "zip":
        with zipfile.ZipFile(blob) as zf:
            if spec.get("concat_all"):
                # Datasets split across many per-container log files (Hadoop):
                # concatenate every .log member to get a meaningful slice.
                members = sorted(i.filename for i in zf.infolist() if not i.is_dir() and i.filename.endswith(".log"))
                for member in members:
                    with zf.open(member) as fh:
                        yield from _decode(fh)
            else:
                name = _pick_zip_member(zf, spec.get("member_hint"))
                with zf.open(name) as fh:
                    yield from _decode(fh)
    elif archive == "gz":
        with gzip.open(blob, "rb") as fh:
            yield from _decode(fh)
    else:  # raw
        with open(blob, "rb") as fh:
            yield from _decode(fh)


def _decode(fh: io.BufferedReader | object) -> Iterator[str]:
    for raw in fh:  # type: ignore[union-attr]
        # errors="replace": keep the line even if the source has bad bytes -
        # that messiness is exactly what we want the reducer to survive.
        yield raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")


def _pick_tar_member(tf: tarfile.TarFile, hint: str | None) -> tarfile.TarInfo:
    files = [m for m in tf.getmembers() if m.isfile()]
    if hint:
        for m in files:
            if m.name.endswith(hint):
                return m
    logs = [m for m in files if m.name.endswith(".log")] or files
    return max(logs, key=lambda m: m.size)


def _pick_zip_member(zf: zipfile.ZipFile, hint: str | None) -> str:
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if hint:
        for i in infos:
            if i.filename.endswith(hint):
                return i.filename
    logs = [i for i in infos if i.filename.endswith(".log")] or infos
    return max(logs, key=lambda i: i.file_size).filename


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _build_one(spec: dict, force: bool) -> dict:
    name = spec["name"]
    out_path = HERE / f"{name}.log.gz"
    blob = CACHE / (name + "." + spec["archive"])

    if not blob.exists() or force:
        _download(spec["url"], blob)

    cleanse = spec["cleanse"]
    extra = [(re.compile(p), r) for p, r in spec.get("extra_sub", [])]
    hosts = spec.get("cleanse_hosts", False)
    cleanser = Cleanser()
    target = spec["target_lines"]

    # Write to a temp name and rename on success, so a mid-build failure never
    # clobbers a previously good committed slice (leaving file and manifest
    # silently disagreeing).
    kept = 0
    hasher = hashlib.sha256()
    tmp_path = out_path.with_suffix(".gz.tmp")
    try:
        with gzip.open(tmp_path, "wb", compresslevel=9) as gz:
            for line in _slice(_raw_lines(spec, blob), target):
                if cleanse == "full":
                    line = cleanser.clean(line, extra, hosts=hosts)
                elif cleanse == "light":
                    for pattern, repl in extra:
                        line = pattern.sub(repl, line)
                data = (line + "\n").encode("utf-8")
                gz.write(data)
                hasher.update(data)
                kept += 1
        tmp_path.replace(out_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    size = out_path.stat().st_size
    print(f"  {name}: {kept} lines -> {out_path.name} ({size / 1024:.0f} KiB)")
    return {
        "name": name,
        "domain": spec["domain"],
        "format": spec["format"],
        "source_url": spec["url"],
        "license": spec["license"],
        "citation": spec["citation"],
        "cleansed": cleanse,
        "lines": kept,
        "bytes_gz": size,
        "sha256": hasher.hexdigest(),
    }


def _slice(lines: Iterable[str], n: int) -> Iterator[str]:
    for i, line in enumerate(lines):
        if i >= n:
            return
        yield line


def main() -> int:
    parser = argparse.ArgumentParser(description="Build logreducer real-log test corpora")
    parser.add_argument("--force", action="store_true", help="re-download and rebuild all")
    parser.add_argument("--only", nargs="*", help="build only these dataset names")
    args = parser.parse_args()

    specs = DATASETS
    if args.only:
        specs = [s for s in DATASETS if s["name"] in set(args.only)]

    manifest = []
    failures = 0
    for spec in specs:
        print(f"[{spec['name']}]")
        try:
            manifest.append(_build_one(spec, args.force))
        except Exception as exc:  # keep going; report the failure at exit
            failures += 1
            print(f"  FAILED: {exc}", file=sys.stderr)

    # Merge with any existing manifest entries not rebuilt this run.
    manifest_path = HERE / "manifest.json"
    existing = {}
    if manifest_path.exists():
        existing = {e["name"]: e for e in json.loads(manifest_path.read_text())}
    for entry in manifest:
        existing[entry["name"]] = entry
    ordered = [existing[s["name"]] for s in DATASETS if s["name"] in existing]
    manifest_path.write_text(json.dumps(ordered, indent=2) + "\n")
    print(f"\nwrote {manifest_path} ({len(ordered)} datasets)")
    if failures:
        print(f"{failures} dataset(s) FAILED to build", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
