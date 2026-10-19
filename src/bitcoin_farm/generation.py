import hashlib
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from bitcoinlib.keys import HDKey

from .storage import RocksDbRepository


@dataclass
class GenerationStatus:
    state: str = "idle"
    filename: str | None = None
    run_id: str | None = None
    processed: int = 0
    matches: int = 0
    last_address: str | None = None
    last_match: str | None = None
    error: str | None = None
    stop_requested: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "filename": self.filename,
                "run_id": self.run_id,
                "processed": self.processed,
                "matches": self.matches,
                "last_address": self.last_address,
                "last_match": self.last_match,
                "error": self.error,
                "stop_requested": self.stop_requested,
            }


class GenerationWorker:
    def __init__(
        self,
        repository: RocksDbRepository,
        wordlist_dir: str = "/wordlists",
        wordlist_encoding: str = "auto",
        derivation_depth: int = 1,
    ):
        self.repository = repository
        self.wordlist_dir = Path(wordlist_dir).resolve()
        self.wordlist_encoding = wordlist_encoding
        self.derivation_depth = derivation_depth
        self.status = GenerationStatus()
        self._thread: threading.Thread | None = None

    def _candidate_addresses_for_passphrase(self, passphrase: str) -> list[tuple[str, str, str]]:
        candidates: list[tuple[str, str, str]] = []
        private_key = hashlib.sha256(passphrase.encode("utf-8")).digest()
        address_types = {
            "p2pkh": {
                "witness_type": "legacy",
                "path": "m/44'/0'/0'",
                "electrum_type": "p2pkh",
            },
            "p2sh": {
                "witness_type": "p2sh-segwit",
                "path": "m/49'/0'/0'",
                "electrum_type": "p2wpkh-p2sh",
            },
            "p2wpkh": {
                "witness_type": "segwit",
                "path": "m/84'/0'/0'",
                "electrum_type": "p2wpkh",
            },
        }

        wallets = {
            kind: HDKey(private_key, witness_type=address_type["witness_type"])
            for kind, address_type in address_types.items()
        }

        for kind, address_type in address_types.items():
            wallet = wallets[kind]
            candidates.append(
                (
                    address_type["electrum_type"],
                    wallet.wif_key(),
                    wallet.address(),
                )
            )

        for kind, address_type in address_types.items():
            wallet = wallets[kind]
            for index in range(self.derivation_depth):
                path = f"{address_type['path']}/0/{index}"
                subkey = wallet.key_for_path(path)
                candidates.append(
                    (
                        address_type["electrum_type"],
                        subkey.wif_key(),
                        subkey.address(),
                    )
                )

        return candidates

    def start(self, filename: str) -> dict:
        if Path(filename).name != filename or filename in {"", ".", ".."}:
            raise ValueError("filename must be a file name only")
        path = (self.wordlist_dir / filename).resolve()
        if path.parent != self.wordlist_dir or not path.is_file():
            raise FileNotFoundError("wordlist not found")
        run_id = uuid4().hex
        with self.status._lock:
            if self.status.state == "running":
                raise RuntimeError("a generation process is already running")
            self.status = GenerationStatus(
                state="running",
                filename=filename,
                run_id=run_id,
            )
        self._thread = threading.Thread(
            target=self._run,
            args=(path, run_id),
            daemon=True,
        )
        self._thread.start()
        return self.status.snapshot()

    def stop(self) -> dict:
        with self.status._lock:
            if self.status.state == "running":
                self.status.stop_requested = True
        return self.status.snapshot()

    def _run(self, path: Path, run_id: str) -> None:
        try:
            with path.open("rb") as wordlist:
                for raw_line in wordlist:
                    with self.status._lock:
                        if self.status.stop_requested:
                            self.status.state = "stopped"
                            return
                    passphrase = self._decode_line(raw_line).rstrip("\r\n")
                    if not passphrase:
                        continue
                    with self.status._lock:
                        self.status.processed += 1
                        sequence = self.status.processed

                    found_match = False
                    for kind, private_key_wif, address in self._candidate_addresses_for_passphrase(passphrase):
                        if not self.repository.exists(address):
                            continue
                        found_match = True
                        self.status.last_address = address
                        self.repository.save_generated_record(
                            run_id=run_id,
                            sequence=sequence,
                            wordlist_filename=path.name,
                            kind=kind,
                            private_key=private_key_wif,
                            address=address,
                        )
                        with self.status._lock:
                            self.status.matches += 1
                            self.status.last_match = address
                        logging.info("MATCH type=%s address=%s line=%d", kind, address, self.status.processed)
                        break

                    if not found_match:
                        with self.status._lock:
                            self.status.last_address = self._candidate_addresses_for_passphrase(passphrase)[-1][2]
            with self.status._lock:
                self.status.state = "completed"
        except Exception as exc:
            with self.status._lock:
                self.status.state = "failed"
                self.status.error = str(exc)

    def _decode_line(self, raw_line: bytes) -> str:
        if self.wordlist_encoding != "auto":
            return raw_line.decode(self.wordlist_encoding)
        try:
            return raw_line.decode("utf-8")
        except UnicodeDecodeError:
            logging.warning("Wordlist line is not UTF-8; using CP1252.")
            return raw_line.decode("cp1252")