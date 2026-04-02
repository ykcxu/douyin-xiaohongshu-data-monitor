from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_headers(headers: Any) -> dict[str, str]:
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def attach_cdp_websocket_trace(
    cdp_session,
    *,
    emit: Callable[[dict[str, object]], None],
) -> None:
    """Attach CDP websocket listeners to an existing CDP session.

    The caller owns the CDP session lifecycle. This helper only wires listeners.
    """
    cdp_session.send("Network.enable")

    def on_websocket_created(params: dict[str, Any]) -> None:
        emit(
            {
                "event": "cdp_websocket_created",
                "ts": iso_now(),
                "request_id": params.get("requestId"),
                "url": params.get("url"),
                "initiator": params.get("initiator"),
            }
        )

    def on_websocket_frame_received(params: dict[str, Any]) -> None:
        response_payload = params.get("response", {})
        emit(
            {
                "event": "cdp_websocket_frame_received",
                "ts": iso_now(),
                "request_id": params.get("requestId"),
                "opcode": response_payload.get("opcode"),
                "payload_preview": str(response_payload.get("payloadData", ""))[:5000],
            }
        )

    def on_websocket_frame_sent(params: dict[str, Any]) -> None:
        response_payload = params.get("response", {})
        emit(
            {
                "event": "cdp_websocket_frame_sent",
                "ts": iso_now(),
                "request_id": params.get("requestId"),
                "opcode": response_payload.get("opcode"),
                "payload_preview": str(response_payload.get("payloadData", ""))[:5000],
            }
        )

    cdp_session.on("Network.webSocketCreated", on_websocket_created)
    cdp_session.on("Network.webSocketFrameReceived", on_websocket_frame_received)
    cdp_session.on("Network.webSocketFrameSent", on_websocket_frame_sent)
