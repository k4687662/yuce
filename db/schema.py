import datetime as dt
from dataclasses import dataclass


@dataclass(kw_only=True)
class ForecastStoreRequest:
    store_id: str
    time_step: dt.timedelta = dt.timedelta(minutes=30)
    dates: list[dt.date]


@dataclass(kw_only=True)
class ForecastRequest(ForecastStoreRequest):
    section: str
    indicator: str