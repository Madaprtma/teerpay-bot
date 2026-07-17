# ============================================================
# conditional_config.py — Konfigurasi Conditional Payments
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Arc Testnet ---
ARC_RPC_URL      = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
ARC_CHAIN_ID     = 5042002
ARC_EXPLORER     = "https://testnet.arcscan.app"
USDC_CONTRACT    = "0x3600000000000000000000000000000000000000"
TEERPAY_CONTRACT = "0x5FeD5f971dE23683D1544857DC2F238962822107"
USDC_DECIMALS    = 6

# --- Wallet ---
PRIVATE_KEY    = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# ============================================================
# KONDISI 1: FX RATE THRESHOLDS
# Kirim hanya jika rate USD/{currency} >= threshold
# Naikkan threshold = lebih selektif (hanya kirim saat USD kuat)
# Turunkan threshold = lebih sering kirim
# ============================================================
FX_THRESHOLDS = {
    "Indonesia":   {"currency": "IDR", "min_rate": 15000},
    "Philippines": {"currency": "PHP", "min_rate": 55},
    "Vietnam":     {"currency": "VND", "min_rate": 24000},
    "Nigeria":     {"currency": "NGN", "min_rate": 1500},
    "India":       {"currency": "INR", "min_rate": 83},
}

# ============================================================
# KONDISI 2: SCHEDULE
# Kirim hanya pada hari dan jam tertentu (WIB)
# 0=Senin, 1=Selasa, ..., 6=Minggu
# ============================================================
ALLOWED_DAYS  = [0, 1, 2, 3, 4]   # Senin-Jumat (hari kerja)
ALLOWED_HOURS = (8, 22)            # Jam 08:00-22:00 WIB

# ============================================================
# KONDISI 3: BALANCE
# Selalu sisakan minimum USDC setelah transfer
# ============================================================
MIN_RESERVE_USDC = 1.0   # Sisakan minimal 1 USDC di wallet

# --- Bot Settings ---
DELAY_BETWEEN_TX  = 5    # Detik antar transaksi
CHECK_INTERVAL    = 3600 # Cek kondisi setiap 1 jam (detik) — untuk mode cloud

# --- Remittance Targets ---
REMITTANCE_TARGETS = [
    {
        "country":  "Indonesia",
        "currency": "IDR",
        "address":  "0x018fBE6bB41b6bA47AfBC499b60375117A9373ea",
        "amount":   0.01,
    },
    {
        "country":  "Philippines",
        "currency": "PHP",
        "address":  "0xc68cAA6C024c7d844b0195EBE79aCc9820B4a1a4",
        "amount":   0.01,
    },
    {
        "country":  "Vietnam",
        "currency": "VND",
        "address":  "0xF4E12151430a7D761EF355079f97c7c83AEf512c",
        "amount":   0.01,
    },
    {
        "country":  "Nigeria",
        "currency": "NGN",
        "address":  "0xD4F8F759B80365966fB137E9D27640B5e379ADf6",
        "amount":   0.01,
    },
    {
        "country":  "India",
        "currency": "INR",
        "address":  "0x384f05d832fDebE47C1030CC6935AE3a4325eCd0",
        "amount":   0.01,
    },
]
