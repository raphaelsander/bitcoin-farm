from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessedBlock:
    height: int
    block_hash: str
    addresses: set[str]
    transactions: int
    outputs: int
