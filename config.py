import os

# ─────────────────────────────────────────────────────────────
# 🔑 TELEGRAM BOT & API KEYS CONFIGURATION
# Reads from Environment Variables with fallbacks
# ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8908238181:AAFDaBABB1Bj-PgCDalr8jvZPXNhgE6ukKo")

# SMS Provider API Keys
GRIZZLY_API_KEY = os.getenv("GRIZZLY_API_KEY", "804def05f9fa4a8469bf9704f1edfa73")
NUMERASMS_API_KEY = os.getenv("NUMERASMS_API_KEY", "a0b9fbacc969d22984f613334f028bed0d44")
TIGERSMS_API_KEY = os.getenv("TIGERSMS_API_KEY", "OulvxGKfZ31ObBxxck16WeaAM6VXbS6u")
NEXNUM_API_KEY = os.getenv("NEXNUM_API_KEY", "nxn_live_jtgqj2nmTekopnltsG8E9DpKoAe_9m2s")
SMSBOWER_API_KEY = os.getenv("SMSBOWER_API_KEY", "JDvqNuzbtpc2YB6t52TrNOdLZdtu50xQ")

# 🔗 DEFAULT MEESHO REFERRAL LINK / CODE
DEFAULT_REFERRAL_LINK = os.getenv(
    "MEESHO_REFERRAL_LINK",
    "https://app.meesho.com/2yoV/r99th0qd?via=i5bxd&from=home_page_pill"
)

# STRICT MINIMUM DISCOUNT (e.g., 180, 150, 200)
DEFAULT_MIN_OFFER = int(os.getenv("MIN_OFFER_DISCOUNT", "180"))

# PORT for Render Web Service (to keep service alive 24/7)
PORT = int(os.getenv("PORT", "10000"))

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
MEESHO_BASE = "https://prod.meeshoapi.com"
MEESHO_EVENTS_BASE = "https://events.meeshoapi.com"
MEESHO_STATIC_KEY = "32c4d8137cn9eb493a1921f203173080"

GRIZZLY_BASE = "https://api.grizzlysms.com/stubs/handler_api.php"
NUMERASMS_BASE = "https://api.numerasms.com/stubs/handler_api.php"
TIGERSMS_BASE = "https://api.tiger-sms.com/stubs/handler_api.php"
NEXNUM_BASE = "https://nexnum.in/stubs/handler_api.php"
SMSBOWER_BASE = "https://smsbower.page/stubs/handler_api.php"

OTPLESS_BASE = "https://user-auth.otpless.app"
OTPLESS_APP_ID = "XN07RN1IQC548C9YK5I4"
OTPLESS_APP_SIG = "oBcOM6bXKNcqouiPFcR1ur60Z6myTuVIDNSNWuKOlzU"
OTPLESS_LOGIN_URI = "otpless.xn07rn1iqc548c9yk5i4://otpless"
OTP_RSA_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAslmrLKGRzVnAtii3o89y"
    "I33FXZoRfBJV89PaCTp9Mxu7FgAaAOtaOnB2xWGG2a6Rz6zRzKPilRdAsm5oBW8m"
    "m8Uzvt7mbf7c7pjfBrjNdnKji/9/zM3fpjh364/GwG3OpyYngD49i09ySljA7Elh"
    "97Pp+QJH2z25Xv2eRSHJPizgQ8TE1bJkP9fd9JcfpGFyeEJX1bUIbgRlfED2TpJK"
    "GeaEfZ9no5+i/rgCaIRO9t86UqgeVJyCyJLnUkrU/ARPj9q/AijJV9kvyPT137UQ"
    "LO+Cl6nZYOglqGcPnRbGiW6WM7imkSxR2XBn6N4ojf49nJOwnN826hkdH5JaPJ1p"
    "AQIDAQAB"
)

CALIBRATION_PHONES = ["7828071445", "9340417208"]
