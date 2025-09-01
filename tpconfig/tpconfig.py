"""Taipy configuration."""

import datetime as dt
from typing import Optional

import pandas as pd
from taipy import Config, Scope

from algo.forecast import forecast_sma, forecast_xgb, business_features
from db.crud import read_df
from db.schema import ForecastStoreRequest


# the dataset contains data for 2023 and Q1 2024
# this taipy application will perform in-sample forecasting for weeks (beginning Monday) in Q1 2024
# pd.to_datetime(df.start_time.dt.date.drop_duplicates()).pipe(lambda series: series[(series.dt.day_of_week==0) & (series.dt.year == 2024)]).dt.date.values.tolist()
forecast_dates = [
    dt.date(2024, 1, 1), dt.date(2024, 1, 8), dt.date(2024, 1, 15), dt.date(2024, 1, 22), dt.date(2024, 1, 29), 
    dt.date(2024, 2, 5), dt.date(2024, 2, 12), dt.date(2024, 2, 19), dt.date(2024, 2, 26), dt.date(2024, 3, 4), 
    dt.date(2024, 3, 11), dt.date(2024, 3, 18), dt.date(2024, 3, 25)
]

# data nodes
forecast_store_request_cfg = Config.configure_data_node(
    id="forecast_store_request", scope=Scope.SCENARIO
)  # db.schema.ForecastStoreRequest
cutoff_date_cfg = Config.configure_data_node(id="cutoff_date", scope=Scope.SCENARIO)  # Union[dt.date, dt.dt]
promo_flag_cfg = Config.configure_data_node(id="promo_flag", scope=Scope.SCENARIO)  # bool
air_pollution_cfg = Config.configure_data_node(id="air_pollution", scope=Scope.SCENARIO, default_data=0)  # int [0-5]

store_df_cfg = Config.configure_data_node(id="store_df", scope=Scope.SCENARIO)  # pd.DataFrame
data_df_cfg = Config.configure_data_node(id="data_df", scope=Scope.SCENARIO)  # pd.DataFrame

# tasks
FCST_SMA_KEY = "forecast_sma"
FCST_LAST_WEEK_KEY = "forecast_last_week"
FCST_XGB_KEY = "forecast_xgb"


def tp_get_store_df(fsr: ForecastStoreRequest, cutoff_date: Optional[dt.date | dt.datetime]) -> pd.DataFrame:
    """cutoff_date is exclusive."""

    assert fsr.dates[0] in forecast_dates and len(fsr.dates) == 7, "invalid forecast date"

    df = read_df(fsr.store_id)
    df = df.set_index("start_time")
    df = df[df.index < pd.Timestamp(cutoff_date)].reset_index()
    return df


get_store_df_task_cfg = Config.configure_task(
    id="get_store_df",
    function=tp_get_store_df,
    input=[forecast_store_request_cfg, cutoff_date_cfg],
    output=[store_df_cfg],
    skippable=True
)

def tp_generate_data_df(store_df: pd.DataFrame, fsr: ForecastStoreRequest, promo_flag: bool, air_pollution: int) -> pd.DataFrame:
    """Convert store_df (truncated raw dataset) to data_df (in-sample forecast with true values)."""

    dfs = []
    for section_indicator, _df in store_df.groupby(by=["section", "indicator"], observed=True):
        _df = _df.drop(columns=["store_id", "section", "indicator"])
        _series = _df.set_index("start_time").value
        fcst_df = forecast_sma(_series, dates=fsr.dates).to_frame(name=FCST_SMA_KEY)
        features = {"promo": int(promo_flag), "pollution": air_pollution}
        fcst_df[FCST_XGB_KEY] = forecast_xgb(_df, dates=fsr.dates, features=features).values

        fcst_df["section"] = section_indicator[0]
        fcst_df["indicator"] = section_indicator[1]

        fcst_df = fcst_df.reset_index()

        dfs.append(fcst_df)    

    data_df = pd.concat(dfs, ignore_index=True)
    data_df["section"] = data_df["section"].astype("category")
    data_df["indicator"] = data_df["indicator"].astype("category")

    # merge with actual y value
    data_df = data_df.merge(read_df(store_id=fsr.store_id), on=["start_time", "section", "indicator"], how="left")
    data_df = data_df[["start_time", "section", "indicator", "value", FCST_SMA_KEY, FCST_XGB_KEY, *business_features]]  # reorder columns

    return data_df

generate_data_df_task_cfg = Config.configure_task(
    id="generate_data_df",
    function=tp_generate_data_df,
    input=[store_df_cfg, forecast_store_request_cfg, promo_flag_cfg, air_pollution_cfg],
    output=[data_df_cfg],
)


# scenario
sales_forecast_scenario_cfg = Config.configure_scenario(
    id="sales_forecast_scenario",
    task_configs=[get_store_df_task_cfg, generate_data_df_task_cfg],
)