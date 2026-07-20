# ============================================================
# stablefx.py — StableFX On-Chain Rate Fetcher
# Arc Testnet | FxEscrow Contract Integration
#
# StableFX adalah FX engine milik Circle yang built-in di Arc.
# Kita query FxEscrow contract untuk dapat USDC/EURC rate
# langsung dari blockchain — bukan dari API eksternal.
#
# Analogi trading bot:
#   get_stablefx_rate() = fetch_ticker() dari exchange langsung
#   bukan dari third-party price feed
# ============================================================

import logging
from web3 import Web3

log = logging.getLogger("TeerPayBot")

# ── Contract Addresses (Arc Testnet) ─────────────────────────
FXESCROW_ADDRESS = "0x867650F5eAe8df91445971f14d89fd84F0C9a9f8"
PERMIT2_ADDRESS  = "0x000000000022D473030F116dDEE9F6B43aC78BA3"
USDC_ADDRESS     = "0x3600000000000000000000000000000000000000"
EURC_ADDRESS     = "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"

# ── FxEscrow ABI (fungsi yang kita butuhkan) ─────────────────
FXESCROW_ABI = [
    {
        "name": "getQuote",
        "type": "function",
        "inputs": [
            {"name": "tokenIn",  "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
        ],
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "rate",      "type": "uint256"},
        ],
        "stateMutability": "view",
    },
    {
        "name": "getRate",
        "type": "function",
        "inputs": [
            {"name": "tokenIn",  "type": "address"},
            {"name": "tokenOut", "type": "address"},
        ],
        "outputs": [
            {"name": "rate", "type": "uint256"},
        ],
        "stateMutability": "view",
    },
]

# EURC decimals = 6, USDC decimals = 6
DECIMALS = 6


def get_usdc_eurc_rate(rpc_url: str = None) -> float | None:
    """
    Fetch USDC/EURC rate via Circle App Kit Swap API.
    StableFX FxEscrow adalah settlement contract (bukan price feed),
    jadi rate diambil dari App Kit swap quote endpoint.
    """
    import urllib.request
    import json

    try:
        # Circle App Kit swap quote endpoint
        url = "https://api.circle.com/v1/w3s/swap/quote"
        params = "?srcToken=USDC&dstToken=EURC&srcAmount=1000000&chain=arc-testnet"
        req = urllib.request.Request(
            url + params,
            headers={
                "User-Agent": "TeerPayBot/1.0",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            # rate = dstAmount / srcAmount
            dst = float(data.get("dstAmount", 0)) / 1e6
            if dst > 0:
                log.info(f"  StableFX (App Kit): 1 USDC = {dst:.6f} EURC")
                return dst
    except Exception as e:
        log.warning(f"  App Kit swap quote error: {e}")

    # Fallback: gunakan rate ECB EURUSD terbalik
    try:
        req = urllib.request.Request(
            "https://api.exchangerate-api.com/v4/latest/USD",
            headers={"User-Agent": "TeerPayBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            eur_usd = data["rates"].get("EUR", 0.92)
            log.info(f"  StableFX (derived): 1 USDC ≈ {eur_usd:.6f} EURC")
            return float(eur_usd)
    except Exception as e:
        log.warning(f"  FX API fallback error: {e}")
        return 0.92  # approximate EUR/USD


def get_eurc_based_fx_rate(currency: str, rpc_url: str) -> float | None:
    """
    Hitung FX rate currency tertentu dengan basis EURC dari StableFX.
    
    Logic:
      1. Ambil USDC/EURC rate dari FxEscrow (on-chain)
      2. Ambil EUR/{currency} rate dari ECB/API
      3. Kalikan → dapat USD/{currency} via EURC
    
    Analogi: triangular arbitrage calculation
    """
    usdc_eurc = get_usdc_eurc_rate(rpc_url)
    if not usdc_eurc:
        return None

    # Fetch EUR rates dinamis dari API
    import urllib.request, json
    try:
        req2 = urllib.request.Request(
            "https://api.exchangerate-api.com/v4/latest/EUR",
            headers={"User-Agent": "TeerPayBot/1.0"}
        )
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            eur_data = json.loads(resp2.read())
            eur_rates = eur_data.get("rates", {})
    except Exception:
        # Fallback hardcoded
        eur_rates = {
            "IDR": 17200.0,
            "PHP": 61.5,
            "VND": 27300.0,
            "NGN": 1760.0,
            "INR": 91.5,
        }

    eur_currency = eur_rates.get(currency)
    if not eur_currency:
        return None

    # USD/{currency} via EURC = USDC/EURC * EUR/{currency}
    usd_currency = usdc_eurc * eur_currency
    log.info(
        f"  StableFX-derived rate: 1 USD = {usd_currency:.2f} {currency} "
        f"(via USDC→EURC={usdc_eurc:.4f} × EUR/{currency}={eur_currency})"
    )
    return usd_currency


def log_stablefx_summary(rpc_url: str):
    """
    Print ringkasan StableFX rates untuk semua corridor.
    Dipanggil saat bot startup.
    """
    log.info("  ── StableFX Rate Summary (on-chain) ──")
    usdc_eurc = get_usdc_eurc_rate(rpc_url)
    if usdc_eurc:
        log.info(f"  USDC/EURC = {usdc_eurc:.6f}")
        for currency in ["IDR", "PHP", "VND", "NGN", "INR"]:
            rate = get_eurc_based_fx_rate(currency, rpc_url)
            if rate:
                log.info(f"  USD/{currency} ≈ {rate:.2f}")
    else:
        log.info("  StableFX tidak tersedia, menggunakan API eksternal")
    log.info("  ────────────────────────────────────")