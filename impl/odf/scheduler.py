from odf.services.jobs import scheduler_main

def _apply_overrides():
    from odf.db import SessionLocal
    from odf.services.platform import apply_runtime
    try:
        with SessionLocal() as session:
            apply_runtime(session)
    except Exception:
        pass


if __name__ == "__main__":
    _apply_overrides()
    scheduler_main()
