import re

FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "copy", "call", "do", "merge", "vacuum", "attach",
    "detach", "pragma", "outfile", "dumpfile", "load_file", "nextval",
    "setval", "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
}
FORBIDDEN_PATTERNS = (
    r"for\s+(update|share)",
    r"into\s+(outfile|dumpfile)",
    r"locking\s+clause",
)


class SqlGuardError(ValueError):
    pass


def _scan(sql):
    """Blank out strings, identifiers and comments; keep real SQL tokens."""
    out, i, n = [], 0, len(sql)
    in_block = False
    while i < n:
        if in_block:
            if sql.startswith("/*", i):
                raise SqlGuardError("nested comments are not allowed")
            if sql.startswith("*/", i):
                in_block = False
                out.append(" ")
                i += 2
                continue
            i += 1
            continue

        if sql.startswith("/*", i):
            in_block = True
            i += 2
            continue

        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            out.append(" ")
            continue

        ch = sql[i]
        if ch == "'":
            escape = i > 0 and sql[i - 1] in "Ee" and (
                i < 2 or not sql[i - 2].isalnum())
            i += 1
            closed = False
            while i < n:
                if escape and sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    closed = True
                    break
                i += 1
            if not closed:
                raise SqlGuardError("unclosed string literal")
            out.append(" ")
            continue

        if ch == '"':
            i += 1
            closed = False
            while i < n:
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    closed = True
                    break
                i += 1
            if not closed:
                raise SqlGuardError("unclosed quoted identifier")
            out.append(" ")
            continue

        if ch == "$":
            match = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end < 0:
                    raise SqlGuardError("unclosed dollar quote")
                i = end + len(tag)
                out.append(" ")
                continue

        out.append(ch)
        i += 1

    if in_block:
        raise SqlGuardError("unclosed comment")
    return "".join(out)


def ensure_read_only(sql):
    scanned = _scan(sql or "").strip()
    if not scanned:
        raise SqlGuardError("sql is empty")
    body = scanned.rstrip(";").rstrip()
    if ";" in body:
        raise SqlGuardError("multiple statements are not allowed")
    if not re.match(r"(?is)^(select|with)\b", body):
        raise SqlGuardError("only SELECT queries are allowed")
    lowered = body.lower()
    for word in FORBIDDEN:
        if re.search(r"\b%s\b" % word, lowered):
            raise SqlGuardError("forbidden keyword: %s" % word)
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            raise SqlGuardError("forbidden construct: %s" % pattern)
