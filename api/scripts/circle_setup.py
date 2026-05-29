"""One-time Circle Developer-Controlled-Wallets bootstrap.

The entity secret is ACCOUNT-LEVEL (shared across every API key) and is
registered with Circle exactly once. This script does NOT register a new one —
it reads the already-registered CIRCLE_ENTITY_SECRET from api/.env and creates
the treasury wallet set, printing CIRCLE_WALLET_SET_ID to write back into .env.

First-time registration (only if the account has never had an entity secret):
    from circle.web3 import utils
    secret = os.urandom(32).hex()
    utils.register_entity_secret_ciphertext(
        api_key=..., entity_secret=secret, recoveryFileDownloadPath="<a dir>")
    # then save `secret` to api/.env as CIRCLE_ENTITY_SECRET

Run:  .venv/bin/python scripts/circle_setup.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from circle.web3 import developer_controlled_wallets as dcw
from circle.web3 import utils

API_DIR = Path(__file__).resolve().parent.parent


def _env(key: str) -> str:
    for line in (API_DIR / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"{key} not found in api/.env")


def main() -> None:
    api_key = _env("CIRCLE_API_KEY")
    entity_secret = _env("CIRCLE_ENTITY_SECRET")
    for name, val in (("CIRCLE_API_KEY", api_key), ("CIRCLE_ENTITY_SECRET", entity_secret)):
        if not val or val.startswith("YOUR_"):
            raise SystemExit(f"{name} in api/.env is empty/placeholder.")

    print("Creating treasury wallet set...", file=sys.stderr)
    client = utils.init_developer_controlled_wallets_client(
        api_key=api_key, entity_secret=entity_secret
    )
    api = dcw.WalletSetsApi(client)
    resp = api.create_wallet_set(
        dcw.CreateWalletSetRequest(
            name="brewing-treasury",
            idempotency_key=str(uuid.uuid4()),
        )
    )
    print(f"WALLET_SET_ID={resp.data.wallet_set.id}")


if __name__ == "__main__":
    main()
