#!/usr/bin/env sh
set -eu

FILE="${1:-.env}"
if [ ! -f "$FILE" ]; then
  echo "usage: $0 path/to/.env" >&2
  exit 2
fi

python3 - "$FILE" <<'PY'
import base64
import os
import secrets
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(
    "replace-with-at-least-32-random-characters", secrets.token_urlsafe(48)
)
text = text.replace(
    "replace-with-a-generated-fernet-key",
    base64.urlsafe_b64encode(os.urandom(32)).decode(),
)
text = text.replace(
    "replace-strong-db-password", secrets.token_urlsafe(24)
)
path.write_text(text, encoding="utf-8", newline="\n")
print(f"wrote {path} with generated secrets")
PY
