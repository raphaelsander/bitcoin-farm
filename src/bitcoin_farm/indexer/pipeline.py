import time
from concurrent.futures import Future, ThreadPoolExecutor

from ..bitcoin import BitcoinRPC
from ..models import ProcessedBlock
from ..processing import extract_addresses


def process_block(rpc: BitcoinRPC, height: int) -> ProcessedBlock:
    block_hash = rpc.block_hash(height)
    return extract_addresses(height, block_hash, rpc.block(block_hash))


def process_range(indexer, start: int, end: int) -> int:
    if start > end:
        return start - 1

    next_submit = next_commit = start
    max_in_flight = max(indexer.config.workers * 2, indexer.config.workers)
    futures: dict[Future, int] = {}
    completed: dict[int, ProcessedBlock] = {}
    batch: list[ProcessedBlock] = []

    with ThreadPoolExecutor(max_workers=indexer.config.workers) as executor:
        def submit() -> None:
            nonlocal next_submit
            while next_submit <= end and len(futures) < max_in_flight:
                future = executor.submit(process_block, indexer.rpc, next_submit)
                futures[future] = next_submit
                next_submit += 1

        submit()
        while futures:
            done_future = next((future for future in futures if future.done()), None)
            if done_future is None:
                time.sleep(0.005)
                continue
            height = futures.pop(done_future)
            try:
                completed[height] = done_future.result()
            except Exception as exc:
                raise RuntimeError(f"Error processing block {height}: {exc}") from exc
            submit()
            while next_commit in completed:
                batch.append(completed.pop(next_commit))
                next_commit += 1
                if len(batch) >= indexer.config.batch_size:
                    indexer.commit_batch(batch, end)
                    batch = []

    if batch:
        indexer.commit_batch(batch, end)
    return next_commit - 1
