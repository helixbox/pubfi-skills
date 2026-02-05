# Morpho Conservative Leaderboard Skill Design

## Context and Goals
We need the `morpho-protocol-leaderboard-conservative` skill to run successfully on the first attempt with no guessing. Today the skill is missing concrete GraphQL field names, a deterministic filter pipeline, and an executable query. The goal is a self-contained, step-by-step workflow that uses Morpho's official GraphQL API (Vaults V2) to fetch vaults, apply conservative filters, and output a ranked markdown table. It must avoid mock data, be deterministic, and clarify how to derive each output column from documented fields. The skill should also explain how to build a working vault link and how to format APY and liquidity values. We should keep the external interface stable (`chain`, `limit`) and avoid introducing new required parameters.

## Constraints and Risks
The V2 API exposes adapter allocations, but it does not provide a direct, documented list of exposure assets. That means strict “exposure asset allowlist” filtering is not feasible without additional data sources or legacy V1 endpoints. We need to decide whether to (1) skip exposure filtering, (2) add a legacy V1 optional path, or (3) maintain per-chain token address allowlists. Option (1) risks loosened conservatism; option (2) adds complexity and a second query; option (3) is accurate but high-maintenance and brittle. Another risk is that vault token symbols are not identical to deposit asset symbols, so we must define a deterministic heuristic for deposit-asset identification that is conservative and excludes unknowns rather than guessing.

## Options Considered
1. **V2-only, conservative safety filters**: Use V2 query, require `whitelisted` true and no warnings, filter by liquidity and `avgNetApy`, infer deposit asset from vault symbol/name. Pros: single query, stable, works today. Cons: exposure allowlist cannot be enforced.
2. **Hybrid V2 + legacy V1 for exposure filtering**: Use V2 for metrics, V1 allocation data for exposure allowlist, join by address. Pros: stricter exposure filtering. Cons: more queries, partial coverage, V1 may be deprecated.
3. **Address allowlist per chain**: Use V2 asset address and a maintained allowlist of stablecoin/ETH/BTC token addresses across chains. Pros: precise, fully deterministic. Cons: large and brittle lists, high maintenance, easy to drift.

## Decision
Choose **Option 1** with explicit documentation of its limits and a conservative safety gate (`whitelisted` true and zero warnings). We will keep the exposure allowlist as a rule of intent but document that V2 does not expose exposure assets; therefore, the rule is not enforced in the default flow. This makes the skill runnable in one pass while keeping the conservative posture via whitelisting and warning checks. If strict exposure enforcement is required later, we can extend with an optional legacy path.

## Data Flow
1. Accept `chain` and `limit` params. Map `chain` to chain IDs and network strings.
2. Run GraphQL queries against `https://api.morpho.org/graphql` using `vaultV2s` per chain (Ethereum/Base/Arbitrum) to avoid timeouts; use `first: 200` per chain and merge results.
3. Normalize each vault: compute `liquidityUsd` (`liquidityUsd ?? totalAssetsUsd`), and if both are null for stablecoins, compute `totalAssets / 10^decimals` as a USD proxy. Compute `netApyPct = avgNetApy * 100`, determine a conservative `depositAsset` via symbol/name matching. Exclude any vault that cannot be mapped to a deposit asset or whose USD liquidity cannot be verified.
4. Filter by `whitelisted == true`, `warnings.length == 0`, `liquidityUsd >= 10_000_000`, `netApyPct > 0`, and deposit asset in allowlist.
5. Sort by net APY descending, then liquidity descending, then take top `limit`.
6. Format output table and include a vault link using `https://app.morpho.org/{network}/vault/{address}`.

## Error Handling and Verification
- Fail fast on GraphQL errors and report them verbatim.
- Validate `chain` and `limit` inputs with clear error messages.
- If no vaults match, return an empty table and explain why.
- Verification: run a live GraphQL query to confirm field names and types before finalizing the skill.
