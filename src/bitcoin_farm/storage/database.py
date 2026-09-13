import json
import logging

from rocksdict import Options, Rdict, WriteBatch

from ..models import ProcessedBlock


HEIGHT_KEY = b"\x00meta:height"
ADDRESS_PREFIX = b"\x01"
GENERATED_RECORD_PREFIX = b"\x02generated:"


class RocksDbRepository:
    def __init__(self, path: str, parallelism: int = 2, max_open_files: int = 256):
        logging.info("Opening RocksDB: %s", path)
        options = Options()
        options.create_if_missing(True)
        options.increase_parallelism(parallelism)
        options.set_max_open_files(max_open_files)
        options.optimize_level_style_compaction(512 * 1024 * 1024)
        self.db = Rdict(path, options)

    def last_height(self) -> int:
        value = self.db.get(HEIGHT_KEY)
        return -1 if value is None else int.from_bytes(value, "big")

    def insert_batch(self, blocks: list[ProcessedBlock]) -> int:
        if not blocks:
            return 0
        addresses = {address for block in blocks for address in block.addresses}
        batch = WriteBatch()
        for address in addresses:
            try:
                key = ADDRESS_PREFIX + address.encode("ascii")
            except UnicodeEncodeError:
                logging.warning("Ignoring non-ASCII address: %r", address)
                continue
            batch.put(key, b"")
        batch.put(HEIGHT_KEY, blocks[-1].height.to_bytes(8, "big"))
        self.db.write(batch)
        return len(addresses)

    def exists(self, address: str) -> bool:
        try:
            key = ADDRESS_PREFIX + address.encode("ascii")
        except UnicodeEncodeError:
            return False
        return self.db.get(key) is not None

    def save_generated_record(self, sequence: int, private_key: str, public_key: str, address: str) -> None:
        payload = json.dumps({
            "sequence": sequence,
            "private_key": private_key,
            "public_key": public_key,
            "address": address,
        }, sort_keys=True).encode("utf-8")
        self.db.put(GENERATED_RECORD_PREFIX + str(sequence).encode("ascii"), payload)

    def generated_records(self, offset: int = 0, limit: int = 100) -> dict:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be >= 0 and limit must be > 0")

        records = []
        for key, value in self.db.items(from_key=GENERATED_RECORD_PREFIX):
            if not key.startswith(GENERATED_RECORD_PREFIX):
                break
            records.append(json.loads(value))

        records.sort(key=lambda record: int(record["sequence"]))
        return {
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "items": records[offset:offset + limit],
        }

    def close(self) -> None:
        logging.info("Closing RocksDB.")
        self.db.close()


Database = RocksDbRepository
