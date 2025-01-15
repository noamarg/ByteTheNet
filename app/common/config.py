# app/common/config.py
import os
from enum import Enum
from dotenv import load_dotenv

class EnvVarType(Enum):
    INT = 1
    HEX = 2
    FLOAT = 3
    STR = 4

DEFAULT_CONFIG = {
    "MAGIC_COOKIE": ("0xabcddcba", EnvVarType.HEX),
    "MSG_TYPE_OFFER": ("0x2", EnvVarType.HEX),
    "MSG_TYPE_REQUEST": ("0x3", EnvVarType.HEX),
    "MSG_TYPE_PAYLOAD": ("0x4", EnvVarType.HEX),

    "BROADCAST_PORT": ("13118", EnvVarType.INT),
    "BROADCAST_INTERVAL": ("1.0", EnvVarType.FLOAT),

    "MAX_TCP_CONNECTIONS": ("999", EnvVarType.INT),
}

def get_config() -> dict[str, any]:
    # Load environment variables from .env
    load_dotenv()

    # Get environment variables
    config = {}
    for key, (default_val, var_type) in DEFAULT_CONFIG.items():
        val = os.getenv(key, default_val)
        if var_type == EnvVarType.INT:
            val = int(val)
        elif var_type == EnvVarType.HEX:
            val = int(val, 16)
        elif var_type == EnvVarType.FLOAT:
            val = float(val)
        elif var_type == EnvVarType.STR:
            val = str(val)
        else:
            raise ValueError(f"Unknown EnvVarType: {var_type}")
        config[key] = val

    return config
