import logging
import threading
import time
from typing import Any

import requests


class BitcoinRPC:
    def __init__(self, url: str, username: str, password: str):
        self.url = url
        self.username = username
        self.password = password
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.auth = (self.username, self.password)
            session.headers.update({
                "Content-Type": "application/json",
                "User-Agent": "bitcoin-farm",
            })
            self._local.session = session
        return session

    def call(self, method: str, params: list[Any] | None = None, retries: int = 5) -> Any:
        params = [] if params is None else params
        payload = {"jsonrpc": "1.0", "id": "bitcoin-farm", "method": method, "params": params}

        for attempt in range(retries):
            try:
                response = self._session().post(self.url, json=payload, timeout=(10, 180))
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
                data = response.json()
                if data.get("error") is not None:
                    error = data["error"]
                    raise RuntimeError(f"RPC {method}: {error.get('code')}: {error.get('message')}")
                return data["result"]
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"Final RPC failure for {method}: {exc}") from exc
                wait = min(2 ** attempt, 30)
                logging.warning("RPC %s failed: %s. Retrying in %ds.", method, exc, wait)
                time.sleep(wait)

        raise RuntimeError(f"Unexpected RPC failure for {method}")

    def blockchain_info(self) -> dict:
        return self.call("getblockchaininfo")

    def block_hash(self, height: int) -> str:
        return self.call("getblockhash", [height])

    def block(self, block_hash: str) -> dict:
        return self.call("getblock", [block_hash, 2])

    def prune(self, height: int) -> int:
        return self.call("pruneblockchain", [height])
