# PubFi DSL Server Contract (Primitive OpenSearch Contract)

This contract describes the server-side behavior for a restricted PubFi DSL that supports:

- Time-windowed retrieval from OpenSearch.
- A small set of aggregation primitives (terms, date_histogram, cooccurrence).
- Deterministic validation and hard limits.
- No SQL execution and no raw OpenSearch DSL passthrough.
- No server-side natural language compilation.

## Endpoints

All endpoints are served under the public API scope:

- `GET /v1/dsl/schema`
  - Returns supported document fields, aggregation fields, date fields, and hard limits.
- `POST /v1/dsl/query`
  - Executes the restricted DSL over OpenSearch and returns documents and aggregation results.

## Response Envelope

All responses are wrapped in the shared `ApiEnvelope` shape:

```json
{
  "code": 0,
  "data": {},
  "message": null
}
```

On errors, `code` is a negative value and `message` is an English description.

## Schema Response (Data Payload)

```json
{
  "document_fields": ["document_id", "title", "source", "source_published_at"],
  "aggregation_fields": ["tag_slugs", "source", "quality_label"],
  "date_fields": ["source_published_at", "ingested_at"],
  "limits": {
    "max_window_hours": 720,
    "max_doc_topk": 200,
    "max_filter_items": 50,
    "max_filter_len": 128,
    "max_fields": 32,
    "max_aggregations": 10,
    "max_terms_size": 200,
    "max_cooccurrence_edges": 2500
  }
}
```

## Query Request Shape

Required:

- `window`: `{start, end}` (UTC RFC 3339). `end` is exclusive.
- `search`: `{text, doc_topk}`.

Optional:

- `filters`: `{tags, entities, sources}`.
- `output`: `{fields, aggregations}`.

The `window` is currently applied to `source_published_at`.

## Query Response (Data Payload)

```json
{
  "request_id": "1738870000000000000",
  "window": {"start": "2026-02-05T00:00:00Z", "end": "2026-02-06T00:00:00Z"},
  "data": {
    "documents": [
      {
        "document_id": "…",
        "title": "…",
        "source": "…",
        "source_published_at": "…",
        "tag_slugs": ["…"],
        "score": 12.34
      }
    ],
    "aggregations": {
      "top_tags": {"buckets": [{"key": "exchange_hack", "doc_count": 42}]},
      "tag_edges": {
        "edges": [{"a": "exchange_hack", "b": "withdrawal_pause", "doc_count": 12}]
      }
    }
  },
  "meta": {"os_returned": 20, "os_total": 1842, "warnings": []}
}
```

Notes:

- `documents` contains only `_source` fields selected by `output.fields`, plus an added `score`.
- `aggregations` is keyed by the request aggregation `name`.
- For `cooccurrence`, the server normalizes the OpenSearch response into `edges` to avoid deeply nested buckets.

## Aggregation Mapping

- `terms`: OpenSearch `terms` aggregation on a fixed allow list of keyword fields.
- `date_histogram`: OpenSearch `date_histogram` on an allow list of date fields. `fixed_interval` is restricted.
- `cooccurrence`: OpenSearch `terms` aggregation with an inner `terms` sub-aggregation on the same field, normalized to edges.

## Validation Rules

- Reject any unknown field at any nesting level.
- Enforce a maximum window length.
- Enforce `window.end` as exclusive.
- Enforce `doc_topk` limits.
- Enforce filter list sizes and per-item string lengths.
- Enforce maximum requested document fields and aggregations.
- Enforce `terms.size` limits.
- Enforce `cooccurrence` maximum edges and allowed fields.
- Enforce `date_histogram.fixed_interval` allow list.

## Security Notes

- Never accept SQL or OpenSearch DSL in the payload.
- Never expose raw indices or table names to clients.
- Always apply server-side authentication, rate limiting, and audit logging.
