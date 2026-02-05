---
name: morpho-protocol-leaderboard-conservative
description: Use when you need a conservative Morpho Vaults leaderboard (Ethereum/Base/Arbitrum) filtered by liquidity >$10M and ranked by net APY from the Morpho GraphQL API.
argument-hint: [optional: chain, optional: limit]
status: draft
---

# Morpho Protocol Leaderboard (Conservative)

> **Conservative DeFi Vaults Ranking**

## Overview

Uses Morpho Vaults V2 GraphQL data to fetch vaults on Ethereum, Base, and Arbitrum, apply conservative safety and liquidity filters, and rank by Net APY. No mock data is allowed.

## Rules

**Deposit Assets (Canonical):**
- USDC, USDT, ETH, BTC

**Exposure Assets (Intent):**
- BTC, ETH, WETH, WBTC, cbBTC, cbETH, wstETH, USDS, sUSDS, USDT, USDC

**Safety:**
- `whitelisted` must be true
- `warnings` must be empty

**Thresholds:**
- Minimum Liquidity: $10,000,000 USD (use `liquidityUsd`, fallback `totalAssetsUsd`)
- Net APY: `avgNetApy` > 0

**Target Chains:**
- Ethereum (Chain ID: 1)
- Base (Chain ID: 8453)
- Arbitrum (Chain ID: 42161)

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| chain | string | all | Target chain: ethereum, base, arbitrum, or all |
| limit | number | 10 | Number of vaults to return (1-100) |

## Execution Workflow

### Step 1: Initialize
```yaml
1. Map chain param to chain IDs:
   - ethereum -> [1]
   - base -> [8453]
   - arbitrum -> [42161]
   - all -> [1, 8453, 42161]
2. Set result limit (default: 10, max: 100)
3. If chain == all, plan to query each chain separately and merge results
4. Define canonical deposit assets: USDC, USDT, ETH, BTC
5. Define conservative safety gate: whitelisted == true AND warnings.length == 0
```

### Step 2: Fetch Data (Vaults V2)
```yaml
Source: Morpho GraphQL API
Endpoint: https://api.morpho.org/graphql
```

**GraphQL query (V2):**
```graphql
query VaultsConservative($chainIds: [Int!], $first: Int!) {
  vaultV2s(first: $first, where: { chainId_in: $chainIds }) {
    items {
      address
      symbol
      name
      whitelisted
      warnings { type level }
      chain { id network }
      asset { decimals }
      totalAssets
      totalAssetsUsd
      liquidityUsd
      avgNetApy
    }
  }
}
```

**Example variables:**
```json
{ "chainIds": [1, 8453, 42161], "first": 200 }
```

**If `chain=all`, run the query once per chain to avoid timeouts, then merge results.**

**If a chain returns exactly 200 items, consider pagination or a larger `first` for that chain.**

### Step 3: Normalize and Filter
```yaml
Normalization:
  - liquidityUsd := liquidityUsd ?? totalAssetsUsd
  - if liquidityUsd is null AND depositAsset in [USDC, USDT]:
      liquidityUsd := totalAssets / (10 ^ asset.decimals)
  - if liquidityUsd is still null, exclude (cannot verify $10M threshold)
  - netApyPct := avgNetApy * 100
  - depositAsset := infer from symbol/name (uppercase):
      * if contains USDC -> USDC
      * else if contains USDT -> USDT
      * else if contains WBTC or CBBTC or BTC -> BTC
      * else if contains WSTETH or CBETH or WETH or ETH -> ETH
      * else -> UNKNOWN (exclude)

Filtering:
  - whitelisted == true
  - warnings.length == 0
  - liquidityUsd >= 10_000_000
  - avgNetApy > 0
  - depositAsset in [USDC, USDT, ETH, BTC]
```

### Step 4: Sort and Rank
```yaml
Sorting:
  - Primary: avgNetApy (descending)
  - Secondary: liquidityUsd (descending)

Take:
  - Top N = limit
```

### Step 5: Build Vault Link
```yaml
link := https://app.morpho.org/{network}/vault/{address}
# network comes from chain.network; lowercase it for URL safety
```

### Step 6: Reference Script (Python)
```bash
# Optional: run end-to-end without guessing
# CHAIN=all LIMIT=10 FIRST=200
python - <<'PY'
import json, os, sys, urllib.request
from datetime import datetime, timezone

QUERY = """
query VaultsConservative($chainIds: [Int!], $first: Int!) {
  vaultV2s(first: $first, where: { chainId_in: $chainIds }) {
    items {
      address
      symbol
      name
      whitelisted
      warnings { type level }
      chain { id network }
      asset { decimals }
      totalAssets
      totalAssetsUsd
      liquidityUsd
      avgNetApy
    }
  }
}
"""

CHAIN_MAP = {
    "ethereum": [1],
    "base": [8453],
    "arbitrum": [42161],
    "all": [1, 8453, 42161],
}

chain = os.getenv("CHAIN", "all").lower()
limit = int(os.getenv("LIMIT", "10"))
first = int(os.getenv("FIRST", "200"))
chain_ids = CHAIN_MAP.get(chain)
if not chain_ids:
    raise SystemExit("Invalid CHAIN. Use: ethereum, base, arbitrum, all")

def infer_deposit_asset(symbol: str, name: str):
    merged = ((symbol or "") + " " + (name or "")).upper()
    if "USDC" in merged:
        return "USDC"
    if "USDT" in merged:
        return "USDT"
    if "WBTC" in merged or "CBBTC" in merged or "BTC" in merged:
        return "BTC"
    if "WSTETH" in merged or "CBETH" in merged or "WETH" in merged or "ETH" in merged:
        return "ETH"
    return None

def fetch(chain_id: int):
    payload = json.dumps({"query": QUERY, "variables": {"chainIds": [chain_id], "first": first}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.morpho.org/graphql",
        data=payload,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    items = data["data"]["vaultV2s"]["items"]
    if len(items) == first:
        print(f"Warning: chain {chain_id} returned {first} items; consider pagination.", file=sys.stderr)
    return items

items = []
for cid in chain_ids:
    items.extend(fetch(cid))

results = []
for v in items:
    if not v.get("whitelisted"):
        continue
    if v.get("warnings"):
        continue
    deposit = infer_deposit_asset(v.get("symbol"), v.get("name"))
    if deposit not in {"USDC", "USDT", "ETH", "BTC"}:
        continue
    liquidity = v.get("liquidityUsd") or v.get("totalAssetsUsd")
    if liquidity is None and deposit in ("USDC", "USDT"):
        decimals = (v.get("asset") or {}).get("decimals") or 0
        total_assets = v.get("totalAssets")
        if total_assets is not None:
            liquidity = total_assets / (10 ** decimals)
    if liquidity is None or liquidity < 10_000_000:
        continue
    avg_net_apy = v.get("avgNetApy")
    if avg_net_apy is None or avg_net_apy <= 0:
        continue
    results.append({
        "name": v.get("name") or v.get("symbol"),
        "symbol": v.get("symbol"),
        "chain": v.get("chain", {}).get("network"),
        "deposit": deposit,
        "net_apy_pct": avg_net_apy * 100,
        "liquidity": liquidity,
        "address": v.get("address"),
    })

results.sort(key=lambda r: (-r["net_apy_pct"], -r["liquidity"]))
results = results[:limit]

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
print("# Morpho Protocol Leaderboard (Conservative)")
print("")
print("> Top Vaults by Net APY")
print(f"> Chains: {chain.title()} | Updated: {ts}")
print("> Filters: Liquidity >$10M USD | whitelisted only | no warnings")
print("\n---\n")
print("## Top Vaults\n")
print("| Rank | Vault | Deposit Asset | Chain | Net APY | Liquidity | Exposure | Link |")
print("|------|-------|---------------|-------|---------|-----------|----------|------|")
for i, r in enumerate(results, 1):
    chain_slug = (r['chain'] or '').lower()
    link = f"https://app.morpho.org/{chain_slug}/vault/{r['address']}"
    print(f"| {i} | {r['name']} | {r['deposit']} | {r['chain']} | {r['net_apy_pct']:.2f}% | ${r['liquidity']/1e6:.1f}M | N/A (V2) | {link} |")
PY
```

## Output Format

```markdown
# Morpho Protocol Leaderboard (Conservative)

> Top Vaults by Net APY
> Chains: Ethereum, Base, Arbitrum | Updated: 2026-02-05 14:00 UTC
> Filters: Liquidity >$10M USD | whitelisted only | no warnings

---

## Top Vaults

| Rank | Vault | Deposit Asset | Chain | Net APY | Liquidity | Exposure | Link |
|------|-------|---------------|-------|---------|-----------|----------|------|
| 1 | Example Vault A | USDC | Ethereum | 4.75% | $43.4M | N/A (V2) | https://app.morpho.org/ethereum/vault/0x... |
| 2 | Example Vault B | ETH | Base | 3.92% | $32.1M | N/A (V2) | https://app.morpho.org/base/vault/0x... |

---

### Summary

- Total Vaults: 2
- Average APY: 4.33%
- Highest APY: 4.75% (Example Vault A)

---

*Generated by Morpho Protocol Leaderboard*
*Data Source: Morpho GraphQL API*
```

## Error Handling

| Error | Action |
|-------|--------|
| GraphQL error | Return error payload and stop |
| API Timeout | Retry once with exponential backoff |
| Invalid Chain | Return valid options: ethereum, base, arbitrum, all |
| No Vaults Found | Return empty table with explanation |

## Notes

- Exposure assets are not directly available in the Vaults V2 API. The conservative filter is enforced via `whitelisted` and `warnings` instead.
- `avgNetApy` is a decimal rate; multiply by 100 for percentage output.
- Prefer `liquidityUsd` and fallback to `totalAssetsUsd` when missing; if both are null, compute USD only for stablecoins using `totalAssets / 10^decimals`.
