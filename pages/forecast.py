"""View forecast data vs historical data."""

from typing import Optional
from taipy.gui import Markdown
import taipy as tp
from string import Template
import pandas as pd
from db.crud import get_tree_mappings
from sklearn.metrics import mean_squared_error
from tpconfig.tpconfig import FCST_SMA_KEY, FCST_XGB_KEY

tree_mappings = get_tree_mappings()

section_list = []
selected_section = None
indicator_list = []
selected_indicator = None

chart_data_list = ["residuals", "values"]
selected_chart_data = chart_data_list[0]

chart_type_list = ["line", "histogram"]
selected_chart_type = chart_type_list[0]

metrics_df = pd.DataFrame()

forecast_template = Template(
"""
## Forecast Explorer

Examine and evaluate the generated in-sample forecast. 

Hint: The **[table at the bottom of this page](/forecast#historical-data)**{: .color-primary} shows the **actual** business feature values.
Create a **[new scenario](/create) with these features**{: .color-primary} and observe its improvement.

<br/>

<|layout|columns=3 2|

<chart|card|
$_chart_md
|chart>

<rhs|card|

<|Forecast Metrics - {selected_section}/{selected_indicator}|text|class_name=h3|> <br/>

<kpi|layout|columns=15em 15em|

<|card p-half m-half text-center card-font card-bg|
**SMA MSE**{: .color-primary}

<|{metrics_df.loc[(metrics_df.section==selected_section) & (metrics_df.indicator==selected_indicator), 'mse_forecast_sma'].item() if not metrics_df.empty else 0}|text|raw|format=%,.2f|>
|>

<|card p-half m-half text-center card-font card-bg|
**XGB MSE**{: .color-primary}

<|{metrics_df.loc[(metrics_df.section==selected_section) & (metrics_df.indicator==selected_indicator), 'mse_forecast_xgb'].item() if not metrics_df.empty else 0}|text|raw|format=%,.2f|>
|>

|kpi>

### Forecast Metrics - All Sections/Indicators

<|{metrics_df}|table|width=fit-content|number_format=%.2f|show_all|>

|rhs>

|>

<|Forecast Data (Table) 🗃️|expandable|expanded=True|id=historical-data|
<|{selected_scenario.data_df.read() if bool(selected_scenario) else [()]}|table|filter|date_format=yyyy-MM-dd HH:mm:SS|>
|>
""")

_chart_md = """\
<|{selected_chart_data.title()} - {selected_chart_type.title()}|text|class_name=h3|> <br/>

<selectors_row1|layout|columns=1 1|
<|{selected_section}|selector|lov={section_list}|dropdown|class_name=fullwidth|label=Section|>

<|{selected_indicator}|selector|lov={indicator_list}|dropdown|class_name=fullwidth|label=Indicator|>
|selectors_row1>

<|{selected_chart_data}|toggle|lov={chart_data_list}|>
<|{selected_chart_type}|toggle|lov={chart_type_list}|>

<|part|render={selected_chart_data == "residuals" and selected_chart_type == "line"}|
<|{create_residuals_chart(selected_scenario, selected_section, selected_indicator)}|chart|properties={residuals_chart_properties}|>
|>

<|part|render={selected_chart_data == "values" and selected_chart_type == "line"}|
<|{create_values_chart(selected_scenario, selected_section, selected_indicator)}|chart|properties={values_chart_properties}|>
|>

<|part|render={selected_chart_data == "residuals" and selected_chart_type == "histogram"}|
<|{create_residuals_chart(selected_scenario, selected_section, selected_indicator)}|chart|properties={residuals_histogram_properties}|>
|>

<|part|render={selected_chart_data == "values" and selected_chart_type == "histogram"}|
<|{create_values_chart(selected_scenario, selected_section, selected_indicator)}|chart|properties={values_histogram_properties}|>
|>
"""

forecast_md = Markdown(forecast_template.substitute(_chart_md=_chart_md))


def create_metrics_table(selected_scenario: Optional[tp.Scenario]) -> pd.DataFrame:
    MSE_FCST_SMA_KEY = "mse_forecast_sma"
    MSE_FCST_XGB_KEY = "mse_forecast_xgb"
    if selected_scenario is None:
        # empty df with relevant columns for (empty) table to render
        return pd.DataFrame([], columns=["section", "indicator", MSE_FCST_SMA_KEY, MSE_FCST_XGB_KEY])

    data_df: pd.DataFrame = selected_scenario.data_df.read()
    metrics_table_df = data_df.groupby(by=["section", "indicator"], observed=True).apply(lambda grp: pd.Series({
        MSE_FCST_SMA_KEY: mean_squared_error(grp.value, grp[FCST_SMA_KEY]),
        MSE_FCST_XGB_KEY: mean_squared_error(grp.value, grp[FCST_XGB_KEY])
    })).reset_index()

    return metrics_table_df

SMA_RESIDUALS_KEY = "sma_residuals"
XGB_RESIDUALS_KEY = "xgb_residuals"
def create_residuals_chart(selected_scenario, selected_section, selected_indicator):
    if selected_scenario is None:
        # empty df with relevant columns for (empty) chart to render
        return pd.DataFrame([], columns=["start_time_str", SMA_RESIDUALS_KEY, XGB_RESIDUALS_KEY])

    data_df: pd.DataFrame = selected_scenario.data_df.read()
    residuals_df = data_df.loc[(data_df.section == selected_section) & (data_df.indicator == selected_indicator), :].copy()

    residuals_df["start_time_str"] = residuals_df.start_time.astype(str)
    residuals_df[SMA_RESIDUALS_KEY] = residuals_df.value - residuals_df[FCST_SMA_KEY]
    residuals_df[XGB_RESIDUALS_KEY] = residuals_df.value - residuals_df[FCST_XGB_KEY]

    return residuals_df

residuals_chart_properties = {
    "x": "start_time_str",
    "y": [SMA_RESIDUALS_KEY, XGB_RESIDUALS_KEY],
    "mode": "lines",
    "layout": dict(
        title=dict(text="Residuals Over Time"),
        hovermode="x unified",
        xaxis=dict(title="Start time"),
        yaxis=dict(title="Residual"),
    ),
}

residuals_histogram_properties = {
    "x": [SMA_RESIDUALS_KEY, XGB_RESIDUALS_KEY],
    "name[1]": SMA_RESIDUALS_KEY,
    "name[2]": XGB_RESIDUALS_KEY,
    "type": "histogram",
    "options": [
        dict(opacity=0.5),
        dict(opacity=0.5),
    ],
    "layout": dict(
        title=dict(text="Residuals Histogram"),
        barmode="overlay",
        xaxis=dict(title="Values"),
        yaxis=dict(title="Count"),
    ),
}

def create_values_chart(selected_scenario, selected_section, selected_indicator):
    if selected_scenario is None:
        # empty df with relevant columns for (empty) chart to render
        return pd.DataFrame([], columns=["start_time_str", FCST_SMA_KEY, FCST_XGB_KEY, "value"])

    data_df: pd.DataFrame = selected_scenario.data_df.read()
    values_df = data_df.loc[(data_df.section == selected_section) & (data_df.indicator == selected_indicator), :].copy()
    values_df["start_time_str"] = values_df.start_time.astype(str)

    return values_df

values_chart_properties = {
    "x": "start_time_str",
    "y": [FCST_SMA_KEY, FCST_XGB_KEY, "value"],
    "mode": "lines",
    "layout": dict(
        title=dict(text="Values Over Time"),
        hovermode="x unified",
        xaxis=dict(title="Start time"),
        yaxis=dict(title="Value"),
    ),
}

values_histogram_properties = {
    "x": [FCST_SMA_KEY, FCST_XGB_KEY, "value"],
    "name[1]": SMA_RESIDUALS_KEY,
    "name[2]": XGB_RESIDUALS_KEY,
    "name[3]": "value",
    "type": "histogram",
    "options": [
        dict(opacity=0.5),
        dict(opacity=0.5),
        dict(opacity=0.5),
    ],
    "layout": dict(
        title=dict(text="Values Histogram"),
        barmode="overlay",
        xaxis=dict(title="Values"),
        yaxis=dict(title="Count"),
    ),
}

def forecast_on_init(state):
    ...

root_var_update_list = ["selected_scenario"]
def forecast_on_navigate(state):
    for var_name in root_var_update_list:
        forecast_on_change(state, var_name, getattr(state, var_name))

def forecast_on_change(state, var_name, var_value):
    # root variables
    if var_name == "selected_scenario":
        if var_value is None:
            state.section_list = []
            state.selected_section = None
        else:
            state.section_list = list(tree_mappings[var_value.forecast_store_request.read().store_id].keys())
            state.selected_section = state.section_list[0]
        state.metrics_df = create_metrics_table(var_value)

    # module variables
    elif var_name == "selected_section":
        if var_value is None:
            state.indicator_list = []
            state.selected_indicator = None
        else:
            state.indicator_list = tree_mappings[state.selected_scenario.forecast_store_request.read().store_id][var_value]
            state.selected_indicator = state.indicator_list[0]