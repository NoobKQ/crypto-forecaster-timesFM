import re
import time
import logging
import timesfm
import yfinance as yf
import pandas as pd

class ForecastModel:
    def __init__(self, coin="BTC-USD", period="30d", interval="1h"):
        self.coin = coin
        self.period = period
        self.interval = interval
        self.data = None
        self.prices = None
        self.model = None

    def download_data(self):
        logging.info(f"Downloading data for {self.coin} (period={self.period}, interval={self.interval})...")
        max_retries = 5
        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 10 * (2 ** (attempt - 1))
                logging.info(f"  Retry {attempt + 1}/{max_retries} after {wait}s...")
                time.sleep(wait)
            try:
                self.data = yf.download(
                    self.coin,
                    period=self.period,
                    interval=self.interval,
                    progress=False
                )
                if self.data is not None and not self.data.empty:
                    break
            except Exception as e:
                last_error = e
                logging.info(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")
        if self.data is None or self.data.empty:
            msg = f"Failed to download data for {self.coin} after {max_retries} attempts."
            if last_error:
                msg += f" Last error: {last_error}"
            raise ValueError(msg)
        close = self.data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        self.prices = close.dropna().to_numpy().flatten()
        logging.info(f"Data downloaded successfully. Total rows: {len(self.data)}")

    def load_model(self, model_name_or_path="google/timesfm-2.5-200m-pytorch"):
        logging.info(f"Loading TimesFM model from {model_name_or_path}...")
        self.model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            model_name_or_path
        )
        logging.info("Compiling model...")
        self.model.compile(
            timesfm.ForecastConfig(
                max_context=1024,
                max_horizon=256,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
            )
        )
        logging.info("Model loaded and compiled successfully.")

    def forecast(self, horizon=24):
        """
        Runs a forecast on the full dataset to predict the unseen future.
        """
        if self.prices is None:
            self.download_data()

        logging.info(f"Running future forecast for horizon={horizon}...")
        point_forecast, quantile_forecast = self.model.forecast(
            horizon=horizon,
            inputs=[self.prices]
        )
        forecasted = point_forecast[0]

        # Extract quantile bands: p10 (lower), p50 (median), p90 (upper)
        lower_band  = quantile_forecast[0, :, 0]
        median_band = quantile_forecast[0, :, 1]
        upper_band  = quantile_forecast[0, :, 2]

        # Normalize deprecated frequency aliases (M -> ME for pandas >= 2.2)
        freq = re.sub(r'(?i)(\d+)M$', r'\1ME', self.interval)

        # Generate future index starting from the last known data point
        future_index = pd.date_range(
            start=self.data.index[-1],
            periods=horizon + 1,
            freq=freq
        )[1:]

        return forecasted, future_index, lower_band, median_band, upper_band
