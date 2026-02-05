---
name: morpho-protocol-leaderboard-conservative
description: Use when you need a conservative Morpho Vaults leaderboard (Ethereum/Base/Arbitrum) with exposure-asset allowlist enforcement, filtered by liquidity >$10M and ranked by net APY.
argument-hint: [optional: chain, optional: limit]
status: draft
---

# Morpho Protocol Leaderboard (Conservative)

> **Conservative DeFi Vaults Ranking**

## Overview

Uses Morpho Vaults V2 GraphQL data to fetch vaults on Ethereum, Base, and Arbitrum, enforce strict exposure-asset **address** allowlists, apply conservative safety and liquidity filters, and rank by Net APY. Exposure enforcement relies on V2 adapter data: `MetaMorphoAdapter` (recursive vault exposure) and `MorphoMarketV1Adapter` (loan/collateral assets). No mock data is allowed.

## Rules

**Deposit Assets (Canonical):**
- USDC, USDT, ETH, BTC
- Deposit asset is determined by `vault.asset.address` and mapped to symbols via the address allowlist.
- `WETH -> ETH`, `WBTC/cbBTC -> BTC` for deposit normalization.

**Exposure Assets (Enforced by Address):**
- BTC, ETH, WETH, WBTC, cbBTC, cbETH, wstETH, USDS, sUSDS, USDT, USDC
- Any adapter exposure address outside the allowlist **excludes** the vault.

**Safety:**
- `whitelisted` must be true
- `warnings` must be empty

**Thresholds:**
- Minimum Liquidity: $10,000,000 USD (use `totalAssetsUsd`, fallback to `totalAssets / 10^decimals` for USDC/USDT)
- Net APY: `netApy` > 0

**Target Chains:**
- Ethereum (Chain ID: 1)
- Base (Chain ID: 8453)
- Arbitrum (Chain ID: 42161)

## Address Allowlists (by Chain)

**Ethereum (1)**
- USDC: `0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48`
- USDT: `0xdac17f958d2ee523a2206206994597c13d831ec7`
- WETH: `0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2`
- WBTC: `0x2260fac5e5542a773aa44fbcfedf7c193bc2c599`
- cbBTC: `0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf`
- cbETH: `0xbe9895146f7af43049ca1c1ae358b0541ea49704`
- wstETH: `0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0`
- USDS: `0xdc035d45d973e3ec169d2276ddab16f1e407384f`
- sUSDS: `0xa3931d71877c0e7a3148cb7eb4463524fec27fbd`

**Base (8453)**
- USDC: `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913`
- USDT: `0xfde4c96c8593536e31f229ea8f37b2ada2699bb2`
- WETH: `0x4200000000000000000000000000000000000006`
- WBTC: `0x0555e30da8f98308edb960aa94c0db47230d2b9c`
- cbBTC: `0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf`
- cbETH: `0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22`
- wstETH: `0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452`
- USDS: `0x820c137fa70c8691f0e44dc420a5e53c168921dc`
- sUSDS: `0x5875eee11cf8398102fdad704c9e96607675467a`

**Arbitrum (42161)**
- USDC: `0xaf88d065e77c8cc2239327c5edb3a432268e5831`
- USDT: `0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9`
- WETH: `0x82af49447d8a07e3bd95bd0d56f35241523fbab1`
- WBTC: `0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f`
- cbBTC: `0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf`
- cbETH: `0x1debd73e752beaf79865fd6446b0c970eae7732f`
- wstETH: `0x5979d7b546e38e414f7e9822514be443a4800529`
> Note: USDS/sUSDS are listed for Ethereum and Base in Sky's official deployments tracker. They are omitted for Arbitrum to avoid guessing.

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
3. If chain == all, query each chain separately and merge results
4. Enable pagination with `skip` and `first` for vault lists (default: first=200)
5. Load address allowlists for each chain (see above)
6. Conservative safety gate: whitelisted == true AND warnings.length == 0
```

### Step 2: Fetch Data (Vaults V2)
```yaml
Source: Morpho GraphQL API
Endpoint: https://api.morpho.org/graphql
```

**GraphQL query (V2 list):**
```graphql
query VaultV2s($chainIds: [Int!], $first: Int!, $skip: Int!) {
  vaultV2s(
    where: { chainId_in: $chainIds }
    first: $first
    skip: $skip
    orderBy: TotalAssetsUsd
    orderDirection: Desc
  ) {
    items {
      address
      name
      symbol
      chain { id network }
      asset { address symbol decimals }
      totalAssets
      totalAssetsUsd
      netApy
      whitelisted
      warnings { type level }
    }
    pageInfo { countTotal count skip limit }
  }
}
```

**Example variables:**
```json
{ "chainIds": [1, 8453, 42161], "first": 200, "skip": 0 }
```

### Step 3: Pre-Filter
```yaml
Normalization:
  - depositAddress := vault.asset.address (lowercase)
  - depositSymbol := map address -> symbol via allowlist
  - depositCanonical :=
      * WETH -> ETH
      * WBTC/cbBTC -> BTC
      * else -> same
  - liquidityUsd := totalAssetsUsd
  - if liquidityUsd is null AND depositCanonical in [USDC, USDT]:
      liquidityUsd := totalAssets / (10 ^ asset.decimals)

Filtering:
  - whitelisted == true
  - warnings.length == 0
  - liquidityUsd >= 10_000_000
  - netApy > 0
  - depositCanonical in [USDC, USDT, ETH, BTC]
```

### Step 4: Fetch Exposures (Adapters)
Use adapter-specific fields to extract exposure assets. Any unknown adapter type or missing data => exclude vault.

**GraphQL query (V2 exposure by address):**
```graphql
query VaultV2Exposure($address: String!, $chainId: Int!, $positionsFirst: Int!) {
  vaultV2ByAddress(address: $address, chainId: $chainId) {
    adapters {
      items {
        __typename
        type
        ... on MetaMorphoAdapter {
          metaMorpho {
            address
            asset { address symbol }
          }
        }
        ... on MorphoMarketV1Adapter {
          positions(first: $positionsFirst) {
            items {
              market {
                loanAsset { address symbol }
                collateralAsset { address symbol }
              }
            }
          }
        }
      }
    }
  }
}
```

**Exposure rules:**
- `MetaMorphoAdapter`: recursively resolve exposures from the nested `metaMorpho.address` vault.
- If the nested vault cannot be queried, fall back to `metaMorpho.asset.address` and log a warning.
- `MorphoMarketV1Adapter`: collect `loanAsset.address` and `collateralAsset.address` from all positions.
- If positions length == `positionsFirst`, treat as possibly truncated => exclude vault (conservative).
- If any exposure address is not in the chain allowlist => exclude vault.

### Step 5: Sort and Rank
```yaml
Sorting:
  - Primary: netApy (descending)
  - Secondary: liquidityUsd (descending)
Take:
  - Top N = limit
```

### Step 6: Build Vault Link
```yaml
link := https://app.morpho.org/{network}/vault/{address}
# network comes from chain.network; lowercase it for URL safety
```

### Step 7: Reference Script (Python)
```bash
# Optional: run end-to-end without guessing
# CHAIN=all LIMIT=10 FIRST=200 SKIP=0 POSITIONS_FIRST=200
python - <<'PY'
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

GRAPHQL = "https://api.morpho.org/graphql"

VAULTS_QUERY = """
query VaultV2s($chainIds: [Int!], $first: Int!, $skip: Int!) {
  vaultV2s(
    where: { chainId_in: $chainIds }
    first: $first
    skip: $skip
    orderBy: TotalAssetsUsd
    orderDirection: Desc
  ) {
    items {
      address
      name
      symbol
      chain { id network }
      asset { address symbol decimals }
      totalAssets
      totalAssetsUsd
      netApy
      whitelisted
      warnings { type level }
    }
    pageInfo { countTotal count skip limit }
  }
}
"""

EXPOSURE_QUERY = """
query VaultV2Exposure($address: String!, $chainId: Int!, $positionsFirst: Int!) {
  vaultV2ByAddress(address: $address, chainId: $chainId) {
    adapters {
      items {
        __typename
        type
        ... on MetaMorphoAdapter {
          metaMorpho {
            address
            asset { address symbol }
          }
        }
        ... on MorphoMarketV1Adapter {
          positions(first: $positionsFirst) {
            items {
              market {
                loanAsset { address symbol }
                collateralAsset { address symbol }
              }
            }
          }
        }
      }
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

ALLOWLIST = {
    1: {
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0xbe9895146f7af43049ca1c1ae358b0541ea49704": "CBETH",
        "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "WSTETH",
        "0xdc035d45d973e3ec169d2276ddab16f1e407384f": "USDS",
        "0xa3931d71877c0e7a3148cb7eb4463524fec27fbd": "SUSDS",
    },
    8453: {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "USDC",
        "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2": "USDT",
        "0x4200000000000000000000000000000000000006": "WETH",
        "0x0555e30da8f98308edb960aa94c0db47230d2b9c": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": "CBETH",
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": "WSTETH",
        "0x820c137fa70c8691f0e44dc420a5e53c168921dc": "USDS",
        "0x5875eee11cf8398102fdad704c9e96607675467a": "SUSDS",
    },
    42161: {
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT",
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": "WETH",
        "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0x1debd73e752beaf79865fd6446b0c970eae7732f": "CBETH",
        "0x5979d7b546e38e414f7e9822514be443a4800529": "WSTETH",
    },
}

DEPOSIT_ALLOW = {"USDC", "USDT", "ETH", "BTC"}

chain = os.getenv("CHAIN", "all").lower()
limit = int(os.getenv("LIMIT", "10"))
first = int(os.getenv("FIRST", "200"))
skip = int(os.getenv("SKIP", "0"))
positions_first = int(os.getenv("POSITIONS_FIRST", "200"))

chain_ids = CHAIN_MAP.get(chain)
if not chain_ids:
    raise SystemExit("Invalid CHAIN. Use: ethereum, base, arbitrum, all")

limit = max(1, min(limit, 100))


def gql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(GRAPHQL, data=payload, headers={"content-type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt == 0:
                time.sleep(1.5)
                continue
            raise
        except urllib.error.URLError:
            if attempt == 0:
                time.sleep(1.5)
                continue
            raise


def canonical_deposit(symbol: str) -> str:
    if symbol == "WETH":
        return "ETH"
    if symbol in ("WBTC", "CBBTC"):
        return "BTC"
    return symbol


def fetch_vaults(chain_id: int):
    items = []
    page = 0
    while True:
        offset = skip + page * first
        data = gql(VAULTS_QUERY, {"chainIds": [chain_id], "first": first, "skip": offset})
        batch = data["vaultV2s"]["items"]
        items.extend(batch)
        if len(batch) < first:
            break
        page += 1
    return items


exposure_cache = {}


def resolve_exposures(vault_address: str, chain_id: int, seen=None):
    key = (chain_id, vault_address.lower())
    if key in exposure_cache:
        return exposure_cache[key]
    if seen is None:
        seen = set()
    if key in seen:
        exposure_cache[key] = (set(), True)
        return exposure_cache[key]
    seen.add(key)

    try:
        data = gql(EXPOSURE_QUERY, {"address": vault_address, "chainId": chain_id, "positionsFirst": positions_first})
    except Exception as exc:
        print(f"Warning: exposure query failed for {vault_address} on {chain_id}: {exc}", file=sys.stderr)
        exposure_cache[key] = (set(), True)
        return exposure_cache[key]
    vault = data.get("vaultV2ByAddress") or {}
    adapters = (vault.get("adapters") or {}).get("items") or []

    exposures = set()
    unknown = False

    for adapter in adapters:
        typename = adapter.get("__typename")
        if typename == "MetaMorphoAdapter":
            meta = adapter.get("metaMorpho") or {}
            meta_addr = (meta.get("address") or "").lower()
            asset_addr = ((meta.get("asset") or {}).get("address") or "").lower()
            if meta_addr:
                nested, nested_unknown = resolve_exposures(meta_addr, chain_id, seen)
                if not nested_unknown:
                    exposures.update(nested)
                    continue
            if asset_addr:
                exposures.add(asset_addr)
                print(f"Warning: MetaMorpho fallback to asset address for {meta_addr or vault_address}", file=sys.stderr)
                continue
            unknown = True
        elif typename == "MorphoMarketV1Adapter":
            positions = (adapter.get("positions") or {}).get("items") or []
            if len(positions) >= positions_first:
                unknown = True
                continue
            for pos in positions:
                market = (pos or {}).get("market") or {}
                for key in ("loanAsset", "collateralAsset"):
                    addr = ((market.get(key) or {}).get("address") or "").lower()
                    if not addr:
                        unknown = True
                        continue
                    exposures.add(addr)
        else:
            unknown = True

    if not exposures:
        unknown = True

    exposure_cache[key] = (exposures, unknown)
    return exposure_cache[key]


results = []
for cid in chain_ids:
    allow = ALLOWLIST.get(cid, {})
    for v in fetch_vaults(cid):
        if not v.get("whitelisted"):
            continue
        if v.get("warnings"):
            continue

        asset = v.get("asset") or {}
        deposit_addr = (asset.get("address") or "").lower()
        deposit_symbol = allow.get(deposit_addr)
        if not deposit_symbol:
            continue
        deposit_canon = canonical_deposit(deposit_symbol)
        if deposit_canon not in DEPOSIT_ALLOW:
            continue

        liquidity = v.get("totalAssetsUsd")
        if liquidity is None and deposit_canon in ("USDC", "USDT"):
            total_assets = v.get("totalAssets")
            decimals = asset.get("decimals") or 0
            if total_assets is not None:
                liquidity = total_assets / (10 ** decimals)
        if liquidity is None or liquidity < 10_000_000:
            continue

        net_apy = v.get("netApy")
        if net_apy is None or net_apy <= 0:
            continue

        exposures, unknown = resolve_exposures(v.get("address"), cid)
        if unknown:
            continue
        if not exposures.issubset(set(allow.keys())):
            continue

        exposure_symbols = sorted({allow[a] for a in exposures if a in allow})
        results.append({
            "name": v.get("name") or v.get("symbol") or v.get("address"),
            "symbol": v.get("symbol"),
            "chain": (v.get("chain") or {}).get("network"),
            "deposit": deposit_canon,
            "exposures": exposure_symbols,
            "net_apy_pct": net_apy * 100,
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
if not results:
    print("| - | No vaults matched filters | - | - | - | - | - | - |")
else:
    for i, r in enumerate(results, 1):
        chain_slug = (r["chain"] or "").lower()
        link = f"https://app.morpho.org/{chain_slug}/vault/{r['address']}"
        exposure_str = ", ".join(r["exposures"]) if r["exposures"] else "-"
        print(f"| {i} | {r['name']} | {r['deposit']} | {r['chain']} | {r['net_apy_pct']:.2f}% | ${r['liquidity']/1e6:.1f}M | {exposure_str} | {link} |")
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
| 1 | Example Vault A | USDC | Ethereum | 4.75% | $43.4M | USDT, sUSDS | https://app.morpho.org/ethereum/vault/0x... |
| 2 | Example Vault B | ETH | Base | 3.92% | $32.1M | WETH, wstETH | https://app.morpho.org/base/vault/0x... |

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
| Unknown adapter type | Exclude vault (conservative) |
| No Vaults Found | Return table with a single row: `No vaults matched filters` |

## Notes

- Exposure assets are enforced via V2 adapters. `MorphoMarketV1Adapter` uses loan/collateral asset addresses, `MetaMorphoAdapter` is resolved recursively via nested vault adapters.
- If a MetaMorpho nested vault cannot be queried, the script falls back to the nested vault asset address with a warning.
- `netApy` is a decimal rate; multiply by 100 for percentage output.
- Prefer `totalAssetsUsd`; fallback to `totalAssets / 10^decimals` for USDC/USDT only.
- ETH/BTC are represented via their wrapped tokens (WETH/WBTC/cbBTC) in address-based filters.
- Arbitrum uses the USD₮0 (USDT) token contract address for USDT allowlisting.
- USDS/sUSDS are only included for Ethereum and Base (per Sky deployments tracker).
- Exposure query failures are logged and treated as unknown, which excludes the vault.
