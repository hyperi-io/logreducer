# Character Policy

## Allowed Characters

This project enforces **strict ASCII-only** character usage for all code, documentation, and logged data.

### Permitted Character Set

**ASCII Characters Only (0x00-0x7F):**
- Letters: A-Z, a-z
- Numbers: 0-9
- Punctuation: . , ; : ! ? ' " ` - _ ( ) [ ] { } / \ | @ # $ % ^ & * + = < > ~
- Whitespace: space, tab, newline, carriage return
- Control characters: standard ASCII control codes

### Status Indicators

Instead of Unicode symbols, use ASCII alternatives:

| Status | ASCII | Unicode (FORBIDDEN) |
|--------|-------|-------------------|
| Success | [PASS] or OK | [PASS] [FAIL] |
| Failure | [FAIL] or ERROR | [FAIL] |
| Warning | [WARN] or WARNING | [WARN] |
| Info | [INFO] or NOTE | [INFO] |
| Progress | [RUNNING] or ... | [START] |
| Package | [PKG] or BUILT | [PKG] |

### Enforcement Rules

1. **Code Files (.py, .sh, etc.)**: ASCII-only, no exceptions
2. **Documentation (.md, .rst, .txt)**: ASCII-only
3. **Configuration (.yaml, .json, .ini)**: ASCII-only
4. **Log Files**: Strict ASCII-only enforcement
5. **Console Output**: ASCII-only for professional appearance

### Examples

**ALLOWED:**
```
[PASS] Unit tests completed successfully
[WARN] Type checking found 30 issues (non-blocking)
[INFO] Build artifacts: wheel (22.5 KB), source (26.0 KB)
```

**FORBIDDEN:**
```
[PASS] Unit tests completed successfully
[WARN] Type checking found 30 issues (non-blocking)
[PKG] Build artifacts: wheel (22.5 KB), source (26.0 KB)
```

### Rationale

- **Professional Appearance**: ASCII-only output works in all terminals
- **Log Compatibility**: Ensures logs work with all systems and tools
- **Universal Support**: Compatible with legacy systems and strict environments
- **Parsing Reliability**: ASCII-only prevents encoding issues
- **Enterprise Standards**: Many enterprise environments require ASCII-only

### Violation Detection

Use this regex to find violations:
```bash
grep -r '[^\x00-\x7F]' --include="*.py" --include="*.md" --include="*.yaml" .
```

### Enforcement

This policy is enforced by:
1. Pre-commit hooks (when configured)
2. CI/CD pipeline checks
3. Manual code review
4. Automated scanning tools
