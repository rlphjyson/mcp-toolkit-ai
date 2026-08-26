from dataclasses import dataclass

import psutil


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str | None
    cpu_percent: float
    memory_mb: float


def list_processes(name_filter: str = "") -> list[ProcessInfo]:
    needle = name_filter.lower()
    results = []
    for proc in psutil.process_iter(["pid", "name", "username", "memory_info"]):
        info = proc.info
        name = info.get("name") or ""
        if needle and needle not in name.lower():
            continue
        memory_info = info.get("memory_info")
        memory_mb = round(memory_info.rss / (1024 * 1024), 1) if memory_info else 0.0
        try:
            cpu_percent = proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        results.append(
            ProcessInfo(
                pid=info["pid"],
                name=name,
                username=info.get("username"),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
            )
        )
    return results
