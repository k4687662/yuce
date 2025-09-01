from taipy.gui import Markdown, notify, Icon
import taipy as tp
from string import Template
from tpconfig.tpconfig import sales_forecast_scenario_cfg, forecast_dates
from db.crud import get_tree_mappings
from db.schema import ForecastStoreRequest
from pages.common import fsr_to_label, year_week_date_adapter, create_scenario_summary_df, get_ordered_scenarios
import datetime as dt

year_week_date_adapter
create_scenario_summary_df

tree_mappings = get_tree_mappings()
store_list = list(tree_mappings.keys())
selected_store = store_list[0]

forecast_dates
selected_week_start = forecast_dates[0]

promo_flag = False

air_pollution_list = [
    ("0", Icon("assets/images/sentiment/sentiment_very_satisfied_white_24dp.svg", "Good")),
    ("1", Icon("assets/images/sentiment/sentiment_insert_emoticon_24dp.svg", "Moderate")),
    ("2", Icon("assets/images/sentiment/sentiment_satisfied_white_white_24dp.svg", "Unhealthy for Sensitive Groups")),
    ("3", Icon("assets/images/sentiment/sentiment_neutral_white_24dp.svg", "Unhealthy")),
    ("4", Icon("assets/images/sentiment/sentiment_dissatisfied_white_24dp.svg", "Very Unhealthy")),
    ("5", Icon("assets/images/sentiment/sentiment_very_dissatisfied_white_24dp.svg", "Hazardous")),
]

selected_air_pollution = air_pollution_list[0][0]
create_template = Template(
"""
**Create scenario**{: .h3}

This application is built on a dataset with **data for 2023 and Q1 2024**{: .color-primary}.

1. **Select a store and a week**{: .color-primary} (beginning Monday) in Q1 2024, then
2. **Submit**{: .color-primary} the scenario.

<|layout.start|columns=1 3|>

<lhs|card|

### Store:

<|{selected_store}|selector|lov={store_list}|dropdown|label=Store|>

### Week:

<|{selected_week_start}|selector|lov={forecast_dates}|dropdown|label=Week|adapter=year_week_date_adapter|>

### Business Rules:

**Promotion:** <|{promo_flag}|toggle|>

**Air pollution:**

<|{selected_air_pollution}|slider|lov={air_pollution_list}|value_by_id|>

<br/>

<|Submit 🚀|button|on_action=create_scenario|>

|lhs>

<rhs|card|

## Existing scenarios

Scenarios with the same Store ID as the selected store.

**Selected store:** <|{selected_store}|>

<|{create_similar_scenarios_df(selected_store, scenario_list)}|table|width=fit-content|filter|allow_all_rows|date_format=yyyy-MM-dd HH:mm:SS|>

|rhs>

<|layout.end|>
""")

def create_similar_scenarios_df(selected_store: str, scenario_list: list[tp.Scenario]):
    similar_scenario_lst = [s for s in scenario_list if s.forecast_store_request.read().store_id == selected_store]
    return create_scenario_summary_df(similar_scenario_lst)

create_md = Markdown(create_template.substitute())


def create_scenario(state):
    fsr = ForecastStoreRequest(
        store_id=state.selected_store, 
        dates=[state.selected_week_start + dt.timedelta(days=n) for n in range(7)]
    )
    scenario = tp.create_scenario(sales_forecast_scenario_cfg, name=fsr_to_label(fsr))
    scenario.name += f" | id={scenario.id[-4:]}"
    scenario.forecast_store_request.write(fsr)
    scenario.cutoff_date.write(state.selected_week_start)
    scenario.promo_flag.write(state.promo_flag)
    scenario.air_pollution.write(int(state.selected_air_pollution))
    notify(state, "I", "Scenario submitted. Please wait...")
    scenario.submit(wait=True)
    notify(state, "S", "Scenario executed successfully!")
    state.scenario_list = get_ordered_scenarios()
    state.selected_scenario = scenario

def create_on_init(state):
    ...

root_var_update_list = ["selected_scenario", "scenario_list"]
def create_on_navigate(state):
    for var_name in root_var_update_list:
        create_on_change(state, var_name, getattr(state, var_name))

def create_on_change(state, var_name, var_value):
    # root variables
    if var_name == "":
        ...

    # module variables
    elif var_name == "":
        ...