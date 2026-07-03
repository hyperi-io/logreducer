# Real-log test corpora

Gzipped slices of **real** public log datasets (never synthetic) used by the
integration tests to verify reduction on varied, messy, real-world logs. Each
`*.log.gz` is a truncated, PII-cleansed slice; `manifest.json` records the
source, licence, line count and sha256 for each.

These are committed in **plain git** (not LFS) - they are small (~4 MB total)
and write-once. Attribution and licences are in the top-level [NOTICE](../../NOTICE).

## Why real, messy data

The set spans deliberately different shapes so reduction, dedup, pattern mining
(Drain3), anomaly detection and the timestamp parsing all meet genuine edge
cases: syslog, pipe-delimited, bracketed, `nova` request-context, Java stack
traces, 1990s web-access logs, structured JSON, and SSH brute-force noise -
template counts from a handful to well over a thousand.

| File | Domain | Notable messiness |
|------|--------|-------------------|
| `loghub_mac` | macOS syslog | highest template diversity, hex/IPv6 |
| `loghub_linux` | Linux syslog | varied daemon/auth messages |
| `loghub_openssh` | SSH auth | repetitive failed-login (brute force) |
| `loghub_openstack` | cloud/nova | long lines, `[req-UUID user tenant]` |
| `loghub_hadoop` | bigdata | multi-line Java stack traces |
| `loghub_proxifier` | desktop net | bracketed `[MM.DD HH:MM:SS]`, ultra-regular |
| `loghub_healthapp` | mobile app | pipe-delimited fields |
| `ita_calgary_http` | web access | 1990s format, pre-anonymised |
| `ita_nasa_http` | web access | 1995 Apache, host tokens cleansed |
| `elastic_nginx_json` | structured | one JSON object per line |
| `secrepo_auth` | security | auth.log SSH failures |

## PII cleansing

`build.py` rewrites IPs (-> `10.x`), IPv6 (-> `2001:db8::`), emails
(-> `example.com`), MAC addresses and specific hostnames to synthetic values,
**deterministically** - the same real value always maps to the same fake one,
so a line's repetition survives and the reducer still finds the pattern.
Timestamps and log structure are left intact.

## Rebuilding

The slices are committed; you only rebuild to add/refresh a dataset:

```bash
python tests/testdata/build.py            # build any missing datasets
python tests/testdata/build.py --force     # re-download + rebuild all
python tests/testdata/build.py --only loghub_mac ita_nasa_http
```

Downloads are cached in `.cache/` (gitignored). Add a dataset by appending an
entry to `DATASETS` in `build.py`. Only add datasets whose licence permits
redistribution in a public repo (see the research in the source datasets'
terms) and add its attribution to NOTICE.
