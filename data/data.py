import numpy as np
import pandas as pd
from scipy.stats import skewnorm
import datetime as dt
import itertools, math, warnings
from dateutil.relativedelta import relativedelta, MO

np.random.seed(0)

_freq = dt.timedelta(minutes=30)
_sample_sections = ["MAINS", "SIDES", "BEVERAGE"]
_sample_indicators = ["Transactions"]  # we will generate "Items" and "Sales", based on "Transactions"

_default_beverage_size = 500
_default_mains_size = 1500
_default_sides_size = 1000

# the following multipliers will be randomised from a normal distribution with scale mu/10
_STD_PCT_OF_MEAN = 0.1
_weekend_multiplier = 1.6
_default_items_multiplier = 2.5  # based on "Transactions"
_default_sales_multiplier = 3.5 * 100  # based on "Items", expressed in cents


def _generate_sales_distribution(target_total_sum):
    """Generate a sales distribution.

    The sum of the distribution will be `target_total_sum` at max, often less (due to truncating floating points).
    """

    size = 5000
    bins = 48
    assert pd.Timedelta(days=1) / _freq == bins
    mu = 100
    _n = size / 1.375  # 1 from midday peak, 0.375 (1/2 * 0.75) from dinner peak
    n = int(np.random.normal(_n, _n / 10))
    arr = np.random.normal(mu, mu / 50, size=n)

    midday_peak, _ = np.histogram(arr, bins=bins)
    dinner_peak, _ = np.histogram(skewnorm.rvs(-3, loc=mu, scale=mu / 10, size=int(n / 2)), bins=int(bins / 2))
    dinner_peak_padded = np.hstack((np.zeros(int(bins / 2)), dinner_peak * 0.75))

    arr = midday_peak + dinner_peak_padded

    arr *= target_total_sum / np.sum(arr)
    arr = arr.astype(int)

    return arr


def _generate_transactions_for_indicator(start_date: dt.date, end_date: dt.date, size: int) -> pd.DataFrame:
    "end_date is inclusive"

    end_date = end_date + dt.timedelta(days=1)
    date_range = pd.date_range(start_date, end_date, freq=_freq, name="start_time", inclusive="left")

    sales_distribution_list = []
    date_list = date_range.to_series().dt.date.unique()
    for date in date_list:
        _size = size
        if date.weekday() in [5, 6]:
            _size = _size * np.random.normal(_weekend_multiplier, _STD_PCT_OF_MEAN * _weekend_multiplier)
        sales_distribution = _generate_sales_distribution(_size).astype(int)
        sales_distribution_list.append(sales_distribution)

    df = pd.DataFrame(index=date_range, data={"value": np.hstack(sales_distribution_list)})
    return df


def _generate_items_from_transactions(transactions_df: pd.DataFrame, base_multiplier: float) -> pd.DataFrame:
    items_df = transactions_df.copy()
    multiplier_array = np.random.normal(base_multiplier, _STD_PCT_OF_MEAN * base_multiplier, len(items_df))
    items_df["value"] = (items_df["value"] * multiplier_array).astype(int)
    return items_df


def _generate_sales_from_items(items_df: pd.DataFrame, base_multiplier: float) -> pd.DataFrame:
    sales_df = items_df.copy()
    multiplier_array = np.random.normal(base_multiplier, _STD_PCT_OF_MEAN * base_multiplier, len(sales_df))
    sales_df["value"] = (sales_df["value"] * multiplier_array).astype(int)
    return sales_df


def _generate_actual_df(store_list: list[str], start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    dfs = []

    for store_id, zone in itertools.product(store_list, _sample_sections):
        store_multiplier = np.random.rand() + 0.5
        if zone == "MAINS":
            size = _default_mains_size * store_multiplier
        elif zone == "SIDES":
            size = _default_sides_size * store_multiplier
        elif zone == "BEVERAGE":
            size = _default_beverage_size * store_multiplier
        else:
            raise ValueError(f"Unknown zone: {zone}")

        transactions_df = _generate_transactions_for_indicator(start_date, end_date, size=size)
        transactions_df["store_id"] = store_id
        transactions_df["section"] = zone
        transactions_df["indicator"] = "Transactions"

        items_df = _generate_items_from_transactions(transactions_df, _default_items_multiplier)
        items_df["store_id"] = store_id
        items_df["section"] = zone
        items_df["indicator"] = "Items"

        sales_df = _generate_sales_from_items(items_df, _default_sales_multiplier)
        sales_df["store_id"] = store_id
        sales_df["section"] = zone
        sales_df["indicator"] = "Sales"

        dfs.append(transactions_df)
        dfs.append(items_df)
        dfs.append(sales_df)

    actual_df = pd.concat(dfs).reset_index().reset_index(drop=True)
    actual_df = actual_df.loc[:, ["start_time", "store_id", "section", "indicator", "value"]]
    actual_df.store_id = actual_df.store_id.astype("category")
    actual_df.section = actual_df.section.astype("category")
    actual_df.indicator = actual_df.indicator.astype("category")
    return actual_df


def get_data(n_stores: int = 10) -> pd.DataFrame:
    """Generate data for n_stores stores."""

    sample_stores = [f"{i+1:03}" for i in range(n_stores)]

    # First Monday in 2023
    start_date = dt.date(2023, 1, 1)
    start_date = start_date + relativedelta(weekday=MO(+1))
    # end date is the Sunday of the final week (beginning Monday) for March 2024
    end_date = dt.date(2024, 3, 31)
    end_date = end_date + relativedelta(weekday=MO(-1))
    end_date = end_date + dt.timedelta(days=6)
    actual_df = _generate_actual_df(sample_stores, start_date, end_date)

    actual_df["week"] = actual_df["start_time"].dt.to_period("W-SUN").dt.start_time
    promo_chance = 0.3
    promo_multiplier = 1.3

    def apply_promo(df: pd.DataFrame) -> pd.DataFrame:
        promo_df = df.reset_index().copy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            weeks_in_2023 = list(promo_df[promo_df.week.dt.year == 2023].week.drop_duplicates().dt.to_pydatetime())
            weeks_in_2024 = list(promo_df[promo_df.week.dt.year == 2024].week.drop_duplicates().dt.to_pydatetime())

        # sample from 2023 and 2024 separately so 30% of the in-sample forecast (which occurs in 2024) will be promos
        promo_week_list = sorted(
            np.random.choice(weeks_in_2023, math.ceil(len(weeks_in_2023) * promo_chance), replace=False)
        )
        promo_week_list += sorted(
            np.random.choice(weeks_in_2024, math.ceil(len(weeks_in_2024) * promo_chance), replace=False)
        )

        promo_df["promo"] = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            promo_df.loc[pd.Series(promo_df.week.dt.to_pydatetime()).isin(promo_week_list), "promo"] = 1

        promo_df.loc[promo_df.promo == 1, "value"] = (
            promo_df.loc[promo_df.promo == 1, "value"] * promo_multiplier
        ).astype(int)
        return promo_df

    actual_df = (
        actual_df.groupby(by="store_id", observed=True)
        .apply(apply_promo, include_groups=False)
        .reset_index(0)
        .set_index("index", drop=True)
    )

    def apply_pollution(df: pd.DataFrame) -> pd.DataFrame:
        """Apply pollution (0-5) to the data.

        Pollution is a value between 0-5, where 0 is no pollution and 5 is maximum pollution. Pollution affects the data
        as a multiplier to the value, where the multiplier is 1-(pollution/10).
        """
        pollution_df = df.reset_index().copy()
        pollution = np.ceil((1 - np.cbrt(np.random.rand())) * 6) - 1
        pollution_multiplier = 1 - (pollution / 10)
        pollution_df["pollution"] = pollution
        pollution_df["value"] = (pollution_df["value"] * pollution_multiplier).astype(int)
        return pollution_df

    actual_df = (
        actual_df.groupby(by=["store_id", "week"], observed=True)
        .apply(apply_pollution, include_groups=False)
        .reset_index(0)
        .set_index("index", drop=True)
    )

    return actual_df