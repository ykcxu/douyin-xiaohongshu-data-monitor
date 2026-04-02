"""
CLI for WebSocket frame decoding and danmaku extraction.

Usage:
    python -m app.cli.decode_websocket --input data/raw/douyin/request-trace/xxx.jsonl
    python -m app.cli.decode_websocket --input data/raw/douyin/request-trace/xxx.jsonl --output decoded.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.collector.douyin.live.websocket_decoder import (
    DouyinWebSocketDecoder,
    DouyinDanmakuExtractor,
    analyze_websocket_trace,
)
import base64


def main() -> int:
    parser = argparse.ArgumentParser(description="Decode Douyin WebSocket frames")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input trace file")
    parser.add_argument("--output", "-o", type=str, help="Output file (optional)")
    parser.add_argument("--format", choices=["summary", "full"], default="summary", help="Output format")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
        
    print(f"Analyzing WebSocket frames from: {input_path}")
    results = analyze_websocket_trace(str(input_path))
    
    if "error" in results:
        print(f"Error: {results['error']}", file=sys.stderr)
        return 1
        
    # Print summary
    print(f"\n=== WebSocket Frame Analysis ===")
    print(f"Total frames: {results['total_frames']}")
    print(f"  - Gzip frames: {results['stats']['gzip_frames']}")
    print(f"  - Raw frames: {results['stats']['raw_frames']}")
    print(f"  - Decode errors: {results['stats']['decode_errors']}")
    print(f"\nExtracted messages: {len(results['messages'])}")
    
    if results['messages']:
        print(f"\n=== Sample Messages ===")
        for msg in results['messages'][:10]:
            print(f"  [{msg.get('confidence', 'unknown')}] {msg.get('type', 'unknown')}: {msg.get('content', '')[:100]}")
            
    # Output to file if specified
    if args.output:
        output_path = Path(args.output)
        
        if args.format == "summary":
            # Save summary only
            summary = {
                "total_frames": results['total_frames'],
                "stats": results['stats'],
                "messages": results['messages'],
            }
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        else:
            # Save full results
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
        print(f"\nResults saved to: {output_path}")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
