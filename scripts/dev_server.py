import base64
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "impl"))
os.environ.setdefault("ODF_DATABASE_URL", "sqlite:///" + ROOT + "/odf_ui.db")
os.environ.setdefault("ODF_JWT_SECRET", "dev-secret-dev-secret-dev-secret")
os.environ.setdefault(
    "ODF_FERNET_KEY",
    base64.urlsafe_b64encode(os.urandom(32)).decode())

import uvicorn

uvicorn.run("odf.main:app", host="127.0.0.1", port=18081)
