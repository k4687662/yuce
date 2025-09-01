import pandas as pd
from dateutil import tz

LOCAL_TZ = tz.tzlocal()
TIME_STEP = pd.Timedelta(minutes=30)