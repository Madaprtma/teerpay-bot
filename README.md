# TeerPay Remittance Bot 🚀

**Cross-border USDC Remittance Protocol on Arc Testnet**

TeerPay is a full-stack USDC remittance protocol built on Arc — Circle's stablecoin-native L1. It exposes reusable primitives for conditional cross-border payments: a Solidity remittance contract, a Python automation bot with FX/schedule/balance filters, and a React frontend with Circle App Kit.

> Built for the [Encode Club Build on Arc Hackathon](https://www.encode.club/) — DeFi Track

---

## Architecture

```
teerpay-bot/                     # This repo — automation layer
├── teerpay_bot.py               # Simple remittance bot (direct ERC-20)
├── teerpay_conditional_bot.py   # Conditional bot (FX + schedule + balance)
├── conditions.py                # Condition evaluators (FX, schedule, balance)
├── stablefx.py                  # StableFX / EURC-based FX rate fetcher
├── conditional_config.py        # Configuration (targets, thresholds)
├── arc_client.py                # Arc Testnet web3 client
└── transactions.csv             # On-chain transaction history

teerpay-web/                     # Frontend repo
└── https://github.com/Madaprtma/teerpay-web
```

**Live site:** https://madaprtma.github.io/teerpay-web  
**Smart contract:** `0x5FeD5f971dE23683D1544857DC2F238962822107` ([ArcScan](https://testnet.arcscan.app/address/0x5FeD5f971dE23683D1544857DC2F238962822107))

---

## Reusable Primitives

These building blocks can be forked independently for any Arc payment application:

### 1. `stablefx.py` — StableFX FX Rate Fetcher
Derives real-time USD/{currency} rates using Circle's EURC/USDC pair as the on-chain FX anchor, with exchangerate-api as fallback.

```python
from stablefx import get_eurc_based_fx_rate

rate = get_eurc_based_fx_rate("IDR", rpc_url)
# → 15050.00 (1 USD = 15050 IDR via USDC→EURC bridge)
```

**How it works:**
1. Fetches USDC/EURC rate from Circle's StableFX engine
2. Fetches EUR/{currency} rate from ECB-sourced API
3. Multiplies → USD/{currency} via EURC triangulation

This is analogous to triangular arbitrage: `USD → EURC → IDR` instead of querying a third-party USD/IDR feed directly.

---

### 2. `conditions.py` — Confluence Filter
Three-condition gate before any payment executes. All must pass — like a trading bot that only enters when all signals agree.

```python
from conditions import evaluate_all_conditions

result = evaluate_all_conditions(
    country="Indonesia",
    current_balance=10.0,
    amount_to_send=0.5,
    rpc_url=RPC_URL,
)
# result["go"] = True/False
# result["summary"] = "FX=✅ | Schedule=✅ | Balance=✅ → 🚀 SEND"
```

| Condition | Logic | Trading Analogy |
|-----------|-------|-----------------|
| FX Rate | Send only if USD is strong vs target currency | Entry signal (RSI threshold) |
| Schedule | Send only on allowed days/hours (WIB) | Trading session filter |
| Balance | Send only if balance > amount + reserve | Margin check / position sizing |

---

### 3. `TeerPayRemittance.sol` — Remittance Smart Contract
Deployable ERC-20 payment contract with recipient registry, on-chain transfer logging, and event emission.

```solidity
function sendRemittance(
    address recipient,
    uint256 amount,
    string calldata country,
    string calldata currency,
    string calldata memo
) external;
```

Fork it as a base for any USDC payment flow on Arc.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Arc Testnet wallet with USDC ([claim here](https://faucet.circle.com))
- Git

### Installation

```bash
git clone https://github.com/Madaprtma/teerpay-bot.git
cd teerpay-bot
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env`:
```env
PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here
ARC_RPC_URL=https://rpc.testnet.arc.network
```

### Run — Simple Mode

```bash
python teerpay_bot.py
```

### Run — Conditional Mode (recommended)

```bash
python teerpay_conditional_bot.py           # run once
python teerpay_conditional_bot.py loop      # 24/7 loop
```

Expected output:
```
2026-07-20 10:00:00 | INFO | CYCLE #1
2026-07-20 10:00:00 | INFO | Wallet balance: 10.0000 USDC
2026-07-20 10:00:01 | INFO | [Indonesia] Evaluating conditions...
2026-07-20 10:00:01 | INFO | FX=✅ | Schedule=✅ | Balance=✅ → 🚀 SEND
2026-07-20 10:00:03 | INFO | ✅ SENT! TX: https://testnet.arcscan.app/tx/0x...
```

---

## Circle Products Used

| Product | Usage |
|---------|-------|
| **USDC on Arc** | Native payment token + gas |
| **EURC on Arc** | FX anchor for StableFX rate derivation |
| **StableFX** | USDC/EURC rate source for conditional payments |
| **Circle App Kit** | Frontend wallet connection + transfers |
| **Arc Testnet** | Settlement layer (Chain ID: 5042002) |

---

## Contract Addresses (Arc Testnet)

| Contract | Address |
|----------|---------|
| TeerPayRemittance | `0x5FeD5f971dE23683D1544857DC2F238962822107` |
| USDC | `0x3600000000000000000000000000000000000000` |
| EURC | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` |
| StableFX FxEscrow | `0x867650F5eAe8df91445971f14d89fd84F0C9a9f8` |

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `PRIVATE_KEY not found` | Check `.env` file, no spaces around `=` |
| `Failed to connect` | Check internet / try public RPC |
| `insufficient funds` | Claim USDC at faucet.circle.com |
| `execution reverted` | Check recipient address (must be valid checksum) |

---

## Trading Bot Analogy

| Trading Bot | TeerPay Bot |
|-------------|-------------|
| Exchange connector | `arc_client.py` |
| Entry signal | FX rate condition |
| Session filter | Schedule condition |
| Position sizing | Balance + reserve check |
| Confluence filter | `evaluate_all_conditions()` |
| Execute order | `send_remittance()` |
| Trade journal | `transactions.csv` |

---

## Related Repos

- **Frontend:** [teerpay-web](https://github.com/Madaprtma/teerpay-web) — React + Circle App Kit
- **Explorer:** [ArcScan](https://testnet.arcscan.app)
- **Reference:** [arc-commerce](https://github.com/circlefin/arc-commerce) | [arc-p2p-payments](https://github.com/circlefin/arc-p2p-payments)

---

## License

MIT — fork freely, build on top, keep it open.
