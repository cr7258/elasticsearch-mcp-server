"""Token comparison: Elasticsearch tool-result JSON vs GCF.

Measures the model-facing token cost of representative Elasticsearch responses when
serialized as compact JSON (what the tool returns today) versus GCF (what the optional
``RESPONSE_FORMAT=gcf`` middleware emits in the content block). Also verifies GCF
round-trips back to the original value, so the saving is lossless.

Run with real token counts:

    uv run --with tiktoken python benchmarks/gcf_benchmark.py

Without tiktoken it falls back to a bytes/4 approximation (clearly labeled).
"""

from __future__ import annotations

import json

from gcf import decode_generic, encode_generic

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("o200k_base")

    def count_tokens(s: str) -> int:
        return len(_ENC.encode(s))

    TOKENIZER = "o200k_base"
except Exception:  # noqa: BLE001

    def count_tokens(s: str) -> int:
        return max(1, len(s) // 4)

    TOKENIZER = "bytes/4 approximation (install tiktoken for exact counts)"


# --- Representative Elasticsearch tool results (uniform record sets) ---

SEARCH_HITS = {
    "total": 5,
    "max_score": 2.31,
    "hits": [
        {"_index": "orders", "_id": f"ord-{i}", "_score": round(2.31 - i * 0.12, 2),
         "order_id": 100000 + i, "customer": f"cust-{i % 3}", "status": "shipped" if i % 2 else "pending",
         "total": round(19.99 + i * 7.5, 2), "region": ["us-east", "eu-west", "ap-south"][i % 3]}
        for i in range(24)
    ],
}

AGG_BUCKETS = {
    "aggregations": {
        "by_status": {
            "buckets": [
                {"key": "shipped", "doc_count": 1842, "revenue": {"value": 284019.5}},
                {"key": "pending", "doc_count": 613, "revenue": {"value": 91204.0}},
                {"key": "cancelled", "doc_count": 88, "revenue": {"value": 12010.25}},
                {"key": "returned", "doc_count": 41, "revenue": {"value": 5320.0}},
            ]
        }
    }
}

INDEX_MAPPING = {
    "fields": [
        {"field": "order_id", "type": "long", "indexed": True, "stored": False, "doc_values": True},
        {"field": "customer", "type": "keyword", "indexed": True, "stored": False, "doc_values": True},
        {"field": "status", "type": "keyword", "indexed": True, "stored": False, "doc_values": True},
        {"field": "total", "type": "scaled_float", "indexed": True, "stored": False, "doc_values": True},
        {"field": "created_at", "type": "date", "indexed": True, "stored": False, "doc_values": True},
        {"field": "region", "type": "keyword", "indexed": True, "stored": False, "doc_values": True},
    ]
}

CASES = [
    ("search hits (24 uniform docs)", SEARCH_HITS),
    ("terms aggregation (4 buckets)", AGG_BUCKETS),
    ("index mapping (6 fields)", INDEX_MAPPING),
]


def main() -> None:
    print(f"Tokenizer: {TOKENIZER}\n")
    header = f"{'payload':<32} {'JSON':>8} {'GCF':>8} {'saved':>8}  lossless"
    print(header)
    print("-" * len(header))
    tot_json = tot_gcf = 0
    for name, data in CASES:
        j = json.dumps(data, separators=(",", ":"))
        g = encode_generic(data)
        jt, gt = count_tokens(j), count_tokens(g)
        tot_json += jt
        tot_gcf += gt
        lossless = decode_generic(g) == json.loads(j)
        saved = f"{(1 - gt / jt) * 100:.1f}%" if jt else "-"
        print(f"{name:<32} {jt:>8} {gt:>8} {saved:>8}  {'yes' if lossless else 'NO'}")
    print("-" * len(header))
    saved = f"{(1 - tot_gcf / tot_json) * 100:.1f}%" if tot_json else "-"
    print(f"{'TOTAL':<32} {tot_json:>8} {tot_gcf:>8} {saved:>8}")


if __name__ == "__main__":
    main()
