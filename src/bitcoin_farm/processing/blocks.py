from ..models import ProcessedBlock


def extract_addresses(height: int, block_hash: str, block: dict) -> ProcessedBlock:
    addresses: set[str] = set()
    transactions = block.get("tx", [])
    output_count = 0

    for transaction in transactions:
        for output in transaction.get("vout", []):
            output_count += 1
            address = output.get("scriptPubKey", {}).get("address")
            if address:
                addresses.add(address)

    return ProcessedBlock(
        height=height,
        block_hash=block_hash,
        addresses=addresses,
        transactions=len(transactions),
        outputs=output_count,
    )
