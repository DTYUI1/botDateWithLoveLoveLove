import json
import time


def build_message(msg_id: int, size_bytes: int) -> bytes:
    sent_at = time.time()
    envelope = {"id": msg_id, "sent_at": sent_at, "payload": ""}
    overhead = len(json.dumps(envelope).encode("utf-8"))
    padding = max(0, size_bytes - overhead)
    envelope["payload"] = "x" * padding
    return json.dumps(envelope).encode("utf-8")


def read_sent_at(raw: bytes) -> float:
    return json.loads(raw)["sent_at"]
