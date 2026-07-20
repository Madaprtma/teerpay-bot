# ============================================================
# conditions.py — Kondisi Trigger untuk TeerPay
# "Programmable Money Flow" — kirim USDC hanya jika
# semua kondisi terpenuhi
#
# Analogi trading bot:
#   FX Rate check   = price signal (entry condition)
#   Schedule check  = trading session filter
#   Balance check   = risk management / position sizing
# ============================================================

import urllib.request
import json
import logging
from datetime import datetime, time as dtime

log = logging.getLogger("TeerPayBot")


# ============================================================
# 1. FX RATE CONDITION
# Kirim hanya jika rate menguntungkan (USD kuat)
# Analogi: entry hanya jika RSI di bawah threshold
# ============================================================

# Threshold default per corridor (bisa diubah di config)
DEFAULT_FX_THRESHOLDS = {
    "Indonesia":   {"currency": "IDR", "min_rate": 15000},  # kirim jika 1 USD >= 15000 IDR
    "Philippines": {"currency": "PHP", "min_rate": 55},     # kirim jika 1 USD >= 55 PHP
    "Vietnam":     {"currency": "VND", "min_rate": 24000},  # kirim jika 1 USD >= 24000 VND
    "Nigeria":     {"currency": "NGN", "min_rate": 1500},   # kirim jika 1 USD >= 1500 NGN
    "India":       {"currency": "INR", "min_rate": 83},     # kirim jika 1 USD >= 83 INR
}

def get_fx_rate(currency: str, rpc_url: str = None) -> float:
    """
    Ambil FX rate USD/{currency}.
    
    Priority:
      1. StableFX on-chain (FxEscrow Arc Testnet) — sumber primer
      2. exchangerate-api (API eksternal) — fallback
      3. Simulated rate — last resort
    
    Analogi: primary exchange feed → backup feed → hardcoded price
    """
    # ── 1. StableFX on-chain (primer) ──
    if rpc_url:
        try:
            from stablefx import get_eurc_based_fx_rate
            rate = get_eurc_based_fx_rate(currency, rpc_url)
            if rate and rate > 0:
                log.info(f"  FX Rate (StableFX on-chain): 1 USD = {rate:.2f} {currency}")
                return float(rate)
        except Exception as e:
            log.warning(f"  StableFX fallback to API: {e}")

    # ── 2. API eksternal (fallback) ──
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "TeerPayBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            rate = data["rates"].get(currency)
            if rate:
                log.info(f"  FX Rate (API): 1 USD = {rate} {currency}")
                return float(rate)
    except Exception as e:
        log.warning(f"  FX API error ({e}), using simulated rate")

    # ── 3. Simulated rate (last resort) ──
    simulated = {
        "IDR": 15850.0, "PHP": 56.5, "VND": 25100.0,
        "NGN": 1620.0,  "INR": 84.2,
    }
    rate = simulated.get(currency, 1.0)
    log.info(f"  FX Rate (simulated): 1 USD = {rate} {currency}")
    return rate

def check_fx_condition(country: str, thresholds: dict = None, rpc_url: str = None) -> dict:
    thresholds   = thresholds or DEFAULT_FX_THRESHOLDS
    config       = thresholds.get(country, {})
    currency     = config.get("currency", "USD")
    min_rate     = config.get("min_rate", 0)
    current_rate = get_fx_rate(currency, rpc_url=rpc_url)  # ← tambah rpc_url
    passed       = current_rate >= min_rate

    return {
        "condition": "fx_rate",
        "passed":    passed,
        "currency":  currency,
        "current":   current_rate,
        "threshold": min_rate,
        "detail":    f"1 USD = {current_rate} {currency} (min: {min_rate}) → {'✅' if passed else '❌'}",
    }


# ============================================================
# 2. SCHEDULE CONDITION
# Kirim hanya pada hari/jam yang ditentukan
# Analogi: trading session filter (Asia session only)
# ============================================================

def check_schedule_condition(
    allowed_days: list = None,
    allowed_hours: tuple = (8, 22),
) -> dict:
    """
    Cek apakah sekarang adalah waktu yang diizinkan untuk kirim.
    
    allowed_days: list hari (0=Senin, 6=Minggu). Default: semua hari.
    allowed_hours: tuple (jam_mulai, jam_selesai) dalam WIB (UTC+7).
    """
    now      = datetime.utcnow()
    wib_hour = (now.hour + 7) % 24   # konversi ke WIB
    wib_day  = now.weekday()

    allowed_days = allowed_days if allowed_days is not None else list(range(7))

    day_ok  = wib_day in allowed_days
    hour_ok = allowed_hours[0] <= wib_hour < allowed_hours[1]
    passed  = day_ok and hour_ok

    day_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    return {
        "condition":   "schedule",
        "passed":      passed,
        "current_day": day_names[wib_day],
        "current_hour": wib_hour,
        "allowed_days": [day_names[d] for d in allowed_days],
        "allowed_hours": allowed_hours,
        "detail": (
            f"WIB {wib_hour:02d}:00 {day_names[wib_day]} "
            f"(allowed: {allowed_hours[0]:02d}-{allowed_hours[1]:02d} "
            f"{[day_names[d] for d in allowed_days]}) → {'✅' if passed else '❌'}"
        ),
    }


# ============================================================
# 3. BALANCE CONDITION
# Kirim hanya jika saldo USDC cukup (di atas minimum)
# Analogi: margin check sebelum place order
# ============================================================

def check_balance_condition(
    current_balance: float,
    amount_to_send: float,
    min_reserve: float = 1.0,   # selalu sisakan minimal 1 USDC
) -> dict:
    """
    Cek apakah saldo cukup untuk kirim + reserve.
    
    min_reserve: saldo minimum yang harus tersisa setelah transfer.
    Analogi: jangan habiskan semua modal, sisakan buffer.
    """
    required = amount_to_send + min_reserve
    passed   = current_balance >= required

    return {
        "condition":   "balance",
        "passed":      passed,
        "balance":     current_balance,
        "amount":      amount_to_send,
        "reserve":     min_reserve,
        "required":    required,
        "detail": (
            f"Balance {current_balance:.4f} USDC "
            f"(need {required:.4f} = {amount_to_send} + {min_reserve} reserve) "
            f"→ {'✅' if passed else '❌'}"
        ),
    }


# ============================================================
# MASTER CHECK — semua kondisi harus pass
# Analogi: confluence filter di trading (semua signal harus agree)
# ============================================================

def evaluate_all_conditions(
    country: str,
    current_balance: float,
    amount_to_send: float,
    fx_thresholds: dict = None,
    allowed_days: list = None,
    allowed_hours: tuple = (8, 22),
    min_reserve: float = 1.0,
    rpc_url: str = None,
) -> dict:
    """
    Evaluasi semua kondisi sekaligus.
    Return: dict dengan hasil tiap kondisi + keputusan final.
    
    Analogi: strategy.should_enter_trade() yang cek semua filter
    sebelum place order.
    """
    log.info(f"  Evaluating conditions for {country}...")

    fx_result       = check_fx_condition(country, fx_thresholds, rpc_url=rpc_url)
    schedule_result = check_schedule_condition(allowed_days, allowed_hours)
    balance_result  = check_balance_condition(current_balance, amount_to_send, min_reserve)

    all_passed = fx_result["passed"] and schedule_result["passed"] and balance_result["passed"]

    results = {
        "country":    country,
        "go":         all_passed,   # FINAL DECISION: kirim atau tidak
        "conditions": {
            "fx_rate":  fx_result,
            "schedule": schedule_result,
            "balance":  balance_result,
        },
        "summary": (
            f"FX={'✅' if fx_result['passed'] else '❌'} | "
            f"Schedule={'✅' if schedule_result['passed'] else '❌'} | "
            f"Balance={'✅' if balance_result['passed'] else '❌'} "
            f"→ {'🚀 SEND' if all_passed else '⏸ SKIP'}"
        ),
    }

    log.info(f"  {results['summary']}")
    return results
