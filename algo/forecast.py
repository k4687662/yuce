"""Forecasting algorithms."""

import datetime as dt
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from utils.utils import TIME_STEP


def _forecast_sma(series: pd.Series, window: int) -> pd.Series:
    series = series.copy()
    assert window > 0

    fcst = (
        series.groupby(by=[lambda x: x.day_of_week, lambda x: x.time()])
        .rolling(window=window, min_periods=1, closed="left")
        .mean()
        .droplevel([0, 1])
        .sort_index()
    )
    return fcst


def _forecast_last_week(series: pd.Series) -> pd.Series:
    """Simply returns the most recent value with the same day_of_week and time.

    Usually, that would be the value from a week ago.
    """

    series = series.copy()

    fcst = (
        series.groupby(by=[lambda x: x.day_of_week, lambda x: x.time()])
        .rolling(window=1, min_periods=1, closed="left")
        .mean()
        .droplevel([0, 1])
        .sort_index()
    )
    return fcst


def _generate_dummy_future(start, end, freq, inclusive: str | None = None):
    """Parameters are passed to pd.date_range."""

    dummy_future_index = pd.date_range(start=start, end=end, freq=freq, inclusive=inclusive, name="start_time")
    dummy_future = pd.Series(np.nan, index=dummy_future_index, name="value")

    return dummy_future


def forecast_sma(series: pd.Series, window: int = 4, dates: Optional[list[dt.date]] = None) -> pd.Series:
    """
    Parameters
    ----------
    dates : list[dt.date], optional
        If not provided, the immediate 7 days following the date of the latest timestamp is used.

    """

    _DEFAULT_N_DAYS = 7

    if series.empty:
        return series

    if dates is None:
        latest_date = series.index.max().date()
        dates = [latest_date + dt.timedelta(days=i) for i in range(1, _DEFAULT_N_DAYS + 1)]

    expanding_series = series.copy()
    while max(expanding_series.index.to_series().dt.date.to_list()) < max(dates):
        expanding_series_max_date = expanding_series.index.max()
        dummy_future = _generate_dummy_future(
            expanding_series_max_date,
            expanding_series_max_date + pd.offsets.Week(),
            freq=TIME_STEP,
            inclusive="right",
        )
        _fcst = _forecast_sma(pd.concat([expanding_series, dummy_future]), window=window)

        # add the forecast to the actual values
        expanding_series = pd.concat([expanding_series, _fcst[dummy_future.index]])

    # subset with passed dates
    fcst = expanding_series[expanding_series.index.to_series().dt.date.isin(dates)]
    return fcst


def forecast_last_week(series: pd.Series, dates: Optional[list[dt.date]] = None) -> pd.Series:
    """
    Parameters
    ----------
    dates : list[dt.date], optional
        If not provided, the immediate 7 days following the date of the latest timestamp is used.

    """

    _DEFAULT_N_DAYS = 7

    if series.empty:
        return series

    if dates is None:
        latest_date = series.index.max().date()
        dates = [latest_date + dt.timedelta(days=i) for i in range(1, _DEFAULT_N_DAYS + 1)]

    expanding_series = series.copy()
    while max(expanding_series.index.to_series().dt.date.to_list()) < max(dates):
        expanding_series_max_date = expanding_series.index.max()
        dummy_future = _generate_dummy_future(
            expanding_series_max_date,
            expanding_series_max_date + pd.offsets.Week(),
            freq=TIME_STEP,
            inclusive="right",
        )
        _fcst = _forecast_last_week(pd.concat([expanding_series, dummy_future]))

        # add the forecast to the actual values
        expanding_series = pd.concat([expanding_series, _fcst[dummy_future.index]])

    # subset with passed dates
    fcst = expanding_series[expanding_series.index.to_series().dt.date.isin(dates)]
    return fcst


time_features = ["time_block", "is_weekend", "y_lag_1w"]
business_features = ["promo", "pollution"]
feature_cols = time_features + business_features

def _forecast_next_week_xgb(df: pd.DataFrame, xgb: XGBRegressor, features: dict[str: Any]) -> pd.DataFrame:
    """Forecast and return the next 7 days."""

    df = df.copy()
    
    max_date = df["start_time"].max()
    fcst = _generate_dummy_future(max_date, max_date + pd.Timedelta(weeks=1), freq=TIME_STEP, inclusive="right")
    fcst_df = fcst.reset_index().assign(**features)  # apply feature map
    feature_df = _apply_features(pd.concat([df, fcst_df]).reset_index())
    fcst_df["value"] = xgb.predict(feature_df[feature_cols].iloc[-len(fcst):])

    return fcst_df[["start_time", "value", *business_features]]

def _apply_features(df: pd.DataFrame):
    cols = ["start_time", "value", *business_features]
    assert all([col in df.columns for col in cols])
    
    feature_df = df.rename(columns={"value": "y"})
    feature_df["day_of_week"] = feature_df["start_time"].dt.dayofweek
    feature_df["day"] = feature_df["start_time"].dt.day
    feature_df["time_block"] = feature_df["start_time"].dt.hour + feature_df["start_time"].dt.minute / 60
    feature_df["is_weekend"] = (feature_df["day_of_week"] > 4).astype(int)

    # lags
    feature_df["y_lag_1w"] = feature_df.y.shift(periods=int(pd.Timedelta(weeks=1)/pd.infer_freq(df.start_time.head())))

    return feature_df

def forecast_xgb(df: pd.DataFrame, dates: Optional[Sequence[dt.date]] = None, features: dict[str: Any] = {}) -> pd.Series:
    """
    Parameters
    ----------
    dates : Sequence[dt.date], optional
        If not provided, the immediate 7 days following the date of the latest timestamp is used.
    features : dict[str, Any]
        Dictionary of feature name to feature value (scalar). E.g. {"promo": 0} creates a "promo" feature column with
        value 0.
    """

    _DEFAULT_N_DAYS = 7

    if df.empty:
        return df

    if dates is None:
        latest_date = df["start_time"].max().date()
        dates = [latest_date + dt.timedelta(days=i) for i in range(1, _DEFAULT_N_DAYS + 1)]

    # train xgb model
    xgb = XGBRegressor()
    feature_df = _apply_features(df)
    xgb.fit(feature_df[feature_cols], feature_df.y)

    expanding_df = df[["start_time", "value", *business_features]].copy()
    while expanding_df["start_time"].max() < pd.Timestamp(max(dates)+dt.timedelta(days=1)):
        _fcst = _forecast_next_week_xgb(expanding_df, xgb, features)
        expanding_df = pd.concat([expanding_df, _fcst])

    # subset with passed dates
    fcst = expanding_df[expanding_df["start_time"].dt.date.isin(dates)].value
    return fcst