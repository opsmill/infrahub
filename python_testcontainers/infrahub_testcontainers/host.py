import platform
from typing import Any

import psutil


def get_system_stats() -> dict[str, Any]:
    """
    Gather and return key system statistics about CPU, memory and platform
    Returns a dictionary with system information
    """
    # CPU information
    cpu_freq = psutil.cpu_freq()
    cpu_stats = {
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_freq_current": float(f"{cpu_freq.current:.2f}") if cpu_freq else None,  # MHz
        "cpu_freq_min": float(f"{cpu_freq.min:.2f}") if cpu_freq else None,  # MHz
        "cpu_freq_max": float(f"{cpu_freq.max:.2f}") if cpu_freq else None,  # MHz
        "cpu_percent": psutil.cpu_percent(interval=1, percpu=False),
    }

    # Memory information
    memory = psutil.virtual_memory()
    memory_stats = {
        "total_memory": float(f"{memory.total / (1024**3):.2f}"),  # GB
        "available_memory": float(f"{memory.available / (1024**3):.2f}"),  # GB
        "memory_percent_used": memory.percent,
        "memory_used": float(f"{memory.used / (1024**3):.2f}"),  # GB
    }

    # Platform information
    platform_stats = {
        "system": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
    }

    return {"cpu": cpu_stats, "memory": memory_stats, "platform": platform_stats}
