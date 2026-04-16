from flask import Flask, Blueprint, request, jsonify
import math
import os
import time
import requests
try:
    from iapws import IAPWS97
except ImportError:
    IAPWS97 = None
try:
    from flask_cors import CORS
except ImportError:
    CORS = None

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Callable, Union, Tuple, List
from datetime import datetime


def get_steam_enthalpy(temp_celsius, pressure_bar):
    if IAPWS97 is None:
        return 0.0
    steam = IAPWS97(T=temp_celsius + 273, P=pressure_bar * 0.0980665)
    return steam.h / 4.1868


__all__ = [
    'Flask', 'Blueprint', 'request', 'jsonify',
    'math', 'os', 'time', 'requests',
    'pd', 'np',
    'datetime',
    'IAPWS97', 'get_steam_enthalpy', 'CORS',
    'Dict', 'Any', 'Optional', 'Callable', 'Union', 'Tuple', 'List',
]