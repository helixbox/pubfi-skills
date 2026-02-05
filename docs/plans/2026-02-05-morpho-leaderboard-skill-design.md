# Morpho Conservative Leaderboard Skill Design

## Context and Goals
We need the `morpho-protocol-leaderboard-conservative` skill to run successfully on the first attempt with no guessing. The user requires strict enforcement of exposure-asset allowlists. The goal is a self-contained, step-by-step workflow that uses Morpho's official GraphQL API (Vaults V1 legacy) to fetch vaults, enforce exposure allowlists, apply conservative safety and liquidity filters, and output a ranked markdown table. It must avoid mock data, be deterministic, and clarify how to derive each output column from documented fields. The skill should also explain how to build a working vault link and how to format APY and liquidity values. We should keep the external interface stable (`chain`, `limit`) and avoid introducing new required parameters.

## Constraints and Risks
Vaults V2 does not directly expose exposure assets, so strict allowlist enforcement is not possible there. Vaults V1 exposes allocation markets with loan/collateral assets, which makes allowlist enforcement feasible, but the API is marked legacy. The primary risk is reliance on V1 schema stability and larger payloads when fetching allocations; we mitigate this by per-chain queries and pagination guidance.

## Options Considered
1. **V1-only (legacy) with exposure enforcement**: Use V1 `vaults` + `state.allocation.market.loanAsset/collateralAsset` to enforce exposure allowlists. Pros: satisfies requirement, deterministic. Cons: relies on legacy API.
2. **V2 + external mapping**: Use V2 for metrics, add a maintained adapter→asset mapping to infer exposures. Pros: stays on V2. Cons: high maintenance and risk of drift.
3. **V2 without exposure enforcement**: Fast and stable but violates requirement.

## Decision
Choose **Option 1**. Use Vaults V1 and enforce exposure allowlist using allocation markets. This meets the requirement and keeps runtime deterministic. We will include a reference script and pagination guidance.

## Data Flow
1. Accept `chain` and `limit` params. Map `chain` to chain IDs and network strings.
2. Run GraphQL queries against `https://api.morpho.org/graphql` using `vaults` per chain (Ethereum/Base/Arbitrum) to avoid timeouts; use `first: 200` and `skip: 0` per chain and merge results.
3. Normalize each vault: compute `liquidityUsd` (`state.totalAssetsUsd`, fallback to `state.totalAssets / 10^decimals` for USDC/USDT), compute `netApyPct = state.netApy * 100`, determine `depositAsset` from `asset.symbol` (fallback to symbol/name inference). Build `exposureAssets` from allocation markets’ loan/collateral asset symbols.
4. Filter by `whitelisted == true`, `warnings.length == 0`, `liquidityUsd >= 10_000_000`, `state.netApy > 0`, deposit asset in allowlist, and **all exposure assets** in the exposure allowlist.
5. Sort by net APY descending, then liquidity descending, then take top `limit`.
6. Format output table and include a vault link using `https://app.morpho.org/{network}/vault/{address}`.

## Error Handling and Verification
- Fail fast on GraphQL errors and report them verbatim.
- Validate `chain` and `limit` inputs with clear error messages.
- If no vaults match, return an empty table and explain why.
- Verification: run a live GraphQL query and the reference script to confirm schema and output.
