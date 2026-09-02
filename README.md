# 🚀 Meesho Account & JSON Session Generator Telegram Bot

An automated 24/7 Telegram Bot designed to generate fresh Meesho accounts, harvest high First Order Discount (FOD ₹180+) offers, bind referral codes, and instantly deliver `session_<phone>_meesho.json` files directly to your Telegram chat.

---

## ✨ Key Features

- **⚡ Instant JSON Delivery:** As soon as an account is generated, its full `session_*.json` file is sent directly as a downloadable document on Telegram.
- **🎯 FOD Offer Harvesting:** Automatically emulates flagship devices (Pixel 9 Pro XL, Galaxy S24 Ultra, OnePlus 12, Vivo X100 Pro) to secure maximum discount (₹180, ₹200, ₹225 OFF).
- **🔗 Referral Code Binding:** Automatically binds your referral link / code during session initialization.
- **🔄 Multi-Provider SMS Integration:** Concurrently fetches numbers from **GrizzlySMS, NumeraSMS, TigerSMS, NexNum, and SmsBower** with instant fallback.
- **📱 Dual Generation Modes:**
  - **Auto Mode (`/create`)**: Completely automated OTP fetching from SMS providers.
  - **Manual Mode (`/manual <phone>`)**: Enter your own phone number, receive OTP on your SIM, reply to the bot with OTP, and get the session JSON.
- **🌐 24/7 Render Keep-Alive:** Embedded lightweight HTTP server on port `10000` with `/health` endpoint to ensure seamless 24/7 uptime on Render Web Services.

---

## 📌 Bot Commands

| Command | Parameters | Description |
| :--- | :--- | :--- |
| `/start` | None | Open the interactive main menu with buttons |
| `/create` | `[count] [min_offer] [referral]` | Auto-create `N` accounts and receive JSON files |
| `/manual` | `[phone]` | Manual OTP login mode for a custom phone number |
| `/balance` | None | Check balances across all 5 SMS providers |
| `/referral` | `[code/link]` | View or update active Meesho referral link/code |
| `/minoffer` | `[amount]` | Set minimum FOD discount threshold (e.g. 180, 200) |
| `/sessions` | None | List recently generated session JSON files |
| `/status` | None | View bot uptime, active workers, and server status |
| `/cancel` | None | Cancel active manual OTP flow |

---

## 🛠️ Local Setup & Testing

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Bot
```bash
python bot.py
```
*The bot will immediately connect to Telegram and start polling.*

---

## 🚀 How to Put on GitHub

1. Create a new repository on [GitHub](https://github.com/new) (e.g., `meesho-telegram-bot`). Make it **Private** (recommended) or Public.
2. In your local project directory, run:
```bash
git init
git add .
git commit -m "Initial commit: Meesho Telegram Bot 24/7"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/meesho-telegram-bot.git
git push -u origin main
```

---

## ☁️ How to Deploy on Render (24/7 Free Hosting)

### Method 1: Render Web Service (Recommended)

1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** ➔ **Web Service**.
2. Connect your GitHub repository (`meesho-telegram-bot`).
3. Fill in the deployment settings:
   - **Name:** `meesho-telegram-bot`
   - **Language:** `Python 3`
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** `Free`
4. Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN`: `8908238181:AAFDaBABB1Bj-PgCDalr8jvZPXNhgE6ukKo`
   - `GRIZZLY_API_KEY`: `804def05f9fa4a8469bf9704f1edfa73`
   - `NUMERASMS_API_KEY`: `a0b9fbacc969d22984f613334f028bed0d44`
   - `TIGERSMS_API_KEY`: `OulvxGKfZ31ObBxxck16WeaAM6VXbS6u`
   - `NEXNUM_API_KEY`: `nxn_live_jtgqj2nmTekopnltsG8E9DpKoAe_9m2s`
   - `SMSBOWER_API_KEY`: `JDvqNuzbtpc2YB6t52TrNOdLZdtu50xQ`
   - `MEESHO_REFERRAL_LINK`: `https://app.meesho.com/2yoV/r99th0qd?via=9r3b32&from=referral_program`
   - `MIN_OFFER_DISCOUNT`: `180`
   - `PORT`: `10000`
5. Click **Create Web Service**. Render will build and launch your bot!

### Keep-Alive for Render Free Tier (24/7 Uptime)
Render free web services sleep after 15 minutes of inactivity if no HTTP requests are made.
Because the bot has an embedded web server on `/health`:
1. Copy your Render web service URL (e.g., `https://meesho-telegram-bot.onrender.com`).
2. Go to [UptimeRobot](https://uptimerobot.com/) or [cron-job.org](https://cron-job.org/) (Free).
3. Create a monitor to ping `https://meesho-telegram-bot.onrender.com/health` every **5 or 10 minutes**.
4. Your bot will now run **24/7 without ever sleeping**!

---

## 🔒 Security Notice
The `.gitignore` file is pre-configured to ensure that generated `session_*.json` files containing authentication tokens are never pushed to your public GitHub repository.
