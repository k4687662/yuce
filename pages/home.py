from taipy.gui import Markdown
from string import Template

from pages.common import create_scenario_summary_df

create_scenario_summary_df

home_template = Template(
"""
## Introduction

A sales forecasting application **built with Taipy**{: .color-primary} for Quick-Service Restaurants (QSR).

<|part|render={selected_scenario is None}|
To begin, **[create a scenario](/create)**{: .color-primary}.
|>

### Available Scenarios

<|{create_scenario_summary_df(scenario_list)}|table|width=fit-content|filter|allow_all_rows|date_format=yyyy-MM-dd HH:mm:SS|>
""")


home_md = Markdown(home_template.substitute())

def home_on_init(state):
    ...

root_var_update_list = []
def home_on_navigate(state):
    for var_name in root_var_update_list:
        home_on_change(state, var_name, getattr(state, var_name))

def home_on_change(state, var_name, var_value):
    # root variables
    if var_name == "":
        ...

    # module variables
    elif var_name == "":
        ...