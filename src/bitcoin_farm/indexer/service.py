import logging
import time

from ..bitcoin import BitcoinRPC
from ..config import Config
from ..models import ProcessedBlock
from ..storage import RocksDbRepository
from .pipeline import process_range


class Indexer:
    def __init__(self, config: Config):
        self.config = config
        self.rpc = BitcoinRPC(config.rpc_url, config.rpc_user, config.rpc_password)
        self.db = RocksDbRepository(
            config.db_path,
            config.rocksdb_threads,
            config.rocksdb_max_open_files,
        )
        self.started = time.monotonic()
        self.last_batch_time = self.started
        self.processed_blocks = 0
        self.processed_transactions = 0
        self.processed_outputs = 0
        self.written_addresses = 0
        self.last_pruned_height = -1
        self.last_prune_checkpoint = -1

    def commit_batch(self, batch: list[ProcessedBlock], core_height: int) -> None:
        if not batch:
            return
        started = time.monotonic()
        written = self.db.insert_batch(batch)
        db_time = time.monotonic() - started
        self.written_addresses += written
        self.processed_blocks += len(batch)
        self.processed_transactions += sum(block.transactions for block in batch)
        self.processed_outputs += sum(block.outputs for block in batch)
        elapsed = max(time.monotonic() - self.last_batch_time, 1e-9)
        self.last_batch_time = time.monotonic()
        indexed_height = batch[-1].height
        logging.info(
            "index=%d | core=%d | backlog=%d | batch=%d | keys=%d | %.1f blocks/s | %.0f tx/s | %.0f outputs/s | db=%.3fs",
            indexed_height, core_height, max(0, core_height - indexed_height), len(batch), written,
            len(batch) / elapsed, sum(block.transactions for block in batch) / elapsed,
            sum(block.outputs for block in batch) / elapsed, db_time,
        )
        self.maybe_prune(indexed_height)

    def maybe_prune(self, indexed_height: int) -> None:
        if self.config.prune_margin <= 0:
            return
        if self.last_prune_checkpoint >= 0 and indexed_height - self.last_prune_checkpoint < self.config.prune_interval:
            return
        target = indexed_height - self.config.prune_margin
        if target <= 0:
            return
        try:
            result = self.rpc.prune(target)
            info = self.rpc.blockchain_info()
            self.last_prune_checkpoint = indexed_height
            self.last_pruned_height = int(info.get("pruneheight", 0))
            logging.info("Prune target=%d | result=%d | pruneheight=%d", target, result, self.last_pruned_height)
        except Exception as exc:
            logging.warning("Pruning failed up to %d: %s", target, exc)

    def process_range(self, start: int, end: int) -> int:
        logging.info("Processing %d -> %d", start, end)
        return process_range(self, start, end)

    def run(self) -> None:
        try:
            info = self.rpc.blockchain_info()
            logging.info(
                "Connected to Bitcoin Core | blocks=%s | headers=%s | IBD=%s",
                info.get("blocks"),
                info.get("headers"),
                info.get("initialblockdownload"),
            )
            if not info.get("pruned", False):
                logging.warning("Bitcoin Core is not running in prune mode.")
            next_height = self.db.last_height() + 1
            if next_height == 0:
                next_height = self.config.start_height
            logging.info("Checkpoint loaded | next block=%d", next_height)
            while True:
                info = self.rpc.blockchain_info()
                core_height = int(info["blocks"])
                if next_height <= core_height:
                    next_height = self.process_range(next_height, core_height) + 1
                    continue
                logging.info("Synchronized | height=%d | pruneheight=%s", core_height, info.get("pruneheight", 0))
                time.sleep(self.config.poll_interval)
        except Exception:
            logging.exception("Fatal error in indexer thread.")
            raise

    def close(self) -> None:
        self.db.close()
