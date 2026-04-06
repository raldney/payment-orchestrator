import os
import sys

import starkbank

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.infra.adapters.starkbank_adapter.client import init_starkbank


def register():
    """
    Registra o webhook oficial no Stark Bank.
    """
    init_starkbank()

    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: WEBHOOK_URL environment variable not set.")
        return

    try:
        webhooks = starkbank.webhook.create(url=webhook_url, subscriptions=["invoice"])
        print(f"Webhook registered successfully: {webhooks[0].id}")
    except Exception as e:
        print(f"Failed to register webhook: {e}")


if __name__ == "__main__":
    register()
