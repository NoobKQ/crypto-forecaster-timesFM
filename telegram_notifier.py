import os
import logging
import requests

BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
CHAT_ID_ENV = "TELEGRAM_CHAT_ID"
MSG_URL = "https://api.telegram.org/bot{token}/sendMessage"
PHOTO_URL = "https://api.telegram.org/bot{token}/sendPhoto"

class TelegramNotifier:
    def __init__(self, mape_threshold=5.0):
        self.bot_token = os.environ.get(BOT_TOKEN_ENV)
        self.chat_id = os.environ.get(CHAT_ID_ENV)
        self.enabled = bool(self.bot_token and self.chat_id)
        self.mape_threshold = mape_threshold
        self.results = []

    def _send(self, text):
        if not self.enabled:
            return
        try:
            url = MSG_URL.format(token=self.bot_token)
            requests.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        except Exception:
            logging.warning("Telegram send failed")

    def _send_photo(self, text, photo_path):
        if not self.enabled:
            return
        try:
            url = PHOTO_URL.format(token=self.bot_token)
            with open(photo_path, "rb") as f:
                requests.post(url, data={"chat_id": self.chat_id, "caption": text, "parse_mode": "Markdown"}, files={"photo": f}, timeout=15)
        except Exception:
            logging.warning("Telegram sendPhoto failed")

    def notify_failure(self, coin, timeframe, error_msg):
        text = (
            f"🚨 *Crypto Forecast Failed*\n\n"
            f"Coin:       `{coin}`\n"
            f"Timeframe:  `{timeframe}`\n"
            f"Error:      `{error_msg}`"
        )
        self._send(text)

    def notify_threshold(self, coin, timeframe, row_id, mape, last_predicted, last_actual, chart_path=None):
        text = (
            f"⚠️ *High Error Warning*\n\n"
            f"Coin:       `{coin}`   ID `{row_id}`\n"
            f"Timeframe:  `{timeframe}`\n"
            f"MAPE:       `{mape:.2f}%`  (threshold: `{self.mape_threshold}%`)\n"
            f"Last Pred:  `${last_predicted:,.2f}`\n"
            f"Last Actual: `${last_actual:,.2f}`\n"
            f"Abs Error:  `${abs(last_predicted - last_actual):,.2f}`"
        )
        if chart_path and os.path.exists(chart_path):
            self._send_photo(text, chart_path)
        else:
            self._send(text)

    def add_result(self, coin, timeframe, status, row_id=None, mape=None):
        self.results.append({
            "coin": coin,
            "timeframe": timeframe,
            "status": status,
            "row_id": row_id,
            "mape": mape,
        })

    def send_summary(self, duration_sec):
        lines = ["📊 *Daily Forecast Summary*\n"]
        for r in self.results:
            if r["status"] == "success":
                icon = "⚠️" if (r["mape"] is not None and r["mape"] > self.mape_threshold) else "✅"
                mape_str = f"MAPE {r['mape']:.2f}%" if r["mape"] is not None else "MAPE N/A"
                lines.append(f"{icon} `{r['coin']}` {r['timeframe']}  ID {r['row_id']}  {mape_str}")
            else:
                lines.append(f"❌ `{r['coin']}` {r['timeframe']}  —  FAILED")
        mins, secs = divmod(int(duration_sec), 60)
        lines.append(f"\nCompleted in {mins}m {secs}s")
        self._send("\n".join(lines))
