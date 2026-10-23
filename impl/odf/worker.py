import os

from odf.services.jobs import worker_loop

if __name__ == "__main__":
    worker_loop(os.environ.get("ODF_WORKER_ID", "worker-1"))
