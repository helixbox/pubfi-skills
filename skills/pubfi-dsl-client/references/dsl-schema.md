# PubFi DSL Schema (Client Contract)

This schema describes the restricted DSL accepted by the PubFi API. The server does not accept SQL or raw OpenSearch DSL.

## Endpoints

- `GET /v1/dsl/schema`
- `POST /v1/dsl/query`

## Required Top-Level Fields

- `window`: Object with `start` and `end` timestamps in ISO 8601 UTC. `end` is exclusive.
- `search`: Object with `text` and `doc_topk`.

## Optional Top-Level Fields

- `filters`: Object with `tags`, `entities`, and `sources` arrays.
- `output`: Object with `fields` and `aggregations`.

## Output Fields

- `output.fields`: Array of allow-listed document fields (from the schema endpoint).
- If `output.fields` is empty, the server returns a small default set of fields.

## Aggregations

`output.aggregations` is an array of:

- `{"name": "top_tags", "aggregation": {"type": "terms", "field": "tag_slugs", "size": 50}}`
- `{"name": "volume_1h", "aggregation": {"type": "date_histogram", "field": "source_published_at", "fixed_interval": "1h"}}`
- `{"name": "tag_edges", "aggregation": {"type": "cooccurrence", "field": "tag_slugs", "outer_size": 50, "inner_size": 50}}`

## Constraints

- `window.end` is exclusive.
- `search.doc_topk` must not exceed server limits.
- Filter arrays must not exceed server limits.
- `output.fields` and `output.aggregations` must not exceed server limits.
- `terms.size`, `cooccurrence.outer_size`, and `cooccurrence.inner_size` must not exceed server limits.
- `date_histogram.fixed_interval` must be in the server allow list.
