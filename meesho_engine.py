import os
import sys
import time
import json
import uuid
import base64
import random
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Callable

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import padding

from config import (
    MEESHO_BASE,
    MEESHO_EVENTS_BASE,
    MEESHO_STATIC_KEY,
    GRIZZLY_BASE,
    GRIZZLY_API_KEY,
    NUMERASMS_BASE,
    NUMERASMS_API_KEY,
    TIGERSMS_BASE,
    TIGERSMS_API_KEY,
    NEXNUM_BASE,
    NEXNUM_API_KEY,
    SMSBOWER_BASE,
    SMSBOWER_API_KEY,
    OTPLESS_BASE,
    OTPLESS_APP_ID,
    OTPLESS_APP_SIG,
    OTPLESS_LOGIN_URI,
    OTP_RSA_KEY,
    CALIBRATION_PHONES,
    DEFAULT_MIN_OFFER,
    DEFAULT_REFERRAL_LINK
)

FLAGSHIP_DEVICES = [
    {"brand": "Samsung", "manufacturer": "samsung", "model": "SM-S928B", "device_name": "Galaxy S24 Ultra", "os_version": "14", "sdk_version": "34", "screen_dpi": 505, "screen_width": 1440, "screen_height": 3120, "app_version": "29.1", "app_version_code": "858", "carrier": "Jio"},
    {"brand": "Samsung", "manufacturer": "samsung", "model": "SM-S918B", "device_name": "Galaxy S23 Ultra", "os_version": "14", "sdk_version": "34", "screen_dpi": 500, "screen_width": 1440, "screen_height": 3088, "app_version": "29.1", "app_version_code": "858", "carrier": "Airtel"},
    {"brand": "Google", "manufacturer": "Google", "model": "Pixel 8 Pro", "device_name": "Pixel 8 Pro", "os_version": "14", "sdk_version": "34", "screen_dpi": 480, "screen_width": 1344, "screen_height": 2992, "app_version": "29.1", "app_version_code": "858", "carrier": "Jio"},
    {"brand": "Google", "manufacturer": "Google", "model": "Pixel 9 Pro XL", "device_name": "Pixel 9 Pro XL", "os_version": "14", "sdk_version": "34", "screen_dpi": 486, "screen_width": 1344, "screen_height": 2992, "app_version": "29.1", "app_version_code": "858", "carrier": "Airtel"},
    {"brand": "OnePlus", "manufacturer": "OnePlus", "model": "GM1901", "device_name": "OnePlus 7", "os_version": "12", "sdk_version": "31", "screen_dpi": 450, "screen_width": 1080, "screen_height": 2215, "app_version": "29.1", "app_version_code": "858", "carrier": "BSNL Mobile"},
    {"brand": "OnePlus", "manufacturer": "OnePlus", "model": "CPH2581", "device_name": "OnePlus 12", "os_version": "14", "sdk_version": "34", "screen_dpi": 510, "screen_width": 1440, "screen_height": 3168, "app_version": "29.1", "app_version_code": "858", "carrier": "Jio"},
    {"brand": "Xiaomi", "manufacturer": "Xiaomi", "model": "2210132G", "device_name": "Xiaomi 13 Pro 5G", "os_version": "13", "sdk_version": "33", "screen_dpi": 522, "screen_width": 1440, "screen_height": 3200, "app_version": "29.1", "app_version_code": "858", "carrier": "Jio"},
    {"brand": "Nothing", "manufacturer": "Nothing", "model": "A065", "device_name": "Nothing Phone (2)", "os_version": "14", "sdk_version": "34", "screen_dpi": 394, "screen_width": 1080, "screen_height": 2412, "app_version": "29.1", "app_version_code": "858", "carrier": "Airtel"},
    {"brand": "realme", "manufacturer": "realme", "model": "RMX3850", "device_name": "Realme GT 5 Pro", "os_version": "14", "sdk_version": "34", "screen_dpi": 450, "screen_width": 1264, "screen_height": 2780, "app_version": "29.1", "app_version_code": "858", "carrier": "Jio"},
    {"brand": "vivo", "manufacturer": "vivo", "model": "V2324A", "device_name": "Vivo X100 Pro", "os_version": "14", "sdk_version": "34", "screen_dpi": 452, "screen_width": 1260, "screen_height": 2800, "app_version": "29.1", "app_version_code": "858", "carrier": "Airtel"}
]

INDIAN_ISP_MAP = [
    {"carrier": "BSNL Mobile", "connection_type": "WIFI", "prefix": "117.196"},
    {"carrier": "Jio", "connection_type": "5G", "prefix": "49.36"},
    {"carrier": "Airtel", "connection_type": "5G", "prefix": "106.210"},
    {"carrier": "Vi India", "connection_type": "4G", "prefix": "117.201"},
    {"carrier": "ACT Fibernet", "connection_type": "WIFI", "prefix": "103.115"}
]

TARGET_APP_NAMES = [
    "com.flipkart.android", "com.myntra.android", "in.amazon.mShop.android.shopping",
    "com.bigbasket.mobileapp", "fc.admin.fcexpressadmin", "org.telegram.messenger",
    "com.phonepe.app", "com.whatsapp", "in.swiggy.android", "com.ril.ajio", "com.zeptoconsumerapp"
]


def parse_referral_link(raw_input: str) -> Dict[str, str]:
    """Parses full Meesho referral URL or standalone code into standard attribution metadata."""
    cleaned = (raw_input or "").strip()
    if not cleaned:
        return {"via": "", "shortlink": "", "campaign": "", "media_source": "", "from": "", "full_link": ""}

    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        parsed = urlparse(cleaned)
        qs = parse_qs(parsed.query)
        via_code = qs.get("via", [""])[0]
        from_src = qs.get("from", ["referral_program"])[0]
        path_parts = [p for p in parsed.path.split("/") if p]
        shortlink = path_parts[-1] if path_parts else "r99th0qd"
        return {
            "via": via_code,
            "shortlink": shortlink,
            "campaign": "refferal_acquaint",
            "media_source": "WhatsApp",
            "from": from_src,
            "full_link": cleaned
        }
    else:
        return {
            "via": cleaned,
            "shortlink": "r99th0qd",
            "campaign": "refferal_acquaint",
            "media_source": "WhatsApp",
            "from": "referral_program",
            "full_link": f"https://app.meesho.com/2yoV/r99th0qd?via={cleaned}&from=referral_program"
        }


def load_oracle_session() -> Tuple[Optional[int], Optional[str], Optional[dict], Optional[str]]:
    """Dynamically loads user_id, xo token, and device profile from existing session JSON files."""
    import glob
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    patterns = [
        os.path.join(script_dir, "session_*_meesho.json"),
        "session_*_meesho.json",
        os.path.join(script_dir, "session_*.json"),
        "session_*.json"
    ]
    candidates = []
    for pat in patterns:
        for f in glob.glob(pat):
            if f not in candidates:
                candidates.append(f)

    for fpath in sorted(candidates, key=os.path.getmtime, reverse=True):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > 0:
                data = data[-1]

            if isinstance(data, dict):
                u_id = (data.get("user") or {}).get("user_id") or data.get("user_id") or data.get("distinct_id")
                xo = (
                    data.get("xo")
                    or data.get("xo_token")
                    or (data.get("xoox") or {}).get("xo")
                    or (data.get("raw_session", {}).get("xoox", {}).get("xo"))
                )
                dev = data.get("device_profile") or data.get("device") or {}

                if u_id and xo:
                    return int(u_id), str(xo), dev, os.path.basename(fpath)
        except Exception:
            continue

    return None, None, None, None


class FodOfferHunter:
    def __init__(self, min_offer: int = DEFAULT_MIN_OFFER, ref_meta: Optional[Dict[str, str]] = None):
        self.min_offer = min_offer
        self.ref_meta = ref_meta or parse_referral_link(DEFAULT_REFERRAL_LINK)
        self._server_packages_cache: List[str] = []

    def _build_headers(self, dev: dict, instance_id: str, gaid: str, session_id: str, client_ip: str, xo_token: str = "") -> Dict[str, str]:
        headers = {
            "Authorization": MEESHO_STATIC_KEY,
            "Content-Type": "application/json; charset=UTF-8",
            "country-iso": "in",
            "user-agent": "okhttp/4.9.0",
            "app-sdk-version": str(dev.get("sdk_version", "34")),
            "instance-id": instance_id,
            "shield-session-id": "",
            "app-session-id": session_id,
            "app-session-count": "1",
            "app-client-id": "android",
            "application-id": "com.meesho.supply",
            "meesho-user-context": "anonymous",
            "app-version": dev["app_version"],
            "app-version-code": dev["app_version_code"],
            "accept-encoding": "gzip",
            "app-gaid": gaid,
            "X-Forwarded-For": client_ip,
            "X-Real-IP": client_ip,
            "Client-IP": client_ip
        }
        if xo_token:
            headers["xo"] = xo_token
        return headers

    def _resolve_dynamic_packages(self, headers: dict) -> List[dict]:
        if not self._server_packages_cache:
            try:
                r = requests.get(f"{MEESHO_BASE}/api/1.0/packages", headers=headers, timeout=8)
                if r.status_code == 200:
                    try:
                        pkg_data = r.json()
                    except Exception:
                        pkg_data = {}
                    self._server_packages_cache = pkg_data.get("packages", []) if isinstance(pkg_data, dict) else []
            except Exception:
                pass

        if not self._server_packages_cache:
            return [
                {"id": 101, "package_name": "com.flipkart.android"},
                {"id": 29, "package_name": "com.myntra.android"},
                {"id": 129, "package_name": "com.bigbasket.mobileapp"},
                {"id": 21, "package_name": "org.telegram.messenger"}
            ]

        installed = []
        for idx, pkg in enumerate(self._server_packages_cache):
            if pkg in TARGET_APP_NAMES:
                installed.append({"id": idx, "package_name": pkg})
        return installed

    def _apply_referral_telemetry(self, dev: dict, instance_id: str, gaid: str, session_id: str, xo_token: str, headers: dict):
        """Sends attribution and segment ingestion events to bind referral code."""
        if not self.ref_meta.get("via"):
            return

        now_ms = int(time.time() * 1000)
        via_code = self.ref_meta["via"]
        campaign = self.ref_meta.get("campaign", "refferal_acquaint")
        media_src = self.ref_meta.get("media_source", "WhatsApp")

        events_payload = {
            "events": [
                {
                    "event_id": uuid.uuid4().hex,
                    "event_name": "anonymous_app_open_pre_signup",
                    "user_id": None,
                    "event_time": now_ms,
                    "properties": {
                        "mixpanel_distinct_id": str(uuid.uuid4()),
                        "instance_id": instance_id,
                        "session_id": session_id,
                        "google_advertising_id": gaid,
                        "brand": dev["brand"],
                        "model": dev["model"],
                        "app_version_name": dev["app_version"],
                        "app_version_code": int(dev["app_version_code"]),
                        "install_source": media_src,
                        "install_campaign": campaign,
                        "install_af_status": "Non-organic",
                        "install_af_dp": "supply://open",
                        "via": via_code
                    }
                },
                {
                    "event_id": uuid.uuid4().hex,
                    "event_name": "anonymous_app_installed",
                    "user_id": None,
                    "event_time": now_ms + 250,
                    "properties": {
                        "mixpanel_distinct_id": str(uuid.uuid4()),
                        "google_advertising_id": gaid,
                        "install_source": media_src,
                        "install_campaign": campaign,
                        "install_af_status": "Non-organic",
                        "install_af_dp": "supply://open",
                        "via": via_code
                    }
                }
            ],
            "user_id": None
        }

        try:
            requests.post(f"{MEESHO_EVENTS_BASE}/api/1.0/anonymous/events", json=events_payload, headers=headers, timeout=5)
        except Exception:
            pass

        signals_headers = dict(headers)
        signals_headers["user-agent"] = "CRONET"
        signals_payload = {
            "identity": {"gaid": gaid},
            "signals": {"location": None, "appography": None, "appsflyer": None},
            "experiment_types": ["realtime_user_segment_update"]
        }
        try:
            requests.post(f"{MEESHO_BASE}/api/1.0/signals/ingest", json=signals_payload, headers=signals_headers, timeout=5)
        except Exception:
            pass

    def hunt_top_device(self, max_attempts: int = 40, log_cb: Optional[Callable[[str], None]] = None) -> Tuple[Optional[Dict[str, Any]], str]:
        pool = []
        for _ in range(3):
            sub = list(FLAGSHIP_DEVICES)
            random.shuffle(sub)
            pool.extend(sub)

        result = {"record": None, "desc": ""}
        stop_event = threading.Event()
        lock = threading.Lock()

        def _test_single(dev):
            if stop_event.is_set():
                return
            instance_id = uuid.uuid4().hex
            gaid = str(uuid.uuid4()).upper()
            session_id = str(uuid.uuid4()).upper()
            shield_session_id = uuid.uuid4().hex

            isp = random.choice(INDIAN_ISP_MAP)
            client_ip = f"{isp['prefix']}.{random.randint(1,254)}.{random.randint(1,254)}"
            carrier_name = isp["carrier"]
            conn_type = isp["connection_type"]

            try:
                # 1. Acquire Guest XO Token
                h1 = self._build_headers(dev, instance_id, gaid, session_id, client_ip)
                r1 = requests.get(f"{MEESHO_BASE}/api/1.0/anonymous/config", headers=h1, timeout=6)
                if r1.status_code != 200:
                    return

                try:
                    res1_raw = r1.json()
                except Exception:
                    res1_raw = {}
                res1 = res1_raw if isinstance(res1_raw, dict) else {}
                xo_token = res1.get("xoox", {}).get("xo", "") if isinstance(res1.get("xoox"), dict) else ""
                if not xo_token:
                    return

                # 2. Apply Referral Telemetry & Dynamic Packages
                h2 = self._build_headers(dev, instance_id, gaid, session_id, client_ip, xo_token)
                self._apply_referral_telemetry(dev, instance_id, gaid, session_id, xo_token, h2)
                dynamic_packages = self._resolve_dynamic_packages(h2)

                # 3. Request FOD Personalisation
                init_payload = {
                    "offer_bucket": "",
                    "from_language_modal": False,
                    "brand": dev["brand"],
                    "manufacturer": dev["manufacturer"],
                    "model": dev["model"],
                    "os_version": dev["os_version"],
                    "os": "Android",
                    "carrier": carrier_name,
                    "connection_type": conn_type,
                    "screen_dpi": dev["screen_dpi"],
                    "screen_width": dev["screen_width"],
                    "screen_height": dev["screen_height"],
                    "apps_installed": dynamic_packages
                }

                r3 = requests.post(f"{MEESHO_BASE}/api/1.0/anonymous/fod-personalisation", json=init_payload, headers=h2, timeout=8)
                if r3.status_code != 200:
                    return

                try:
                    res3_raw = r3.json()
                except Exception:
                    res3_raw = {}
                res3 = res3_raw if isinstance(res3_raw, dict) else {}
                fod = res3.get("surgical_first_order_discount_v3")
                if not isinstance(fod, dict):
                    return

                b1 = str(fod.get("offer_bucket", ""))
                off1 = fod.get("offer") if isinstance(fod.get("offer"), dict) else {}
                m1 = str(off1.get("max_offer_value", "?"))
                offer_txt = off1.get("offer_text", "") or f"₹{m1} OFF"
                val = int(m1) if m1.isdigit() else (int(b1) if b1.isdigit() else 0)

                status_desc = f"₹{val} OFF ({offer_txt})"
                if log_cb and not stop_event.is_set():
                    log_cb(f"Tested {dev['brand']} {dev['model']}: {status_desc}")

                if val >= self.min_offer:
                    with lock:
                        if not result["record"]:
                            result["record"] = {
                                "device_profile": dev,
                                "instance_id": instance_id,
                                "gaid": gaid,
                                "session_id": session_id,
                                "shield_session_id": shield_session_id,
                                "xo_token": xo_token,
                                "offer_value": val,
                                "offer_text": offer_txt,
                                "carrier": carrier_name,
                                "connection_type": conn_type,
                                "client_ip": client_ip,
                                "dynamic_packages": dynamic_packages,
                                "referral_metadata": self.ref_meta
                            }
                            result["desc"] = status_desc
                            stop_event.set()
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_test_single, d) for d in pool[:max_attempts]]
            for future in futures:
                if stop_event.is_set():
                    break
                try:
                    future.result(timeout=10)
                except Exception:
                    pass

        if result["record"]:
            return result["record"], result["desc"]

        return None, "Max offer hunt attempts reached"


class SmsRefundManager:
    """
    Manages pending number cancellations and guarantees refunds to the user's wallet.
    Many SMS platforms (GrizzlySMS, TigerSMS, NumeraSMS, SmsBower) enforce a hold period
    (typically 2-3 minutes) before allowing status=8 (ACCESS_CANCEL).

    This manager:
    1. Tries immediate cancellation.
    2. If rejected or pending, schedules retries at 3 minutes (180s) and 6 minutes (360s) from purchase.
    3. Runs continuously in a background daemon thread.
    """
    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.total_refunded = 0
        self.total_queued = 0

    def start(self):
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._worker_loop, daemon=True)
                self._thread.start()

    def queue_cancellation(self, provider: 'SmsProviderClient', act_id: str, phone: str = ""):
        if not provider or not act_id:
            return

        self.total_queued += 1

        # Attempt immediate cancellation first
        try:
            if provider.cancel_number(act_id):
                self.total_refunded += 1
                return
        except Exception:
            pass

        now = time.time()
        # Schedule first retry at ~3 minutes (180s) after purchase
        with self._lock:
            self._queue.append({
                "provider": provider,
                "act_id": act_id,
                "phone": phone,
                "bought_at": now,
                "attempts": 0,
                "next_retry": now + 180  # 3 minutes
            })

    def get_pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    def _worker_loop(self):
        while self._running:
            time.sleep(10)
            now = time.time()
            with self._lock:
                ready_to_retry = []
                remaining = []
                for item in self._queue:
                    if now >= item["next_retry"]:
                        ready_to_retry.append(item)
                    else:
                        remaining.append(item)
                self._queue = remaining

            for item in ready_to_retry:
                provider = item["provider"]
                act_id = item["act_id"]
                phone = item["phone"]
                item["attempts"] += 1
                age_sec = int(now - item["bought_at"])

                try:
                    success = provider.cancel_number(act_id)
                    if success:
                        self.total_refunded += 1
                        continue
                except Exception:
                    pass

                # If still not cancelled, schedule retry at ~6 minutes (360s) after purchase
                if item["attempts"] < 3 and (now - item["bought_at"]) < 450:
                    item["next_retry"] = item["bought_at"] + 360  # 6 minutes from purchase
                    with self._lock:
                        self._queue.append(item)


refund_manager = SmsRefundManager()
refund_manager.start()


def cancel_or_queue_refund(provider: 'SmsProviderClient', act_id: str, phone: str = ""):
    """Cancels immediately or enqueues for retry at 3m and 6m to ensure wallet refund."""
    refund_manager.queue_cancellation(provider, act_id, phone)


class SmsProviderClient:
    def __init__(self, name: str, base_url: str, api_key: str):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key

    def get_balance(self) -> float:
        if not self.api_key:
            return 0.0
        try:
            r = requests.get(f"{self.base_url}?api_key={self.api_key}&action=getBalance", timeout=10)
            text = r.text.strip()
            if text.startswith("ACCESS_BALANCE"):
                return float(text.split(":")[1])
        except Exception:
            pass
        return 0.0

    def get_number(self, service: str = "hp", country: str = "22") -> Tuple[Optional[str], Optional[str]]:
        if not self.api_key:
            return None, None
        url = f"{self.base_url}?api_key={self.api_key}&action=getNumber&service={service}&country={country}"
        try:
            r = requests.get(url, timeout=12)
            resp = r.text.strip()
            if resp.startswith("ACCESS_NUMBER"):
                parts = resp.split(":")
                return parts[1], parts[2]
        except Exception:
            pass
        return None, None

    def cancel_number(self, activation_id: str) -> bool:
        if not self.api_key or not activation_id:
            return False
        url = f"{self.base_url}?api_key={self.api_key}&action=setStatus&status=8&id={activation_id}"
        try:
            r = requests.get(url, timeout=10)
            resp = r.text.strip().upper()
            if "ACCESS_CANCEL" in resp or "STATUS_CANCEL" in resp or resp == "OK":
                return True
            # Also check getStatus if it's already cancelled
            r2 = requests.get(f"{self.base_url}?api_key={self.api_key}&action=getStatus&id={activation_id}", timeout=8)
            resp2 = r2.text.strip().upper()
            if "STATUS_CANCEL" in resp2 or "ACCESS_CANCEL" in resp2:
                return True
        except Exception:
            pass
        return False

    def mark_complete(self, activation_id: str) -> bool:
        if not self.api_key or not activation_id:
            return False
        url = f"{self.base_url}?api_key={self.api_key}&action=setStatus&status=6&id={activation_id}"
        try:
            r = requests.get(url, timeout=10)
            return r.text.strip() == "ACCESS_ACTIVATION"
        except Exception:
            return False

    def wait_for_otp(self, activation_id: str, timeout_seconds: int = 75, poll_interval: int = 2, log_cb: Optional[Callable[[str], None]] = None) -> Optional[str]:
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(f"{self.base_url}?api_key={self.api_key}&action=getStatus&id={activation_id}", timeout=8)
                resp = r.text.strip()
                if resp.startswith("STATUS_OK"):
                    return resp.split(":")[1]
                elif resp == "STATUS_CANCEL":
                    return None
            except Exception:
                pass
            time.sleep(poll_interval)
        return None


def get_all_sms_providers() -> List[SmsProviderClient]:
    return [
        SmsProviderClient("GrizzlySMS", GRIZZLY_BASE, GRIZZLY_API_KEY),
        SmsProviderClient("NumeraSMS", NUMERASMS_BASE, NUMERASMS_API_KEY),
        SmsProviderClient("TigerSMS", TIGERSMS_BASE, TIGERSMS_API_KEY),
        SmsProviderClient("NexNum", NEXNUM_BASE, NEXNUM_API_KEY),
        SmsProviderClient("SmsBower", SMSBOWER_BASE, SMSBOWER_API_KEY),
    ]


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _candidate_hashes(phone10: str) -> List[str]:
    variants = [phone10, "91" + phone10, "+91" + phone10, "91 " + phone10, phone10[:5] + " " + phone10[5:]]
    return [_sha256(v) for v in variants]

def is_phone_registered_on_meesho(phone10: str) -> Optional[bool]:
    """Zero-OTP check for Meesho account existence using oracle session."""
    target = _candidate_hashes(phone10)
    calib_flat = [h for c in CALIBRATION_PHONES for h in _candidate_hashes(c)]
    all_hashes = target + calib_flat

    oracle_user_id, oracle_xo, dev_prof, _ = load_oracle_session()
    if not oracle_user_id or not oracle_xo:
        return None

    dev_prof = dev_prof or {}
    instance_id = dev_prof.get("instance_id") or uuid.uuid4().hex
    gaid = dev_prof.get("gaid") or str(uuid.uuid4()).lower()
    app_session_id = dev_prof.get("app_session_id") or str(uuid.uuid4()).upper()

    headers = {
        "Authorization": MEESHO_STATIC_KEY,
        "Content-Type": "application/json; charset=UTF-8",
        "country-iso": "in",
        "user-agent": "okhttp/4.9.0",
        "app-sdk-version": str(dev_prof.get("sdk_version", "34")),
        "instance-id": instance_id,
        "app-session-id": app_session_id,
        "app-client-id": "android",
        "application-id": "com.meesho.supply",
        "app-version": str(dev_prof.get("app_version", "29.1")),
        "app-version-code": str(dev_prof.get("app_version_code", "858")),
        "app-gaid": gaid,
        "app-user-id": str(oracle_user_id),
        "xo": oracle_xo,
    }

    try:
        sync_payload = {
            "distinct_id": oracle_user_id,
            "phone_book_contacts": [{"name": f"c{i}", "phone": h} for i, h in enumerate(all_hashes)],
            "user_id": oracle_user_id,
        }
        s = requests.post(f"{MEESHO_BASE}/api/1.0/user/phone-book/sync", json=sync_payload, headers=headers, timeout=12)
        if s.status_code != 200:
            return None

        v = requests.post(f"{MEESHO_BASE}/api/2.0/phone-book/verify", json={"phone_book_contacts": all_hashes, "user_id": oracle_user_id}, headers=headers, timeout=12)
        if v.status_code != 200:
            return None

        booleans = v.json().get("phone_book", [])
        if not booleans or len(booleans) != len(all_hashes):
            return None

        n_target = len(target)
        target_bools = booleans[:n_target]
        calib_bools = booleans[n_target:]

        working = [i for i, b in enumerate(calib_bools) if b]
        if not working:
            return None

        return any(target_bools[i % n_target] for i in working)
    except Exception:
        return None


class MeeshoOfferAccountCreator:
    def __init__(self, harvested_device: Dict[str, Any]):
        self.harv = harvested_device
        self.dev = harvested_device["device_profile"]
        self.ref_meta = harvested_device.get("referral_metadata", {})

    def _make_headers(self, xo_token: str = "") -> Dict[str, str]:
        h = {
            "Authorization": MEESHO_STATIC_KEY,
            "Content-Type": "application/json; charset=UTF-8",
            "country-iso": "in",
            "app-iso-language-code": "en",
            "user-agent": "okhttp/4.9.0",
            "app-sdk-version": str(self.dev.get("sdk_version", "34")),
            "instance-id": self.harv["instance_id"],
            "shield-session-id": self.harv["shield_session_id"],
            "app-session-id": self.harv["session_id"],
            "app-session-count": "1",
            "app-client-id": "android",
            "application-id": "com.meesho.supply",
            "meesho-user-context": "anonymous",
            "app-version": str(self.dev.get("app_version", "29.1")),
            "app-version-code": str(self.dev.get("app_version_code", "858")),
            "accept-encoding": "gzip, deflate",
            "app-gaid": self.harv["gaid"],
            "X-Forwarded-For": self.harv.get("client_ip", "49.36.1.1"),
            "X-Real-IP": self.harv.get("client_ip", "49.36.1.1"),
            "Client-IP": self.harv.get("client_ip", "49.36.1.1")
        }
        if xo_token:
            h["xo"] = xo_token
        return h

    def request_otp(self, phone10: str) -> Optional[Dict[str, Any]]:
        clean_phone = "".join(filter(str.isdigit, phone10))
        if len(clean_phone) > 10:
            clean_phone = clean_phone[-10:]
        full_mobile = f"91{clean_phone}"

        now_ms = int(time.time() * 1000)
        tsId = f"{uuid.uuid4().hex}-{now_ms}"
        inId = f"{uuid.uuid4().hex}-{now_ms}"
        gaid = self.harv.get("gaid") or str(uuid.uuid4()).upper()
        android_id = uuid.uuid4().hex[:16]

        dev_info = json.dumps({
            "platform": "android",
            "vendor": self.dev["brand"],
            "browser": "",
            "connection": "",
            "language": "en",
            "cookieEnabled": "",
            "screenWidth": self.dev.get("screen_width", 1080),
            "screenHeight": self.dev.get("screen_height", 2125),
            "userAgent": f"Dalvik/2.1.0 (Linux; U; Android {self.dev.get('os_version', '14')}; {self.dev.get('model', 'SM-S928B')} Build/RKQ1.201217.002) otplesssdk",
            "timezoneOffset": 330,
            "cpuArchitecture": "aarch64"
        }, separators=(",", ":"))

        try:
            state_params = {
                "origin": "https://otpless.com",
                "version": "V3",
                "tsId": tsId,
                "inId": inId,
                "isHeadless": "true",
                "platform": "android",
                "isLoginPage": "false",
                "packageName": "com.meesho.supply",
                "package": "com.meesho.supply",
                "appId": OTPLESS_APP_ID,
                "loginUri": OTPLESS_LOGIN_URI,
                "deviceInfo": dev_info,
            }
            st = requests.get(f"{OTPLESS_BASE}/v2/state", params=state_params, headers={"user-agent": "okhttp/4.9.0"}, timeout=10)
            txn_id = st.json().get("state") if st.status_code == 200 else str(uuid.uuid4())

            tid = "aolplendcndhshdd"
            metadata = json.dumps({
                "appInfo": json.dumps({
                    "platform": "android",
                    "manufacturer": self.dev.get("manufacturer", "samsung"),
                    "androidVersion": str(self.dev.get("sdk_version", "34")),
                    "packageName": "com.meesho.supply",
                    "model": self.dev.get("model", "SM-S928B"),
                    "appSignature": OTPLESS_APP_SIG,
                    "hasTelegram": "true",
                    "hasMiChat": "false",
                    "hasLine": "false",
                    "hasDiscord": "false",
                    "hasSlack": "false",
                    "hasViber": "false",
                    "hasSignal": "false",
                    "hasBotim": "false",
                    "hasTrueCaller": "false",
                    "hasWhatsapp": "false",
                    "sdkVersion": "1.0.9",
                    "inId": inId,
                    "tsId": tsId,
                    "isSilentAuthSupported": "true",
                    "isWebAuthnSupported": "true",
                    "isCellularDataEnabled": "true"
                }),
                "deviceInfo": dev_info,
                "deviceIdInfo": json.dumps({
                    "androidId": android_id,
                    "gaid": gaid
                })
            })

            intent_payload = {
                "selectedCountryCode": "91",
                "mobile": full_mobile,
                "silentAuthEnabled": False,
                "hasWhatsapp": "false",
                "metadata": metadata,
                "triggerWebauthn": False,
                "clientMetaData": json.dumps({"tid": tid}),
                "asId": "",
                "isViSnaWhitelisted": True,
                "isAirtelSnaWhitelisted": True,
                "isAutoIntent": True,
                "origin": "https://otpless.com",
                "version": "V4",
                "tsId": tsId,
                "inId": inId,
                "deviceInfo": dev_info,
                "loginUri": OTPLESS_LOGIN_URI,
                "appId": OTPLESS_APP_ID,
                "isHeadless": True,
                "packageName": "com.meesho.supply",
                "package": "com.meesho.supply",
                "otpHash": OTPLESS_APP_SIG[:12],
                "platform": "HEADLESS"
            }

            r_intent = requests.post(
                f"{OTPLESS_BASE}/v3/lp/user/transaction/intent/{txn_id}",
                json=intent_payload,
                headers={"user-agent": "okhttp/4.9.0", "content-type": "application/json"},
                timeout=12
            )

            if r_intent.status_code == 200:
                intent_data = r_intent.json()
                ql = intent_data.get("quantumLeap", {}) if isinstance(intent_data.get("quantumLeap"), dict) else {}
                ad = intent_data.get("authDetail", {}) if isinstance(intent_data.get("authDetail"), dict) else {}
                auth_token = ql.get("channelAuthToken") or ad.get("token") or intent_data.get("token", "")
                uid = ql.get("uid") or (ad.get("user") or {}).get("uid") or intent_data.get("uid", "")
                asId = ql.get("asId") or ad.get("asId") or intent_data.get("asId", "")

                return {
                    "phone": clean_phone,
                    "txn_id": txn_id,
                    "tsId": tsId,
                    "inId": inId,
                    "dev_info": dev_info,
                    "auth_token": auth_token,
                    "uid": uid,
                    "asId": asId,
                    "android_id": android_id,
                    "xo_token": self.harv["xo_token"],
                    "gaid": gaid
                }
            return None
        except Exception:
            return None

    def verify_otp(self, otp_req_data: Dict[str, Any], otp_code: str) -> Optional[Dict[str, Any]]:
        phone10 = otp_req_data["phone"]
        txn_id = otp_req_data["txn_id"]
        tsId = otp_req_data["tsId"]
        inId = otp_req_data["inId"]
        dev_info = otp_req_data["dev_info"]
        auth_token = otp_req_data.get("auth_token", "")
        uid = otp_req_data.get("uid", "")
        asId = otp_req_data.get("asId", "")
        gaid = otp_req_data.get("gaid", self.harv["gaid"])
        full_mobile = f"91{phone10}"

        try:
            # 1. Otpless OTP Verification
            otp_payload = {
                "selectedCountryCode": "91",
                "mobile": phone10,
                "otp": otp_code,
                "value": full_mobile,
                "isOTPAutoRead": "false",
                "uid": uid,
                "token": auth_token,
                "asId": asId,
                "origin": "https://otpless.com",
                "version": "V4",
                "tsId": tsId,
                "inId": inId,
                "deviceInfo": dev_info,
                "loginUri": OTPLESS_LOGIN_URI,
                "appId": OTPLESS_APP_ID,
                "isHeadless": True,
                "packageName": "com.meesho.supply",
                "package": "com.meesho.supply",
                "otpHash": OTPLESS_APP_SIG[:12],
                "platform": "HEADLESS"
            }

            r_otpless_v = requests.post(
                f"{OTPLESS_BASE}/v3/lp/user/transaction/otp/{txn_id}",
                json=otp_payload,
                headers={"content-type": "application/json; charset=utf-8", "user-agent": "okhttp/4.9.0"},
                timeout=12
            )

            id_token_jwt = None
            merchant_token = None

            if r_otpless_v.status_code == 200:
                d_v = r_otpless_v.json()
                one_tap = d_v.get("oneTap", {}) if isinstance(d_v.get("oneTap"), dict) else {}
                merchant = one_tap.get("merchantUserInfo", {}) if isinstance(one_tap.get("merchantUserInfo"), dict) else {}
                auth_detail = d_v.get("authDetail", {}) if isinstance(d_v.get("authDetail"), dict) else {}
                merchant_token = merchant.get("token") or auth_detail.get("token") or auth_token or d_v.get("token")
                raw_idtoken = merchant.get("idToken") or d_v.get("idToken")
                if raw_idtoken and isinstance(raw_idtoken, str) and len(raw_idtoken.split('.')) == 3:
                    id_token_jwt = raw_idtoken

            if not id_token_jwt or not merchant_token:
                v_body = {
                    "otp": otp_code, "inId": inId, "tsId": tsId,
                    "mobile": full_mobile, "appId": OTPLESS_APP_ID, "origin": "https://otpless.com"
                }
                v_res2 = requests.post(f"{OTPLESS_BASE}/v3/lp/user/transaction/verify/otp/{txn_id}", json=v_body, headers={"user-agent": "okhttp/4.9.0", "content-type": "application/json"}, timeout=12)
                if v_res2.status_code == 200:
                    try:
                        v2_data = v_res2.json()
                    except Exception:
                        v2_data = {}
                    id_token_jwt = v2_data.get("idToken") or id_token_jwt
                    merchant_token = v2_data.get("token") or merchant_token

            if not id_token_jwt or not merchant_token:
                return None

            # 2. AES-GCM and RSA Encryption
            auth_token_final = merchant_token if merchant_token else uuid.uuid4().hex
            aes_key = os.urandom(16)
            nonce = os.urandom(12)
            ct = AESGCM(aes_key).encrypt(nonce, id_token_jwt.encode(), None)
            id_token_b64 = base64.b64encode(nonce + ct).decode()

            pem_str = "-----BEGIN PUBLIC KEY-----\n" + OTP_RSA_KEY + "\n-----END PUBLIC KEY-----"
            pub = load_pem_public_key(pem_str.encode())
            aes_key_enc = base64.b64encode(pub.encrypt(aes_key, padding.PKCS1v15())).decode()

            # 3. Authenticate with Meesho
            meesho_headers = self._make_headers(self.harv["xo_token"])
            login_payload = {
                "login_type": "otpless",
                "otpless": {
                    "token": auth_token_final,
                    "id_token": id_token_b64,
                    "aes_key_encrypted": aes_key_enc,
                    "version": "v2"
                },
                "ga_id": gaid
            }

            m_res = requests.post(f"{MEESHO_BASE}/api/2.0/user/login", json=login_payload, headers=meesho_headers, timeout=12)
            if m_res.status_code in [200, 201]:
                data = m_res.json()
                user_id = (data.get("user") or {}).get("user_id") or data.get("user_id")
                if isinstance(user_id, str) and user_id.isdigit():
                    user_id = int(user_id)

                xoox_obj = data.get("xoox", {})
                auth_xo = xoox_obj.get("xo", "") if isinstance(xoox_obj, dict) else str(xoox_obj)
                ox_token = xoox_obj.get("ox", "") if isinstance(xoox_obj, dict) else ""

                real_offer_value = self.harv["offer_value"]
                real_offer_text = self.harv["offer_text"]

                # Confirm offer from home feed
                try:
                    auth_headers = self._make_headers(auth_xo)
                    auth_headers["meesho-user-context"] = "user"

                    for feed_endpoint in ["/api/2.0/user/home", "/api/1.0/user/home", "/api/2.0/home/feed"]:
                        try:
                            r_home = requests.get(f"{MEESHO_BASE}{feed_endpoint}", headers=auth_headers, timeout=8)
                            if r_home.status_code != 200:
                                continue
                            home_data = r_home.json()
                            if not isinstance(home_data, dict):
                                continue

                            for key in ["fod_offer", "first_order_discount", "surgical_first_order_discount_v3", "fod", "new_user_offer"]:
                                fod_obj = home_data.get(key)
                                if isinstance(fod_obj, dict):
                                    off = fod_obj.get("offer") if isinstance(fod_obj.get("offer"), dict) else fod_obj
                                    val = off.get("max_offer_value") or off.get("offer_value") or off.get("value")
                                    txt = off.get("offer_text") or off.get("text") or ""
                                    if val is not None and str(val).isdigit():
                                        real_offer_value = int(val)
                                        if txt:
                                            real_offer_text = txt
                                        break
                                elif isinstance(fod_obj, list):
                                    for item in fod_obj:
                                        if isinstance(item, dict):
                                            val = item.get("max_offer_value") or item.get("offer_value") or item.get("value")
                                            txt = item.get("offer_text") or item.get("text") or ""
                                            if val is not None and str(val).isdigit():
                                                real_offer_value = int(val)
                                                if txt:
                                                    real_offer_text = txt
                                                break
                                    break
                            if real_offer_value != self.harv["offer_value"]:
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                standardized_account = {
                    "mobile": phone10,
                    "user_id": user_id,
                    "phone": f"+91{phone10}",
                    "xo": auth_xo,
                    "ox": ox_token,
                    "instance_id": self.harv["instance_id"],
                    "gaid": gaid.lower(),
                    "device_profile": self.dev,
                    "harvested_offer": {
                        "offer_value": real_offer_value,
                        "offer_text": real_offer_text
                    },
                    "referral_applied": self.ref_meta,
                    "created_phone": phone10,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "identity": {
                        "instance_id": self.harv["instance_id"],
                        "gaid": gaid.lower(),
                        "android_id": otp_req_data.get("android_id", uuid.uuid4().hex[:16]),
                        "app_session_id": self.harv["session_id"].lower(),
                        "make": self.dev.get("brand", "Samsung"),
                        "model": self.dev.get("model", "SM-S928B"),
                        "android": str(self.dev.get("os_version", "14")),
                        "dalvik_ua": f"Dalvik/2.1.0 (Linux; U; Android {self.dev.get('os_version', '14')}; {self.dev.get('model', 'SM-S928B')}) otplesssdk",
                        "connection_type": self.harv.get("connection_type", "5G"),
                        "carrier": self.harv.get("carrier", "Jio"),
                        "screen_width": self.dev.get("screen_width", 1440),
                        "screen_height": self.dev.get("screen_height", 3120),
                        "screen_dpi": self.dev.get("screen_dpi", 500),
                        "fcm_token": f"{uuid.uuid4().hex[:22]}:APA91b" + uuid.uuid4().hex + uuid.uuid4().hex,
                        "xff": self.harv.get("client_ip", "49.36.1.1"),
                        "anon_xo": self.harv["xo_token"],
                        "_referral_done": True,
                    },
                    "raw_response": data
                }
                return standardized_account
        except Exception:
            pass
        return None


def save_session_file(acc_data: Dict[str, Any]) -> str:
    phone = acc_data.get("created_phone") or (acc_data.get("user") or {}).get("phone") or "unknown"
    clean_digits = "".join(filter(str.isdigit, str(phone)))
    if len(clean_digits) > 10:
        clean_digits = clean_digits[-10:]

    file_path = f"session_{clean_digits}_meesho.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(acc_data, f, indent=2, ensure_ascii=False)
    return file_path


def _get_number_parallel(active_providers: list, timeout: int = 8) -> Optional[Tuple[Any, str, str]]:
    result = {"provider": None, "act_id": None, "full_phone": None}
    done_event = threading.Event()
    lock = threading.Lock()

    def _try_provider(provider):
        if done_event.is_set():
            return
        try:
            act_id, full_phone = provider.get_number(service="hp", country="22")
            if done_event.is_set():
                if act_id:
                    cancel_or_queue_refund(provider, act_id, full_phone or "")
                return
            if act_id and full_phone:
                with lock:
                    if not result["provider"] and not done_event.is_set():
                        result["provider"] = provider
                        result["act_id"] = act_id
                        result["full_phone"] = full_phone
                        done_event.set()
                    else:
                        cancel_or_queue_refund(provider, act_id, full_phone)
        except Exception:
            pass

    threads = []
    for provider in active_providers:
        t = threading.Thread(target=_try_provider, args=(provider,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=timeout)

    if result["provider"]:
        return result["provider"], result["act_id"], result["full_phone"]
    return None


def create_single_account_auto(
    min_offer: int = DEFAULT_MIN_OFFER,
    ref_meta: Optional[Dict[str, str]] = None,
    active_providers: Optional[List[SmsProviderClient]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Automated generation of 1 account with continuous retry until success.
    Returns: (acc_data, session_file_path, error_message)
    """
    ref_meta = ref_meta or parse_referral_link(DEFAULT_REFERRAL_LINK)

    if not active_providers:
        all_provs = get_all_sms_providers()
        active_providers = [p for p in all_provs if p.api_key and p.get_balance() > 0]

    if not active_providers:
        return None, None, "No SMS provider with active balance found."

    # Continuous hunt loop until top offer device is secured
    hunt_attempt = 0
    harvested_dev = None
    offer_desc = ""
    while not harvested_dev:
        if stop_check and stop_check():
            return None, None, "Operation cancelled by user."
        hunt_attempt += 1
        if log_cb:
            log_cb(f"🔍 Hunting FOD offer (≥ ₹{min_offer}) [Cycle #{hunt_attempt}]...")
        hunter = FodOfferHunter(min_offer=min_offer, ref_meta=ref_meta)
        harvested_dev, offer_desc = hunter.hunt_top_device(max_attempts=40)
        if not harvested_dev:
            time.sleep(3)

    dev_name = f"{harvested_dev['device_profile']['brand']} {harvested_dev['device_profile']['model']}"
    if log_cb:
        log_cb(f"🎉 Top Offer Secured: {offer_desc} on [{dev_name}]")

    creator = MeeshoOfferAccountCreator(harvested_dev)
    number_attempts = 0

    # Continuous number & OTP loop until account is successfully generated
    while True:
        if stop_check and stop_check():
            return None, None, "Operation cancelled by user."

        number_attempts += 1
        if log_cb:
            log_cb(f"📱 Acquiring SMS number (Try #{number_attempts} across providers)...")

        result = _get_number_parallel(active_providers, timeout=8)
        if not result:
            time.sleep(4)
            continue

        current_provider, act_id, full_phone = result
        clean_phone = full_phone[-10:]

        if log_cb:
            log_cb(f"📥 Number: +91{clean_phone} ({current_provider.name})")

        # Zero-OTP existence check
        is_registered = is_phone_registered_on_meesho(clean_phone)
        if is_registered is True:
            if log_cb:
                log_cb(f"⚠️ +91{clean_phone} already registered. Auto-refund queued (3m/6m) & retrying...")
            cancel_or_queue_refund(current_provider, act_id, clean_phone)
            time.sleep(1)
            continue

        # Send OTP
        if log_cb:
            log_cb(f"📲 Sending OTP to +91{clean_phone}...")
        otp_req = creator.request_otp(clean_phone)
        if not otp_req:
            if log_cb:
                log_cb(f"⚠️ OTP dispatch failed for +91{clean_phone}. Auto-refund queued & retrying...")
            cancel_or_queue_refund(current_provider, act_id, clean_phone)
            time.sleep(1)
            continue

        # Wait for OTP
        if log_cb:
            log_cb(f"⏳ Waiting for OTP from {current_provider.name} (+91{clean_phone})...")
        otp_code = current_provider.wait_for_otp(act_id, timeout_seconds=75, poll_interval=2)
        if not otp_code:
            if log_cb:
                log_cb(f"⏰ OTP timeout for +91{clean_phone}. Auto-refund queued (3m/6m) & retrying...")
            cancel_or_queue_refund(current_provider, act_id, clean_phone)
            continue

        if log_cb:
            log_cb(f"🔑 OTP received: {otp_code}! Logging in and generating session...")

        acc_result = creator.verify_otp(otp_req, otp_code)
        if acc_result:
            current_provider.mark_complete(act_id)
            file_path = save_session_file(acc_result)
            return acc_result, file_path, None
        else:
            if log_cb:
                log_cb(f"❌ Login verification failed for +91{clean_phone}. Auto-refund queued & retrying...")
            cancel_or_queue_refund(current_provider, act_id, clean_phone)
            time.sleep(1)


def prepare_manual_otp(
    phone10: str,
    min_offer: int = DEFAULT_MIN_OFFER,
    ref_meta: Optional[Dict[str, str]] = None,
    log_cb: Optional[Callable[[str], None]] = None
) -> Tuple[Optional[MeeshoOfferAccountCreator], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Step 1 for manual OTP: Hunts offer and dispatches OTP to user's phone.
    Returns: (creator, otp_req, harvested_dev, error_msg)
    """
    clean_phone = "".join(filter(str.isdigit, phone10))
    if len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]

    if len(clean_phone) != 10:
        return None, None, None, "Invalid phone number. Please provide a 10-digit Indian phone number."

    ref_meta = ref_meta or parse_referral_link(DEFAULT_REFERRAL_LINK)

    if log_cb:
        log_cb(f"🔍 Hunting high discount offer (≥ ₹{min_offer}) for +91{clean_phone}...")

    hunter = FodOfferHunter(min_offer=min_offer, ref_meta=ref_meta)
    harvested_dev, offer_desc = hunter.hunt_top_device(max_attempts=30)
    if not harvested_dev:
        return None, None, None, "Could not secure high FOD discount for device. Please try again."

    dev_name = f"{harvested_dev['device_profile']['brand']} {harvested_dev['device_profile']['model']}"
    if log_cb:
        log_cb(f"🎉 Discount Secured: {offer_desc} on [{dev_name}]\n📲 Dispatching OTP to +91{clean_phone}...")

    creator = MeeshoOfferAccountCreator(harvested_dev)
    otp_req = creator.request_otp(clean_phone)
    if not otp_req:
        return None, None, None, f"Failed to send OTP to +91{clean_phone}. Check number or try again later."

    return creator, otp_req, harvested_dev, None


def complete_manual_otp(
    creator: MeeshoOfferAccountCreator,
    otp_req: Dict[str, Any],
    otp_code: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Step 2 for manual OTP: Verifies OTP code and outputs session JSON file.
    Returns: (acc_data, file_path, error_msg)
    """
    clean_otp = "".join(filter(str.isdigit, otp_code))
    if not clean_otp:
        return None, None, "Invalid OTP code."

    acc_result = creator.verify_otp(otp_req, clean_otp)
    if not acc_result:
        return None, None, "OTP verification or Meesho login failed. Please check the OTP code."

    file_path = save_session_file(acc_result)
    return acc_result, file_path, None
