"""View data till the cutoff period.

Views:
1. Stacked area chart of "Items" for each Section.
"""

from typing import Optional
from taipy.gui import Markdown
import taipy as tp
from taipy.gui.data.decimator import MinMaxDecimator
from string import Template
import pandas as pd
import datetime as dt


indicator_list = []
selected_indicator = None

_FREQ_30MIN = "30min"
_FREQ_DAY = "day"
_FREQ_WEEK = "week"
_FREQ_MONTH = "month"
aggregation_frequency_lov = [_FREQ_30MIN, _FREQ_DAY, _FREQ_WEEK, _FREQ_MONTH]
selected_aggregation_frequency = aggregation_frequency_lov[1]

data_template = Template(
"""
## Data Explorer

Examine the historical data used to train the models.

<br/>

<indicator|card
### Indicator Over Time

<|{selected_indicator}|selector|lov={indicator_list}|dropdown|label=Indicator|>

<|{selected_aggregation_frequency}|toggle|lov={aggregation_frequency_lov}|>

<|{create_indicator_over_time_chart(selected_scenario, selected_indicator, selected_aggregation_frequency)}|chart|properties={indicator_over_time_chart_properties}|>
|indicator>

<|Historical Data (Table) 🗃️|expandable|expanded=False|
<|{selected_scenario.store_df.read() if bool(selected_scenario) else [()]}|table|rebuild|filter|date_format=yyyy-MM-dd HH:mm:SS|>
|>
""")

data_md = Markdown(data_template.substitute())

NOP = int(dt.timedelta(days=21) / dt.timedelta(minutes=30))
decimator_instance = MinMaxDecimator(n_out=NOP, threshold=NOP)
all_sections = ["MAINS", "SIDES", "BEVERAGE"]
indicator_over_time_chart_properties = {
    "x": "start_time_str",
    "y": all_sections,
    "mode": "lines+markers",  # decimator doesn't seem to reload on zoom when mode="lines"
    "marker[1]": dict(opacity=0),
    "marker[2]": dict(opacity=0),
    "marker[3]": dict(opacity=0),
    "selected_marker[1]": dict(opacity=0),
    "selected_marker[2]": dict(opacity=0),
    "selected_marker[3]": dict(opacity=0),
    "decimator[1]": "decimator_instance",
    "decimator[2]": "decimator_instance",
    "decimator[3]": "decimator_instance",
    "options": {
        "fill": "tonexty",
        "stackgroup": "first_group",
    },
    "layout": dict(
        title=dict(text="Indicator Over Time (stacked)"),
        hovermode="x unified", 
        xaxis=dict(
            title="Start time",
            # rangeslider=dict(visible=True, thickness=0.1),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(step="all")
                ])
            ),
        ),
        yaxis=dict(title="Value"),
    ),
        
}
def create_indicator_over_time_chart(selected_scenario: Optional[tp.Scenario], selected_indicator, selected_aggregation_frequency) -> pd.DataFrame:
    if selected_scenario is None:
        # empty df with relevant columns for (empty) chart to render
        return pd.DataFrame([], columns=["start_time_str", *all_sections])

    store_df: pd.DataFrame = selected_scenario.store_df.read()

    # groupby selected_aggregation_frequency
    if selected_aggregation_frequency != _FREQ_30MIN:
        if selected_aggregation_frequency == _FREQ_DAY:
            store_df["start_time"] = store_df.start_time.dt.to_period("D")
        elif selected_aggregation_frequency == _FREQ_WEEK:
            store_df["start_time"] = store_df.start_time.dt.to_period('W-SUN').dt.start_time
        elif selected_aggregation_frequency == _FREQ_MONTH:
            store_df["start_time"] = store_df.start_time.dt.to_period('M').dt.start_time
        store_df = store_df.groupby(by=["store_id", "section", "indicator", "start_time"], observed=True).value.sum().reset_index()


    # assigning CategoricalDtype with all_sections allows pivot_table (with observed=False) to generate even absent 
    # sections for a store
    # the chart needs all section columns to be present
    store_df.section = store_df.section.astype(pd.CategoricalDtype(all_sections))
    store_df["start_time_str"] = store_df.start_time.astype(str)
    kpi_over_time_df = store_df[store_df.indicator==selected_indicator].pivot_table(
        columns="section",
        index="start_time_str",
        values="value",
        dropna=False,
        observed=False,
    ).rename_axis(None, axis=1).reset_index()

    return kpi_over_time_df

def data_on_init(state):
    ...

root_var_update_list = ["selected_scenario"]
def data_on_navigate(state):
    for var_name in root_var_update_list:
        data_on_change(state, var_name, getattr(state, var_name))


def data_on_change(state, var_name, var_value):
    # root variables
    if var_name == "":
        ...

    # module variables
    elif var_name == "selected_scenario":
        state.indicator_list = var_value.store_df.read().indicator.drop_duplicates().tolist() if var_value is not None else []
        state.selected_indicator = state.indicator_list[0] if state.indicator_list else None