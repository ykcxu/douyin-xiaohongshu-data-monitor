from __future__ import annotations

import argparse
import base64
import json
import string
from pathlib import Path
from typing import Any


PRINTABLE = set(string.printable)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect frontier WebSocket frame previews and try lightweight protobuf-style decoding.",
    )
    parser.add_argument("--input", required=True, help="Path to a *.frontier.json summary file.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    return parser


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_probable_base64(payload: str, opcode: Any) -> bool:
    if opcode != 2:
        return False
    if len(payload) < 16:
        return False
    allowed = set(string.ascii_letters + string.digits + "+/=_-")
    return all(ch in allowed for ch in payload)


def decode_payload(payload: str, opcode: Any) -> tuple[bytes, str]:
    if is_probable_base64(payload, opcode):
        return base64.b64decode(payload + "==="), "base64"
    return payload.encode("utf-8", errors="replace"), "utf8"


def ascii_preview(data: bytes, limit: int = 120) -> str:
    return "".join(chr(b) if chr(b) in PRINTABLE and b not in {10, 13, 9, 11, 12} else "." for b in data[:limit])


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    result = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, offset
        shift += 7
        if shift >= 64:
            break
    raise ValueError("Invalid varint")


def parse_protobuf_fields(data: bytes, *, max_fields: int = 12) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    offset = 0
    while offset < len(data) and len(fields) < max_fields:
        try:
            tag, offset = read_varint(data, offset)
        except ValueError:
            break
        field_number = tag >> 3
        wire_type = tag & 0x07
        entry: dict[str, Any] = {
            "field_number": field_number,
            "wire_type": wire_type,
        }
        try:
            if wire_type == 0:
                value, offset = read_varint(data, offset)
                entry["value"] = value
            elif wire_type == 1:
                if offset + 8 > len(data):
                    break
                raw = data[offset : offset + 8]
                offset += 8
                entry["value_hex"] = raw.hex()
            elif wire_type == 2:
                length, offset = read_varint(data, offset)
                raw = data[offset : offset + length]
                offset += length
                entry["length"] = length
                entry["value_hex"] = raw[:48].hex()
                printable = ascii_preview(raw, limit=120)
                if any(ch != "." for ch in printable):
                    entry["ascii_preview"] = printable
                nested = parse_protobuf_fields(raw, max_fields=6)
                if nested:
                    entry["nested_fields"] = nested
            elif wire_type == 5:
                if offset + 4 > len(data):
                    break
                raw = data[offset : offset + 4]
                offset += 4
                entry["value_hex"] = raw.hex()
            else:
                entry["unsupported"] = True
                break
        except ValueError:
            break
        fields.append(entry)
    return fields


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Missing input file: {input_path}")
        return 1

    payload = load_json(input_path)
    result: dict[str, Any] = {
        "input": str(input_path),
        "frames": {},
    }

    frame_map = payload.get("frame_preview_by_request_id", {})
    for request_id, frames in frame_map.items():
        decoded_frames = []
        for frame in frames:
            payload_preview = str(frame.get("payload_preview", ""))
            opcode = frame.get("opcode")
            raw, encoding = decode_payload(payload_preview, opcode)
            decoded_frames.append(
                {
                    "event": frame.get("event"),
                    "opcode": opcode,
                    "encoding_guess": encoding,
                    "raw_length": len(raw),
                    "hex_preview": raw[:64].hex(),
                    "ascii_preview": ascii_preview(raw),
                    "protobuf_fields": parse_protobuf_fields(raw),
                }
            )
        result["frames"][request_id] = decoded_frames

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + ".frames.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved frame inspection: {output_path}")
    for request_id, frames in result["frames"].items():
        print(f"== Request {request_id} ==")
        for frame in frames:
            print(
                f"{frame['event']} opcode={frame['opcode']} encoding={frame['encoding_guess']} "
                f"raw_length={frame['raw_length']}"
            )
            print(f"ascii: {frame['ascii_preview'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
