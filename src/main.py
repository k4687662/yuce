from icecream import ic
import datetime as dt
import plotly.graph_objs as go

from db.schema import ForecastStoreRequest


def dt_prefix():
    return f"{dt.datetime.now().strftime('%H:%M:%S')} |> "


ic.configureOutput(prefix=dt_prefix, includeContext=True)
ic.lineWrapWidth = 150

from taipy.gui import Gui, Markdown, navigate, Icon
import taipy as tp
from pages.home import home_md, home_on_init, home_on_change, home_on_navigate
from pages.create import create_md, create_on_init, create_on_change, create_on_navigate
from pages.data import data_md, data_on_init, data_on_change, data_on_navigate
from pages.forecast import forecast_md, forecast_on_init, forecast_on_change, forecast_on_navigate
from pages.compare import compare_md, compare_on_init, compare_on_change, compare_on_navigate
from pages.common import fsr_to_label, create_scenario_summary_df, get_ordered_scenarios, year_week_adapter
from tpconfig.tpconfig import forecast_dates, sales_forecast_scenario_cfg

create_scenario_summary_df
year_week_adapter

scenario_list = []
selected_scenario = None
show_advanced_select = False
root_md = Markdown(
    """
<|menu|lov={page_list}|on_action=menu_navigate|>

<|layout|columns=30em 20em 20em|gap=1em|

#快消品销售预测 ©️

<|part|
**选择场景:**
<|{selected_scenario}|selector|lov={scenario_list}|dropdown|label=Scenario|adapter={lambda scenario: scenario.name}|class_name=fullwidth|>

<|Advanced Select|button|on_action={lambda s: s.assign("show_advanced_select", True)}|> <|Delete 🗑|button|on_action=delete_selected_scenario|>
|>

<|part|
**店铺编号:** <|{selected_scenario.forecast_store_request.read().store_id if bool(selected_scenario) else ""}|>

**Week:** <|{year_week_adapter(selected_scenario.forecast_store_request.read().dates[0]) if bool(selected_scenario) else ""}|>

**提交:** <|{selected_scenario.creation_date.strftime("%c") if bool(selected_scenario) else ""}|>

**Promotion?:** <|{("✔️" if selected_scenario.promo_flag.read() else "❌") if bool(selected_scenario) else ""}|>

**Air Pollution:** <|{str(selected_scenario.air_pollution.read()) if bool(selected_scenario) else ""}|>
|>

|>
--------------------

<|{show_advanced_select}|dialog|on_action={lambda s: s.assign("show_advanced_select",  False)}|labels=Cancel|height=70%|width=80%|
<|container|
### 选择场景
单击一行将其选中.
<br/>
<|{create_scenario_summary_df(scenario_list)}|table|filter|on_action=advanced_select_table_action|>
|>
|>
"""
)


def advanced_select_table_action(state, var_name, payload):
    index = payload.get("index")
    state.selected_scenario = state.scenario_list[index]
    state.show_advanced_select = False


def delete_selected_scenario(state):
    if state.selected_scenario is None:
        return

    tp.delete(state.selected_scenario)
    state.scenario_list = get_ordered_scenarios()
    state.selected_scenario = state.scenario_list[0] if state.scenario_list else None



def on_init(state):
    state.scenario_list = get_ordered_scenarios()
    state.selected_scenario = state.scenario_list[0] if state.scenario_list else None

    home_on_init(state)
    data_on_init(state)
    create_on_init(state)
    forecast_on_init(state)
    compare_on_init(state)


def menu_navigate(state, id, payload):
    """Any navigate logic should be in on_navigate."""

    navigate(state, payload["args"][0], params=dict())


def on_navigate(state, page_name):
    """
    NOTE: When the application first starts, Taipy calls this function with the
    root page (TaiPy_root_page) and the first page.
    """

    # This logic is in an if block because this function is also called where page_name is a partial or root page
    if page_name in list(pages.keys())[1:]:
        state.page = page_name
        ic("Navigating to", page_name)
        if page_name == "home":
            home_on_navigate(state)
        elif page_name == "data":
            data_on_navigate(state)
        elif page_name == "create":
            create_on_navigate(state)
        elif page_name == "forecast":
            forecast_on_navigate(state)
        elif page_name == "compare":
            compare_on_navigate(state)
    return page_name


def on_change(state, var_name, var_value):
    if isinstance(var_value, tp.Scenario) or isinstance(var_value, go.Figure):
        ic(state.page, var_name)
    else:
        ic(state.page, var_name, var_value)

    if state.page == "home":
        home_on_change(state, var_name, var_value)
    elif state.page == "data":
        data_on_change(state, var_name, var_value)
    elif state.page == "create":
        create_on_change(state, var_name, var_value)
    elif state.page == "forecast":
        forecast_on_change(state, var_name, var_value)
    elif state.page == "compare":
        compare_on_change(state, var_name, var_value)


pages = {
    "/": root_md,
    "home": home_md,
    "create": create_md,
    "data": data_md,
    "forecast": forecast_md,
    "compare": compare_md,
}
page_list = [
    ("home", Icon("assets/images/home_white_24dp.svg", "Home")),
    ("create", Icon("assets/images/create_white_24dp.svg", "Create")),
    ("data", Icon("assets/images/analytics_white_24dp.svg", "Data Explorer")),
    ("forecast", Icon("assets/images/insights_white_24dp.svg", "Forecast Explorer")),
    ("compare", Icon("assets/images/compare_white_24dp.svg", "Scenario Comparison")),
]
page = page_list[0]


def create_first_scenario():
    """This scenario will be created at application launch."""

    selected_week_start = forecast_dates[0]
    fsr = ForecastStoreRequest(store_id="001", dates=[selected_week_start + dt.timedelta(days=n) for n in range(7)])
    promo_flag = True
    air_pollution = 0
    scenario = tp.create_scenario(sales_forecast_scenario_cfg, name=fsr_to_label(fsr))
    scenario.name += f" | id={scenario.id[-4:]}"
    scenario.forecast_store_request.write(fsr)
    scenario.cutoff_date.write(selected_week_start)
    scenario.promo_flag.write(promo_flag)
    scenario.air_pollution.write(air_pollution)
    tp.submit(scenario, wait=True)


if __name__ == "__main__":
    tp.Core().run()

    create_first_scenario()

    stylekit = {
        "color_primary": "#023047",
        "color_secondary": "#ffb703",
    }

    gui_properties = {
        "dark_mode": False,
        "title": "快消品销售预测",
        "favicon": "assets/images/lunch_dining_white_24dp.svg",
        "run_browser": False,
        "use_reloader": True,
        "stylekit": stylekit,
        "time_zone": "Etc/UTC",
    }

    gui = Gui(pages=pages)
    gui.run(**gui_properties)