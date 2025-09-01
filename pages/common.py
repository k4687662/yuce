from typing import Optional
from db.schema import ForecastStoreRequest
import pandas as pd
import taipy as tp
import datetime as dt

def fsr_to_label(fsr: ForecastStoreRequest) -> str:
    """Used as an adapter for the scenario selector lov.
    
    Since there may be duplicate labels (to accommodate other features), we should append the scenario uuid to the label
    after this operation to ensure the names are unique.
    """

    start_date = min(fsr.dates).strftime("%Y-%m-%d")
    label = f"Store {fsr.store_id} | {start_date}"
    return label


def year_week_adapter(date: dt.date):
    return date.strftime("%G-W%V")


def year_week_date_adapter(date: dt.date):
    return date.strftime("%G-W%V | %Y-%m-%d")


def create_scenario_summary_df(scenario_list: list[tp.Scenario]):
    data = [(
        s.name, 
        s.creation_date.strftime("%Y-%m-%d %H:%M:%S"),  # Convert to str to display in local datetime 
        s.forecast_store_request.read().store_id, 
        year_week_adapter(s.forecast_store_request.read().dates[0]),
        s.promo_flag.read(),
        s.air_pollution.read(),
    ) for s in scenario_list]

    return pd.DataFrame(data, columns=["Scenario Name", "Submission Date", "Store ID", "Week", "Promotion?", "Air Pollution"])

def get_ordered_scenarios():
    """Get the list of scenarios ordered by creation date (reverse chronological)."""

    scenario_list = tp.get_scenarios()
    scenario_list.sort(key=lambda s: s.creation_date, reverse=True)
    return scenario_list