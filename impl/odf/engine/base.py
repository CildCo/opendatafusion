from dataclasses import dataclass, field
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JobSpec:
    name: str
    engine: str = "spark"
    image: str = "apache/spark:3.5.1"
    main_application_file: str = ""
    args: list[str] = field(default_factory=list)
    spark_version: str = "3.5.1"
    service_account: str = "spark-operator-spark"
    driver_cores: int = 1
    driver_memory: str = "1g"
    executor_cores: int = 1
    executor_instances: int = 1
    executor_memory: str = "1g"
    spark_conf: dict[str, str] = field(default_factory=dict)
    namespace: str | None = None
    volumes: list[dict] = field(default_factory=list)
    volume_mounts: list[dict] = field(default_factory=list)
