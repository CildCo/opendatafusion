import os
import shutil
from pathlib import Path


class LocalStorage:
    def __init__(self, base):
        self.base = Path(base)

    def _path(self, key):
        p = (self.base / key).resolve()
        if self.base.resolve() not in p.parents and p != self.base.resolve():
            raise ValueError("invalid storage key")
        return p

    def exists(self, key):
        return self._path(key).is_file()

    def put(self, key, temp_path):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        if Path(temp_path).resolve() == p:
            return
        tmp = p.with_name(p.name + ".tmp")
        shutil.copyfile(temp_path, tmp)
        os.replace(tmp, p)

    def open(self, key, chunk=1024 * 1024):
        with open(self._path(key), "rb") as fh:
            while True:
                data = fh.read(chunk)
                if not data:
                    break
                yield data

    def delete(self, key):
        p = self._path(key)
        if p.is_file():
            p.unlink()


class S3Storage:
    def __init__(self, settings):
        import boto3
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            region_name=settings.s3_region or None)

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def put(self, key, temp_path):
        self.client.upload_file(temp_path, self.bucket, key)

    def open(self, key, chunk=1024 * 1024):
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        while True:
            data = body.read(chunk)
            if not data:
                break
            yield data

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)


def storage_for(settings):
    if getattr(settings, "file_backend", "local") == "s3":
        return S3Storage(settings)
    return LocalStorage(getattr(settings, "file_dir", "./data/files"))
