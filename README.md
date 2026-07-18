# Crypto Forecaster

Cryptocurrency price forecasting pipeline using [TimesFM](https://github.com/google-research/timesfm) + yfinance. Runs daily via GitHub Actions, logs results to Excel, and sends Telegram alerts.

## How it works

Each coin goes through a 3-stage pipeline:

1. **Download** — fetch latest price data from Yahoo Finance (retries up to 5×)
2. **Evaluate** — check the previous forecast, compare predicted vs actual prices, calculate MAPE
3. **Forecast** — run TimesFM inference, log the new forecast to Excel

Multiple coins share one model load. If one coin fails, the rest continue.

## Folder structure

```
{model_name}/{coin}_{interval}_{period}_h{horizon}/
├── log.xlsx              # Forecast history (2 sheets)
│   ├── Forecast Logs     # Summary per forecast (ID, time, last price, MAPE)
│   └── Forecast Details  # Per-step prices, bands, errors
├── charts/               # Evaluation charts (PNG)
└── logs/                 # Per-run log files
    ├── log_001.log
    └── log_002.log
```

## Setup

1. Fork or clone the repo
2. Add these secrets in **Settings → Secrets and variables → Actions**:
   - `TELEGRAM_BOT_TOKEN` — bot token from [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHAT_ID` — your chat ID (use [@userinfobot](https://t.me/userinfobot))
3. Push — the Action runs daily at 00:00 UTC

Telegram is optional. If secrets are missing, the pipeline runs without notifications.

## Run locally

```powershell
python main.py --coins BTC-USD,ETH-USD --period 30d --interval 1h --horizon 24
```
