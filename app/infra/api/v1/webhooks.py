import json

import starkbank
from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.infra.config import settings
from app.infra.observability import logger
from app.infra.worker import process_webhook_event_task

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


def _parse_event(payload: str, signature: str, bypass_header: bool):
    parsed_payload = json.loads(payload)
    is_sandbox = settings.stark_environment == "sandbox"
    if is_sandbox and bypass_header and settings.debug:
        from types import SimpleNamespace

        def wrap(d):
            if not isinstance(d, dict):
                return d
            return SimpleNamespace(**{k: wrap(v) for k, v in d.items()})

        event = wrap(parsed_payload.get("event", {}))
        logger.info(
            "Webhook accepted via bypass",
            extra={"event_id": getattr(event, "id", None)},
        )
    else:
        event = starkbank.event.parse(content=payload, signature=signature)
    return (event, parsed_payload)


@router.post("/starkbank")
async def starkbank_webhook(
    request: Request, digital_signature: str = Header(None, alias="Digital-Signature")
):
    if not digital_signature:
        raise HTTPException(status_code=400, detail="Missing Digital-Signature header")
    body = await request.body()
    payload = body.decode("utf-8")
    try:
        bypass_header = request.headers.get("X-Test-Bypass") == "true"
        event, parsed_payload = _parse_event(payload, digital_signature, bypass_header)
        log_obj = getattr(event, "log", None)
        event_type = getattr(log_obj, "type", None)
        event_id = getattr(event, "id", None)
        subscription = getattr(event, "subscription", None)
        logger.info(
            "Webhook received",
            extra={
                "event_id": event_id,
                "subscription": subscription,
                "type": event_type,
            },
        )
        if subscription != "invoice" or not log_obj or (not event_type):
            return Response(content="OK", status_code=200)
        allowed_types = {"paid", "credited", "overdue", "canceled", "expired"}
        if event_type not in allowed_types:
            return Response(content="OK", status_code=200)
        invoice = getattr(log_obj, "invoice", None)
        if not invoice or not getattr(invoice, "id", None) or invoice.amount is None:
            return Response(content="OK", status_code=200)
        process_webhook_event_task.delay(
            source="starkbank",
            event_type=event_type,
            external_event_id=event_id,
            external_invoice_id=invoice.id,
            amount=invoice.amount,
            fee=getattr(invoice, "fee", 0) or 0,
            internal_id=invoice.tags[0] if getattr(invoice, "tags", None) else None,
            raw_payload=parsed_payload,
        )
        return Response(content="OK", status_code=200)
    except starkbank.error.InvalidSignatureError:
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature") from None
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled webhook error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error") from e
