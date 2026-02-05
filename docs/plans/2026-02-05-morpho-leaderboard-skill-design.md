# Morpho Conservative Leaderboard Skill Design

## Context and Goals
We need the `morpho-protocol-leaderboard-conservative` skill to run successfully on the first attempt with no guessing. The user requires strict enforcement of exposure-asset allowlists and wants to support V2-only vaults (example on Base). The goal is a self-contained, step-by-step workflow that uses Morpho's official GraphQL API (Vaults V2) to fetch vaults, enforce address allowlists for exposures, apply conservative safety and liquidity filters, and output a ranked markdown table. It must avoid mock data, be deterministic, and clarify how to derive each output column from documented fields. We should keep the external interface stable (`chain`, `limit`) and avoid introducing new required parameters.

## Constraints and Risks
Vaults V2 expresses allocations via adapters. Exposure assets are not directly listed as a flat field; they must be derived from adapter-specific data (e.g., Morpho Market adapter loan/collateral assets, MetaMorpho nested vaults). This introduces complexity and potential unknown adapter types. To stay conservative, any unknown adapter or incomplete exposure data must exclude the vault. Another risk is USD liquidity fields being null; we mitigate by computing USD for USDC/USDT using total assets and decimals. USDS/sUSDS are officially documented on Ethereum and Base only; we omit Arbitrum addresses to avoid guessing.

## Options Considered
1. **V2 + address allowlist via adapters (recommended)**: Use V2 `vaultV2s` for base data, and `vaultV2ByAddress` to derive exposure addresses from adapters. Pros: supports V2-only vaults and strict allowlists. Cons: more queries and adapter complexity.
2. **V2 + vault address allowlist**: Fast, but violates exposure-asset requirement.
3. **V1 only**: Exposure assets are easy to derive, but misses V2-only vaults.

## Decision
Choose **Option 1**. Use Vaults V2 and enforce exposure allowlists by address derived from adapter data. Unknown adapter types or incomplete exposure data cause exclusion (conservative).

## Data Flow
1. Accept `chain` and `limit` params. Map `chain` to chain IDs and network strings.
2. Query `vaultV2s` per chain (pagination with `first` and `skip`), fetching vault metadata, asset address, total assets, total assets USD, net APY, whitelisted status, and warnings.
3. Normalize each vault: compute `liquidityUsd` (use `totalAssetsUsd`, fallback for USDC/USDT via decimals), compute `netApyPct`, map deposit asset address to a canonical symbol (WETH->ETH, WBTC/cbBTC->BTC).
4. Pre-filter by `whitelisted == true`, `warnings.length == 0`, `liquidityUsd >= 10_000_000`, `netApy > 0`, deposit asset in [USDC, USDT, ETH, BTC].
5. For remaining candidates, query `vaultV2ByAddress` to extract adapter exposures. Supported adapters:
   - `MorphoMarketV1Adapter`: use `market.loanAsset` and `market.collateralAsset` addresses.
   - `MetaMorphoAdapter`: recursively resolve exposures by querying the nested vault’s adapters.
   Unknown adapter type or incomplete exposure data => exclude.
6. Enforce address allowlist per chain. If any exposure address is not in the allowlist, exclude.
7. Sort by net APY descending, then liquidity descending; take top `limit`.
8. Build vault link using `https://app.morpho.org/{network}/vault/{address}`.

## Error Handling and Verification
- Fail fast on GraphQL errors and report them verbatim.
- Validate `chain` and `limit` inputs with clear error messages.
- If no vaults match, return an empty table and explain why.
- Verification: run a live GraphQL query and the reference script to confirm schema and output.
