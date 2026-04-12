from flask import Flask, Blueprint, request, jsonify
import math
try:
    from iapws import IAPWS97
except ImportError:
    IAPWS97 = None
import os
from typing import Dict, Any, Optional, Callable, Union, Tuple, List


def get_steam_enthalpy(temp_celsius, pressure_bar):
    if IAPWS97 is None:
        return 0.0
    steam = IAPWS97(T=temp_celsius + 273, P=pressure_bar * 0.0980665)
    return steam.h / 4.1868


__all__ = [
    'Flask', 'Blueprint', 'request', 'jsonify',
    'math', 'os',
    'IAPWS97', 'get_steam_enthalpy',
    'Dict', 'Any', 'Optional', 'Callable', 'Union', 'Tuple', 'List',
]