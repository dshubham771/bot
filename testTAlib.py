import talib
import numpy as np

# print(talib.get_functions())

print(talib.stream_EMA(np.random.randn(100), timeperiod=15))
