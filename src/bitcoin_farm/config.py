from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    rpc_url: str
    rpc_user: str
    rpc_password: str
    db_path: str
    workers: int
    rocksdb_threads: int
    batch_size: int
    poll_interval: float
    prune_margin: int
    prune_interval: int
    start_height: int
    rocksdb_max_open_files: int = 256

