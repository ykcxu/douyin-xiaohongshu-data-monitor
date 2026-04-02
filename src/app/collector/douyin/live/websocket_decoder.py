"""
抖音直播 WebSocket 帧解码器

协议结构：
  原始二进制 → PushFrame (protobuf)
    └── payload → gzip 解压 → Response (protobuf)
          └── messagesList[] → Message
                └── method + payload → 各类消息体 (protobuf)

主要消息类型：
  WebcastChatMessage       弹幕/聊天
  WebcastGiftMessage       礼物
  WebcastLikeMessage       点赞
  WebcastMemberMessage     进房
  WebcastSocialMessage     关注/分享
  WebcastRoomUserSeqMessage 在线人数
  WebcastControlMessage    开播/下播控制
  WebcastRoomStatsMessage  房间统计
"""

from __future__ import annotations

import base64
import gzip
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# proto 生成的 pb2 模块
try:
    from app.collector.douyin.live.proto import douyin_webcast_pb2 as pb
    _PROTO_AVAILABLE = True
except ImportError:
    _PROTO_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# 数据类：解码结果
# ─────────────────────────────────────────────────────────────

@dataclass
class DecodedMessage:
    """单条直播间消息（已解码）"""
    msg_id:    int
    method:    str
    room_id:   int = 0
    timestamp: int = 0          # 毫秒级 createTime
    fetched_at: str = ""        # ISO8601

    # 各类消息的具体字段（按需填充）
    user_id:   int = 0
    nickname:  str = ""
    content:   str = ""         # 弹幕内容
    gift_id:   int = 0
    gift_name: str = ""
    gift_count: int = 0
    like_count: int = 0
    total_like: int = 0
    online_count: int = 0
    control_status: int = 0     # 2=下播
    share_type: int = 0
    action: int = 0
    raw: dict = field(default_factory=dict)  # 原始字段（调试用）


@dataclass
class FrameDecodeResult:
    """一帧 WebSocket 数据的完整解码结果"""
    seq_id:     int
    log_id:     int
    payload_type: str
    need_ack:   bool
    messages:   list[DecodedMessage] = field(default_factory=list)
    error:      str = ""


# ─────────────────────────────────────────────────────────────
# 核心解码器
# ─────────────────────────────────────────────────────────────

class DouyinWebSocketDecoder:
    """抖音直播 WebSocket 帧解码器（基于 protobuf）"""

    # method → (pb消息类, 解析函数名)
    _METHOD_MAP: dict[str, tuple[Any, str]] = {}

    def __init__(self) -> None:
        if not _PROTO_AVAILABLE:
            raise RuntimeError("proto pb2 模块不可用，请先运行 protoc 编译")
        self._build_method_map()

    def _build_method_map(self) -> None:
        self._METHOD_MAP = {
            "WebcastChatMessage":        (pb.WebcastChatMessage,        "_parse_chat"),
            "WebcastGiftMessage":        (pb.WebcastGiftMessage,        "_parse_gift"),
            "WebcastLikeMessage":        (pb.WebcastLikeMessage,        "_parse_like"),
            "WebcastMemberMessage":      (pb.WebcastMemberMessage,      "_parse_member"),
            "WebcastSocialMessage":      (pb.WebcastSocialMessage,      "_parse_social"),
            "WebcastRoomUserSeqMessage": (pb.WebcastRoomUserSeqMessage, "_parse_room_user_seq"),
            "WebcastControlMessage":     (pb.WebcastControlMessage,     "_parse_control"),
            "WebcastRoomStatsMessage":   (pb.WebcastRoomStatsMessage,   "_parse_room_stats"),
        }

    # ── 入口：解码单帧原始字节 ────────────────────────────────

    def decode_frame_bytes(self, raw: bytes) -> FrameDecodeResult:
        """解码一条 WebSocket 原始二进制帧"""
        try:
            push_frame = pb.PushFrame()
            push_frame.ParseFromString(raw)
        except Exception as e:
            return FrameDecodeResult(0, 0, "", False, error=f"PushFrame 解析失败: {e}")

        result = FrameDecodeResult(
            seq_id=push_frame.seqId,
            log_id=push_frame.logId,
            payload_type=push_frame.payloadType,
            need_ack=False,
        )

        # 解压 payload
        try:
            decompressed = gzip.decompress(push_frame.payload)
        except Exception as e:
            result.error = f"gzip 解压失败: {e}"
            return result

        # 解析 Response
        try:
            response = pb.Response()
            response.ParseFromString(decompressed)
            result.need_ack = response.needAck
        except Exception as e:
            result.error = f"Response 解析失败: {e}"
            return result

        # 逐条解析 Message
        now_iso = datetime.now(timezone.utc).isoformat()
        for msg in response.messagesList:
            decoded = self._decode_message(msg, now_iso)
            if decoded:
                result.messages.append(decoded)

        return result

    def decode_frame_base64(self, b64: str) -> FrameDecodeResult:
        """解码 CDP 格式（base64 编码）的帧"""
        try:
            raw = base64.b64decode(b64)
        except Exception as e:
            return FrameDecodeResult(0, 0, "", False, error=f"base64 解码失败: {e}")
        return self.decode_frame_bytes(raw)

    # ── Message 路由 ────────────────────────────────────────

    def _decode_message(self, msg: Any, fetched_at: str) -> DecodedMessage | None:
        method = msg.method
        entry = self._METHOD_MAP.get(method)

        # 通用基础字段
        base = DecodedMessage(
            msg_id=msg.msgId,
            method=method,
            fetched_at=fetched_at,
        )

        if entry is None:
            # 未知类型，只记录基础信息
            base.content = f"[未知消息类型: {method}]"
            return base

        pb_cls, parse_fn = entry
        try:
            pb_msg = pb_cls()
            pb_msg.ParseFromString(msg.payload)
            getattr(self, parse_fn)(pb_msg, base)
        except Exception as e:
            # 对真实 trace 中字段不稳定的消息，走 schema-free fallback
            if method == "WebcastChatMessage":
                if self._fallback_parse_chat(msg.payload, base):
                    return base
            elif method == "WebcastMemberMessage":
                if self._fallback_parse_member(msg.payload, base):
                    return base
            elif method == "WebcastRoomUserSeqMessage":
                if self._fallback_parse_room_user_seq(msg.payload, base):
                    return base
            base.content = f"[解析失败: {e}]"

        return base

    # ── 各类型解析函数 ───────────────────────────────────────

    def _fill_common(self, common: Any, out: DecodedMessage) -> None:
        if common:
            out.room_id   = common.roomId
            out.timestamp = common.createTime

    def _fill_user(self, user: Any, out: DecodedMessage) -> None:
        if user:
            out.user_id  = user.id
            out.nickname = user.nickname

    def _parse_chat(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        self._fill_user(msg.user, out)
        out.content = msg.content

    def _parse_gift(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        self._fill_user(msg.user, out)
        out.gift_id    = msg.giftId
        out.gift_count = msg.comboCount or msg.repeatCount
        if msg.gift:
            out.gift_name = msg.gift.name

    def _parse_like(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        self._fill_user(msg.user, out)
        out.like_count = msg.count
        out.total_like = msg.total

    def _parse_member(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        self._fill_user(msg.user, out)
        out.online_count = msg.memberCount
        out.content = f"{out.nickname} 进入直播间"

    def _parse_social(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        self._fill_user(msg.user, out)
        out.share_type = msg.shareType
        out.action     = msg.action
        if msg.action == 1:
            out.content = f"{out.nickname} 关注了主播"
        else:
            out.content = f"{out.nickname} 分享了直播"

    def _parse_room_user_seq(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        out.online_count = msg.total
        out.content = f"当前在线人数: {msg.total}"

    def _parse_control(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        out.control_status = msg.status
        status_map = {0: "直播中", 1: "暂停中", 2: "直播结束"}
        out.content = status_map.get(msg.status, f"状态={msg.status}")

    def _parse_room_stats(self, msg: Any, out: DecodedMessage) -> None:
        self._fill_common(msg.common, out)
        out.content = msg.displayLong or msg.displayShort or msg.displayValue

    # ── fallback: schema-free protobuf field scan ──────────────────────────

    def _decode_varint(self, data: bytes, pos: int) -> tuple[int, int]:
        result = 0
        shift = 0
        while True:
            b = data[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                return result, pos
            shift += 7

    def _parse_raw_fields(self, data: bytes) -> list[tuple[int, int, Any]]:
        pos = 0
        fields: list[tuple[int, int, Any]] = []
        while pos < len(data):
            try:
                tag, pos = self._decode_varint(data, pos)
                field_num, wire_type = tag >> 3, tag & 0x7
                if wire_type == 0:
                    value, pos = self._decode_varint(data, pos)
                    fields.append((field_num, wire_type, value))
                elif wire_type == 2:
                    length, pos = self._decode_varint(data, pos)
                    value = data[pos:pos + length]
                    pos += length
                    fields.append((field_num, wire_type, value))
                elif wire_type == 1:
                    pos += 8
                elif wire_type == 5:
                    pos += 4
                else:
                    break
            except Exception:
                break
        return fields

    def _safe_decode_utf8(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except Exception:
            return ""

    def _fallback_parse_chat(self, payload: bytes, out: DecodedMessage) -> bool:
        fields = self._parse_raw_fields(payload)
        if not fields:
            return False

        field_map: dict[int, list[tuple[int, Any]]] = {}
        for fn, wt, val in fields:
            field_map.setdefault(fn, []).append((wt, val))

        common_raw = field_map.get(1, [(None, None)])[0][1]
        if isinstance(common_raw, (bytes, bytearray)):
            try:
                common = pb.Common()
                common.ParseFromString(common_raw)
                self._fill_common(common, out)
            except Exception:
                pass

        user_raw = field_map.get(2, [(None, None)])[0][1]
        if isinstance(user_raw, (bytes, bytearray)):
            user_fields = self._parse_raw_fields(user_raw)
            for fn, wt, val in user_fields:
                if fn == 1 and wt == 0:
                    out.user_id = int(val)
                elif fn in (3, 68) and wt == 2:
                    name = self._safe_decode_utf8(val).strip()
                    if name:
                        out.nickname = name
                        break

        for wt, val in field_map.get(3, []):
            if wt == 2 and isinstance(val, (bytes, bytearray)):
                text = self._safe_decode_utf8(val).strip()
                if text:
                    out.content = text
                    break

        if not out.content:
            # 保守兜底：挑选最长的可读 UTF-8 字段作为聊天文本候选，避开 user/common 子消息。
            candidates: list[str] = []
            for fn, items in field_map.items():
                if fn in (1, 2):
                    continue
                for wt, val in items:
                    if wt == 2 and isinstance(val, (bytes, bytearray)):
                        text = self._safe_decode_utf8(val).strip()
                        if text and len(text) <= 200:
                            candidates.append(text)
            if candidates:
                out.content = max(candidates, key=len)

        out.raw = {
            "fallback": True,
            "field_keys": sorted(field_map.keys()),
        }
        return bool(out.content or out.nickname or out.user_id)

    def _fallback_parse_member(self, payload: bytes, out: DecodedMessage) -> bool:
        fields = self._parse_raw_fields(payload)
        if not fields:
            return False

        field_map: dict[int, list[tuple[int, Any]]] = {}
        for fn, wt, val in fields:
            field_map.setdefault(fn, []).append((wt, val))

        # field 1 = Common, field 2 = User(不稳定，手动抽取昵称/ID), field 3 = memberCount
        common_raw = field_map.get(1, [(None, None)])[0][1]
        if isinstance(common_raw, (bytes, bytearray)):
            try:
                common = pb.Common()
                common.ParseFromString(common_raw)
                self._fill_common(common, out)
            except Exception:
                pass

        user_raw = field_map.get(2, [(None, None)])[0][1]
        if isinstance(user_raw, (bytes, bytearray)):
            user_fields = self._parse_raw_fields(user_raw)
            for fn, wt, val in user_fields:
                if fn == 1 and wt == 0:
                    out.user_id = int(val)
                elif fn in (3, 68) and wt == 2:
                    name = self._safe_decode_utf8(val).strip()
                    if name:
                        out.nickname = name
                        break

        member_count = field_map.get(3, [(None, 0)])[0][1]
        if isinstance(member_count, int):
            out.online_count = member_count

        out.content = f"{out.nickname or '用户'} 进入直播间"
        out.raw = {
            "fallback": True,
            "member_count": out.online_count,
            "field_keys": sorted(field_map.keys()),
        }
        return True

    def _fallback_parse_room_user_seq(self, payload: bytes, out: DecodedMessage) -> bool:
        fields = self._parse_raw_fields(payload)
        if not fields:
            return False

        field_map: dict[int, list[tuple[int, Any]]] = {}
        for fn, wt, val in fields:
            field_map.setdefault(fn, []).append((wt, val))

        common_raw = field_map.get(1, [(None, None)])[0][1]
        if isinstance(common_raw, (bytes, bytearray)):
            try:
                common = pb.Common()
                common.ParseFromString(common_raw)
                self._fill_common(common, out)
            except Exception:
                pass

        # 实测 field 7 是 varint 在线人数；field 3 常是座位数/列表长度，不是总在线
        total = field_map.get(7, [(None, 0)])[0][1]
        if not isinstance(total, int):
            total = field_map.get(3, [(None, 0)])[0][1]
        if isinstance(total, int):
            out.online_count = total

        out.content = f"当前在线人数: {out.online_count}"
        out.raw = {
            "fallback": True,
            "field_keys": sorted(field_map.keys()),
        }
        return True


# ─────────────────────────────────────────────────────────────
# Trace 文件分析（兼容旧接口）
# ─────────────────────────────────────────────────────────────

def analyze_websocket_trace(trace_file: str) -> dict[str, Any]:
    """分析 request-trace JSONL 文件，提取并解码 WebSocket 帧"""
    if not _PROTO_AVAILABLE:
        return {"error": "proto pb2 模块不可用"}

    decoder = DouyinWebSocketDecoder()
    results: dict[str, Any] = {
        "total_frames": 0,
        "decoded_frames": [],
        "messages": [],
        "stats": {
            "chat": 0, "gift": 0, "like": 0, "member": 0,
            "social": 0, "room_user_seq": 0, "control": 0,
            "other": 0, "errors": 0,
        },
    }

    trace_path = Path(trace_file)
    if not trace_path.exists():
        return {"error": f"文件不存在: {trace_file}"}

    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 兼容多种 trace 格式
            ev_type = event.get("event") or event.get("type", "")
            frame_b64 = None

            if ev_type in ("cdp_websocket_frame_received", "cdp_websocket_frame_sent"):
                # 优先使用完整 payload_data，兼容旧 trace 的 payload_preview 字段
                frame_b64 = event.get("payload_data") or event.get("payload_preview") or event.get("response", {}).get("data")
                # 只处理二进制帧（opcode=2），忽略文本控制帧
                if event.get("opcode") not in (None, 2):
                    continue
            elif ev_type == "websocket_frame":
                frame_b64 = event.get("data")

            if not frame_b64:
                continue

            results["total_frames"] += 1
            frame_result = decoder.decode_frame_base64(frame_b64)

            if frame_result.error:
                results["stats"]["errors"] += 1
                continue

            for msg in frame_result.messages:
                method_key = msg.method.replace("Webcast", "").replace("Message", "").lower()
                if method_key in results["stats"]:
                    results["stats"][method_key] += 1
                else:
                    results["stats"]["other"] += 1

                results["messages"].append({
                    "msg_id":   msg.msg_id,
                    "method":   msg.method,
                    "room_id":  msg.room_id,
                    "timestamp": msg.timestamp,
                    "user_id":  msg.user_id,
                    "nickname": msg.nickname,
                    "content":  msg.content,
                    "gift_id":  msg.gift_id,
                    "gift_name": msg.gift_name,
                    "gift_count": msg.gift_count,
                    "like_count": msg.like_count,
                    "online_count": msg.online_count,
                    "control_status": msg.control_status,
                    "fetched_at": msg.fetched_at,
                })

    return results


# ─────────────────────────────────────────────────────────────
# 向后兼容的旧类名（部分 CLI 可能引用）
# ─────────────────────────────────────────────────────────────

class DouyinDanmakuExtractor:
    """兼容旧接口，转发到新解码器"""
    def __init__(self) -> None:
        self._decoder = DouyinWebSocketDecoder() if _PROTO_AVAILABLE else None

    def extract_from_bytes(self, raw: bytes) -> list[dict]:
        if not self._decoder:
            return []
        result = self._decoder.decode_frame_bytes(raw)
        return [
            {"type": "chat", "content": m.content, "nickname": m.nickname,
             "timestamp": m.fetched_at, "confidence": "high"}
            for m in result.messages if m.method == "WebcastChatMessage"
        ]


# ─────────────────────────────────────────────────────────────
# 快速测试入口
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python websocket_decoder.py <trace.jsonl>")
        sys.exit(1)
    res = analyze_websocket_trace(sys.argv[1])
    print(f"总帧数: {res.get('total_frames', 0)}")
    print(f"统计: {res.get('stats', {})}")
    print(f"消息总数: {len(res.get('messages', []))}")
    for m in res.get("messages", [])[:20]:
        print(f"  [{m['method']}] {m['nickname']}: {m['content']}")
