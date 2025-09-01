"""Exposes the public API for reading the sales data."""

from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.utils import TIME_STEP
import sys


df_parquet_path = Path(__file__).parent.parent / "data" / "demo_sales_data.parquet"
print(df_parquet_path)

def read_df(
    store_id: Optional[str] = None,
    section_indicator: Optional[tuple[str, str]] = None,
) -> pd.DataFrame:
    # create df if it doesn't exist
    if not df_parquet_path.exists():
        sys.path.insert(0, str(df_parquet_path.parent.parent))
        from data.data import get_data

        get_data(n_stores=10).to_parquet(df_parquet_path, index=False)

    filters = []
    if store_id:
        filters.append(("store_id", "==", store_id))
    if section_indicator:
        filters.append(("section", "==", section_indicator[0]))
        filters.append(("indicator", "==", section_indicator[1]))

    if filters:
        df = pd.read_parquet(df_parquet_path, filters=filters)
    else:
        df = pd.read_parquet(df_parquet_path)

    return df


def get_tree_mappings_from_tuples(lst: list[tuple]):
    """Get a mapping from a list of tuples.

    E.g., [(1, 2, 3), (1, 4, 5)] -> {1: {2: [3], 4: [5]}}
    """

    tree = lambda: defaultdict(tree)
    d = tree()
    for tup in lst:
        ref = d
        for item in tup[:-2]:
            ref = ref[item]
        if tup[-2] not in ref:
            ref[tup[-2]] = [tup[-1]]
        else:
            ref[tup[-2]].append(tup[-1])
    return d


# stores to sections to indicators
def _get_tree_mappings(df: Optional[pd.DataFrame] = None, store_id: Optional[str] = None) -> dict[str, dict[str, str]]:
    """Get a mapping from stores to sections to indicators.

    E.g., {'001': {'BEVERAGE': ['Items', 'Sales', 'Transactions']}}
    """

    if df is None != store_id is None:
        raise ValueError("df and store_id must be both supplied or both omitted.")

    if df is None:
        df = read_df()
    else:
        df["store_id"] = store_id

    tree_mappings = (
        df.loc[:, ["store_id", "section", "indicator"]]
        .groupby(["store_id"], observed=True)
        .apply(
            lambda df: df.groupby(["section"], observed=True, sort=False).apply(lambda df: df.indicator.unique().tolist()).to_dict()
        )
        .to_dict()
    )
    return tree_mappings


@cache
def get_tree_mappings() -> dict[str, dict[str, str]]:
    return _get_tree_mappings()