import os
import argparse
import logging
from datetime import datetime
from forecast_model import ForecastModel
from excel_logger import ExcelLogger
from telegram_notifier import TelegramNotifier

def setup_coin_logging(coin, args):
    temp_logger = ExcelLogger(model_name=args.model_path, coin=coin, timeframe=args.interval, horizon=args.horizon, period=args.period)
    logs_dir = os.path.join(temp_logger.base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    temp_log = os.path.join(logs_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tmp")

    for h in logging.root.handlers[:]:
        h.close()
        logging.root.removeHandler(h)

    logging.root.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(temp_log, encoding="utf-8")
    fh.setFormatter(formatter)
    logging.root.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logging.root.addHandler(sh)

    return temp_log, logs_dir

def rename_log_file(temp_log, logs_dir, suffix):
    for h in logging.root.handlers[:]:
        h.close()
        logging.root.removeHandler(h)
    new_path = os.path.join(logs_dir, f"log_{suffix}.log")
    os.rename(temp_log, new_path)
    return new_path

def main():
    parser = argparse.ArgumentParser(description="Cryptocurrency Forecasting with TimesFM and Deferred Excel Logging")
    parser.add_argument("--coins", type=str, default="BTC-USD", help="Comma-separated list of coins (e.g. BTC-USD,ETH-USD,SOL-USD)")
    parser.add_argument("--period", type=str, default="30d", help="Historical data period to download (e.g. 30d)")
    parser.add_argument("--interval", type=str, default="1h", help="Interval of price data (e.g. 1h)")
    parser.add_argument("--horizon", type=int, default=24, help="Forecast horizon length in steps (e.g. 24)")
    parser.add_argument("--model_path", type=str, default="google/timesfm-2.5-200m-pytorch", help="HF model name or path for TimesFM")
    parser.add_argument("--mape-threshold", type=float, default=5.0, help="MAPE threshold for Telegram warning (default 5.0)")

    args = parser.parse_args()
    coins = [c.strip() for c in args.coins.split(",")]

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    notifier = TelegramNotifier(mape_threshold=args.mape_threshold)
    start_time = datetime.now()

    fm_template = ForecastModel(coin=coins[0], period=args.period, interval=args.interval)
    fm_template.load_model(model_name_or_path=args.model_path)

    for coin in coins:
        temp_log = None
        logs_dir = None
        try:
            temp_log, logs_dir = setup_coin_logging(coin, args)

            logging.info("")
            logging.info("=" * 80)
            logging.info(f"PROCESSING {coin}")
            logging.info("=" * 80)

            logging.info("")
            logging.info("--- STAGE 1: DOWNLOADING DATA ---")
            fm = ForecastModel(coin=coin, period=args.period, interval=args.interval)
            fm.model = fm_template.model
            fm.download_data()

            logger_helper = ExcelLogger(model_name=args.model_path, coin=coin, timeframe=args.interval, horizon=args.horizon, period=args.period)

            logging.info("")
            logging.info("--- STAGE 2: EVALUATING LATEST FORECAST ---")
            eval_result = logger_helper.check_and_evaluate_latest(fm.data)
            if eval_result.get("evaluated"):
                logging.info("Pending forecast evaluated.")
                mape = eval_result.get("mape", 0)
                if mape > args.mape_threshold:
                    notifier.notify_threshold(
                        coin=coin,
                        timeframe=f"{args.interval}/{args.period}",
                        row_id=eval_result.get("row_id"),
                        mape=mape,
                        last_predicted=eval_result.get("last_predicted"),
                        last_actual=eval_result.get("last_actual"),
                        chart_path=eval_result.get("chart_path"),
                    )
            else:
                logging.info("No evaluation needed.")

            logging.info("")
            logging.info("--- STAGE 3: GENERATING NEW FORECAST ---")
            forecasted, _, lower_band, median_band, upper_band = fm.forecast(horizon=args.horizon)

            logged_id = logger_helper.log_forecast(
                coin=coin,
                timeframe=args.interval,
                horizon=args.horizon,
                forecasted=forecasted,
                lower_band=lower_band,
                median_band=median_band,
                upper_band=upper_band,
            )

            logging.info(f"{coin} completed. Forecast ID: {logged_id}")
            rename_log_file(temp_log, logs_dir, f"{logged_id:03d}")

            notifier.add_result(coin, f"{args.interval}/{args.period}", "success", row_id=logged_id, mape=eval_result.get("mape"))
        except Exception as e:
            logging.exception(f"{coin} failed")
            if temp_log and logs_dir:
                rename_log_file(temp_log, logs_dir, f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            notifier.notify_failure(coin, f"{args.interval}/{args.period}", str(e))
            notifier.add_result(coin, f"{args.interval}/{args.period}", "failed")

    duration = (datetime.now() - start_time).total_seconds()
    notifier.send_summary(duration)

if __name__ == "__main__":
    main()
