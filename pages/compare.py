from taipy.gui import Markdown
import taipy as tp
from string import Template
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from pages.common import create_scenario_summary_df, year_week_adapter
from tpconfig.tpconfig import FCST_SMA_KEY, FCST_XGB_KEY
from sklearn.metrics import mean_squared_error


year_week_adapter

section_list = []
selected_section = None

indicator_list = []
selected_indicator = None

similar_scenario_lov = []
compared_scenario = None
show_similar_scenarios_only = True

show_compared_advanced_select = False

fig = None
xgb_mse_scenario_a = 0
xgb_mse_scenario_b = 0
compare_template = Template(
    """
## Scenario Comparison

Compare **Scenario A**{: style="color: $scenario_a_color;"} (selected in the top panel) with **Scenario B**{: style="color: $scenario_b_color;"} (selected below).

<br/>

<top|card|

<|layout|columns=1 1|gap=1.5em|

<select_scenario|part|
### Compared Scenario (Scenario B)

**Filter list to store & week of Scenario A:** <|{show_similar_scenarios_only}|toggle|>

<filter|part|render={show_similar_scenarios_only==True}|
<|{compared_scenario}|selector|lov={similar_scenario_lov}|dropdown|label=Scenario B (filtered)|adapter={lambda scenario: scenario.name}|class_name=fullwidth|>
|filter>

<nofilter|part|render={show_similar_scenarios_only==False}|
<|{compared_scenario}|selector|lov={scenario_list}|dropdown|label=Scenario B (all)|adapter={lambda scenario: scenario.name}|class_name=fullwidth|>
|nofilter>

<|Advanced Select|button|on_action={lambda s: s.assign("show_compared_advanced_select", True)}|>
|select_scenario>

<scenario_b_metadata|part|
#### Scenario B Metadata

**Store ID:** <|{compared_scenario.forecast_store_request.read().store_id if bool(compared_scenario) else ""}|>

**Week:** <|{year_week_adapter(compared_scenario.forecast_store_request.read().dates[0]) if bool(compared_scenario) else ""}|>

**Submitted on:** <|{compared_scenario.creation_date.strftime("%c") if bool(compared_scenario) else ""}|>

**Promotion?:** <|{("✔️" if compared_scenario.promo_flag.read() else "❌") if bool(compared_scenario) else ""}|>

**Air Pollution:** <|{str(compared_scenario.air_pollution.read()) if bool(compared_scenario) else ""}|>
|scenario_b_metadata>

|>

|top>

<br/>

<|layout|columns=5 2|

<middle|card|
<selectors|layout|columns=1 1|
<|{selected_section}|selector|lov={section_list}|dropdown|label=Section|class_name=fullwidth|>

<|{selected_indicator}|selector|lov={indicator_list}|dropdown|label=Indicator|class_name=fullwidth|>
|selectors>

<|chart|figure={fig}|>
|middle>

<rhs|card|
<kpi|layout|columns=1 1|

<|card p-half m-half text-center card-font card-bg|
**XGB MSE**{: .color-primary} <br/>
**[Scenario A]**{: style="color: $scenario_a_color;"}

<|{xgb_mse_scenario_a}|text|raw|format=%,.2f|>
|>

<|card p-half m-half text-center card-font card-bg|
**XGB MSE**{: .color-primary} <br/>
**[Scenario B]**{: style="color: $scenario_b_color;"}

<|{xgb_mse_scenario_b}|text|raw|format=%,.2f|>
|>

|kpi>

<|{create_side_by_side_comparison_table(selected_scenario, compared_scenario)}|table|show_all|>

|rhs>
|>

<|{show_compared_advanced_select}|dialog|on_action={lambda s: s.assign("show_compared_advanced_select",  False)}|labels=Cancel|height=70%|width=80%|
<|container|
### Select Compared Scenario **(Scenario B)**{: style="color: $scenario_b_color;"}

***Scenario A*{: style="color: $scenario_a_color;"} Store ID:** <|{selected_scenario.forecast_store_request.read().store_id if selected_scenario is not None else ""}|>

***Scenario A*{: style="color: $scenario_a_color;"} Week:** <|{selected_scenario.forecast_store_request.read().dates[0].strftime("%Y-%m-%d") if selected_scenario is not None else ""}|>

Filter list to store & week of **Scenario A**{: style="color: $scenario_a_color;"}:

<|{show_similar_scenarios_only}|toggle|>

Click a row to select it.
<br/>
<|{create_scenario_summary_df(similar_scenario_lov if show_similar_scenarios_only else scenario_list)}|table|filter|on_action=compared_advanced_select_table_action|>
|>
|>
"""
)


def create_side_by_side_comparison_table(scenario_a, scenario_b):
    if scenario_a is None or scenario_b is None:
        return []

    # We convert all columns to str because pandas stores dtype column-wise
    # If 
    scenario_a_summary_df = create_scenario_summary_df([scenario_a]).astype(str)
    scenario_b_summary_df = create_scenario_summary_df([scenario_b]).astype(str)
    
    df = pd.concat([scenario_a_summary_df.T, scenario_b_summary_df.T], axis=1)
    df.columns = ["Scenario A", "Scenario B"]
    
    return df.reset_index()


def compared_advanced_select_table_action(state, var_name, payload):
    index = payload.get("index")
    state.compared_scenario = state.scenario_list[index] if state.show_similar_scenarios_only else state.similar_scenario_lov[index]
    state.show_compared_advanced_select = False


scenario_a_color = px.colors.qualitative.D3[0]
scenario_b_color = px.colors.qualitative.D3[3]

compare_md = Markdown(compare_template.substitute(scenario_a_color=scenario_a_color, scenario_b_color=scenario_b_color))

def create_scenario_comparison_line_chart(state):
    selected_section = state.selected_section
    selected_indicator = state.selected_indicator

    if state.selected_scenario is None or state.compared_scenario is None or selected_section is None or selected_indicator is None:
        return px.line()

    data_df1 = state.selected_scenario.data_df.read()
    data_df2 = state.compared_scenario.data_df.read()
    df1 = data_df1[(data_df1.section == selected_section) & (data_df1.indicator == selected_indicator)].copy()
    df2 = data_df2[(data_df2.section == selected_section) & (data_df2.indicator == selected_indicator)].copy()

    y_vars = ["value", FCST_XGB_KEY]
    main_fig = px.line(df1, x="start_time", y=y_vars, title="Forecast over Time")
    main_fig.update_traces(line_color=scenario_a_color)
    main_fig.for_each_trace(lambda t: t.update(name=t.name+"_ScenarioA", legendgroup=t.legendgroup+"_ScenarioA"))
    sub_fig = px.line(df2, x="start_time", y=y_vars)
    sub_fig.update_traces(line_color=scenario_b_color)
    sub_fig.for_each_trace(lambda t: t.update(name=t.name+"_ScenarioB", legendgroup=t.legendgroup+"_ScenarioB"))
    main_fig.add_traces(sub_fig.data)

    main_fig.for_each_trace(lambda t: t.update(line_dash="dot"), selector=lambda t: t.name.startswith(FCST_XGB_KEY))
    main_fig.for_each_trace(lambda t: t.update(visible="legendonly"), selector=lambda t: not t.name.startswith(FCST_XGB_KEY))
    main_fig.update_layout(xaxis1=dict(title_text="start_time"), yaxis=dict(title_text="value"))

    # Add x-axis2
    main_fig.update_layout(xaxis2=dict(anchor='y', overlaying='x', side='top', title_text="start_time (Scenario B)", color=scenario_b_color), xaxis1=dict(title_text="start_time (Scenario A)", color=scenario_a_color))
    n_y_vars = len(y_vars)
    for i in range(n_y_vars, n_y_vars*2):
        main_fig.data[i].update(xaxis="x2")
    
    return main_fig


def get_similar_scenarios(selected_scenario) -> list[tp.Scenario]:
    if selected_scenario is None:
        return []

    all_scenarios = tp.get_scenarios()
    similar_scenario_lst = [
        s for s in all_scenarios if s.forecast_store_request.read() == selected_scenario.forecast_store_request.read()
    ]
    similar_scenario_lst.sort(key=lambda s: s.creation_date, reverse=True)

    return similar_scenario_lst


def compare_on_init(state):
    if state.selected_scenario is not None:
        state.similar_scenario_lov = get_similar_scenarios(state.selected_scenario)
        state.compared_scenario = state.similar_scenario_lov[0]


root_var_update_list = ["selected_scenario"]


def compare_on_navigate(state):
    if isinstance(state.compared_scenario, tp.Scenario) and not tp.exists(state.compared_scenario.id):
        state.compared_scenario = None

    # TODO: This refresh takes some time and delays the navigation
    # Is there a way to avoid this refresh if the page is already "valid"?
    for var_name in root_var_update_list:
        state.assign(var_name, getattr(state, var_name))


def compare_on_change(state, var_name, var_value):
    # root variables
    if var_name == "selected_scenario":
        state.similar_scenario_lov = get_similar_scenarios(var_value)
        if var_value is None:
            state.compared_scenario = None
        elif state.compared_scenario is None:
            state.compared_scenario = state.similar_scenario_lov[0]
        elif state.show_similar_scenarios_only and state.compared_scenario not in state.similar_scenario_lov:
            # if we are filtering compared scenarios and the current compared scenario is not in the list of similar scenarios, then just use the first one
            state.compared_scenario = state.similar_scenario_lov[0]
        
        _section_list = var_value.store_df.read().section.drop_duplicates().tolist() if var_value is not None else []
        state.section_list = _section_list if state.section_list != _section_list else state.section_list      
        state.selected_section = state.section_list[0] if state.section_list != [] else None
    # module variables
    elif var_name == "show_similar_scenarios_only":
        if var_value is True and state.compared_scenario not in state.similar_scenario_lov:
            state.compared_scenario = state.similar_scenario_lov[0]
    elif var_name == "selected_section":
        _indicator_list = state.selected_scenario.store_df.read().indicator.drop_duplicates().tolist() if state.selected_scenario is not None else []
        state.indicator_list = _indicator_list if state.indicator_list != _indicator_list else state.indicator_list
        state.selected_indicator = state.indicator_list[0] if state.indicator_list != [] else None
    if var_name in {"selected_section", "selected_indicator", "compared_scenario"}:
        state.fig = create_scenario_comparison_line_chart(state)
        if state.selected_scenario is not None and state.compared_scenario is not None and state.selected_section is not None and state.selected_indicator is not None:
            _df_a = state.selected_scenario.data_df.read()
            _df_a = _df_a[(_df_a.section == state.selected_section) & (_df_a.indicator == state.selected_indicator)]
            _df_b = state.compared_scenario.data_df.read()
            _df_b = _df_b[(_df_b.section == state.selected_section) & (_df_b.indicator == state.selected_indicator)]
            state.xgb_mse_scenario_a = mean_squared_error(_df_a.value, _df_a[FCST_XGB_KEY])
            state.xgb_mse_scenario_b = mean_squared_error(_df_b.value, _df_b[FCST_XGB_KEY])
        else: 
            state.xgb_mse_scenario_a = 0
            state.xgb_mse_scenario_b = 0