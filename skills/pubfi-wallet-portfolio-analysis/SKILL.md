---
name: wallet-portfolio-analysis
description: Analyze EVM wallet asset distribution and identify high-risk protocol exposure.
argument-hint: "wallet_address"
status: active
---

# Wallet Portfolio Analysis

> **Goal**: Provide concise asset distribution analysis and risk assessment for EVM wallets.
>

## Inputs

- `wallet_address` (required): EVM address (0x...)

## Data Source

**Primary**: Zerion API via `zerion-portfolio.py`

```bash
# Get all assets
python3 zerion-portfolio.py <address>

# Get only DeFi positions
python3 zerion-portfolio.py <address> --only-defi
```

**Environment**: `ZERION_API_KEY` must be set. If not set, get your API key at: https://www.zerion.io/api

## Execution Workflow

### Step 1: Fetch Portfolio Data

```bash
python3 skills/pubfi-wallet-portfolio-analysis/zerion-portfolio.py <address>
```

Parse JSON response to extract:
- Token holdings (symbol, quantity, USD value, chain)
- DeFi positions (protocol, position type, value)
- Total portfolio value

### Step 2: Categorize Assets

Group assets into:
- **Native tokens**: ETH, MATIC, etc.
- **Stablecoins**: USDC, USDT, DAI, USDS
- **DeFi protocol tokens**: Identified by protocol involvement
- **Other tokens**: Everything else

### Step 3: Risk Assessment

For each DeFi protocol position, check:

**High-Risk Indicators** (🔴):
- Recent exploit (last 90 days) - check rekt.news
- No audit or failed audit
- TVL drop >50% in 30 days
- Known governance issues

**Medium-Risk Indicators** (🟡):
- Single audit only
- New protocol (<6 months)
- TVL drop 20-50% in 30 days
- Centralized control

**Low-Risk Indicators** (🟢):
- Multiple audits from reputable firms
- Battle-tested (>1 year)
- Stable/growing TVL
- Decentralized governance

**Data Sources for Risk**:
- DefiLlama API: `https://api.llama.fi/protocol/{slug}`
- Rekt.news: Recent exploits
- Protocol documentation: Audit reports

### Step 4: Generate Report

Output concise markdown report.

---

## Output Format

### 1) Summary

```
Portfolio: 0x...
Total Value: $X,XXX USD
Chains: Ethereum, Arbitrum, Base
```

### 2) Asset Distribution

```
Asset Breakdown:
• Native: $XXX (XX%)
• Stablecoins: $XXX (XX%)
• DeFi Positions: $XXX (XX%)
• Other Tokens: $XXX (XX%)
```

### 3) Top Positions

Table format showing all positions sorted by value:
```
Protocol/Wallet | Position Type | Value | % Portfolio
----------------|---------------|-------|------------
Wallet Assets   | Wallet        | $XXX  | XX%
Protocol A      | Lending       | $XXX  | XX%
Protocol B      | LP            | $XXX  | XX%
```

### 4) Top Holdings (>2% of portfolio)

Table format:
```
Chain | Asset | Type | Amount | Value | % Portfolio
------|-------|------|--------|-------|------------
```

### 5) DeFi Exposure

For each protocol:

```
Protocol Name (Chain)
• Position Value: $XXX (XX% of portfolio)
• Position Type: Lending/Staking/LP/etc.
• Risk: 🟢/🟡/🔴
• TVL: $XXX (DefiLlama)
• Audit: Yes/No (auditor names)
• Recent Issues: None / [describe]
```

### 6) Risk Summary

**High Priority**:
- List any 🔴 high-risk positions with recommended actions

**Medium Priority**:
- List any 🟡 medium-risk positions with considerations

**Overall Assessment**:
- One paragraph summary
- Risk score: Low/Medium/High

### 7) Data Sources

- Zerion API: Portfolio data (timestamp)
- DefiLlama: Protocol TVL and info
- Rekt.news: Security incidents
- [Other sources used]

---

## Risk Assessment Rules

### Known High-Risk Protocols (as of 2026-02)

Update this list based on recent events:
- Check rekt.news for exploits in last 90 days
- Cross-reference with DefiLlama TVL changes

### Known Safe Protocols

Well-established, audited protocols:
- Aave V2/V3
- Uniswap V2/V3
- Compound V2/V3
- Lido
- Curve
- MakerDAO/Sky

### Protocol Risk Scoring

```
Risk Score = Base Risk + Recent Events + Audit Status + TVL Trend

High Risk (🔴): Score > 7
Medium Risk (🟡): Score 4-7  
Low Risk (🟢): Score < 4

Factors:
- No audit: +5
- Recent exploit: +5
- TVL drop >50%: +3
- TVL drop 20-50%: +2
- New protocol (<6 months): +2
- Single audit: +1
- Multiple audits: -2
- Battle-tested (>1 year): -1
```

---

## Quality Standards

**Conciseness**:
- Total report: 200-400 words (excluding tables)
- Focus on actionable insights only
- No filler or generic statements

**Accuracy**:
- All data must have timestamps
- All values must come from real API calls
- Risk assessments must cite specific evidence

**Usefulness**:
- Highlight positions >5% of portfolio
- Flag any high-risk exposure immediately
- Provide clear next actions if needed

---

## Implementation Notes

### Step-by-Step Execution

1. **Validate input**: Check address format (0x + 40 hex chars)

2. **Fetch data**:
   ```bash
   python3 skills/pubfi-wallet-portfolio-analysis/zerion-portfolio.py $ADDRESS > portfolio.json
   ```

3. **Parse positions**: Extract from JSON
   - Iterate through `data[]` array
   - Get `attributes.fungible_info.symbol`
   - Get `attributes.value` (USD)
   - Get `attributes.chain_id`
   - Get `attributes.quantity`

4. **Identify protocols**: 
   - Look for known DeFi token addresses
   - Check symbol patterns (aUSDC, stETH, etc.)
   - Use position complexity from Zerion

5. **Fetch protocol data** (parallel):
   ```bash
   curl -s "https://api.llama.fi/protocol/{slug}"
   ```

6. **Check recent exploits**:
   - Scan rekt.news for protocol names
   - Last 90 days only

7. **Calculate risk scores**: Apply scoring rules

8. **Generate report**: Follow output format exactly

### Error Handling

- If Zerion API fails: Report error, cannot proceed
- If DefiLlama fails: Mark TVL as "N/A", continue
- If no DeFi positions: Skip DeFi section, report as "No DeFi exposure"
- If zero balance: Report as "Empty wallet"

---

## Update Frequency

- **Risk database**: Update monthly with rekt.news
- **Known protocols**: Update as new major protocols launch
- **Audit status**: Verify quarterly

Last updated: 2026-02-05
