"""Conservative admission control based on current host and worker measurements."""
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import psutil
from .runtime import GIB


@dataclass
class Resources:
    total: int
    available: int
    cores: int
    cpu_busy: float
    swap_used: int

    def public(self):
        return dict(total_gb=round(self.total / GIB, 1), available_gb=round(self.available / GIB, 1),
                    cores=self.cores, cpu_busy=round(self.cpu_busy), swap_gb=round(self.swap_used / GIB, 1))


def snapshot(interval=.15):
    memory = psutil.virtual_memory()
    total, available = memory.total, memory.available
    cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    # Respect container limits rather than allocating against the host's entire RAM/CPU.
    try:
        limit = int(Path('/sys/fs/cgroup/memory.max').read_text().strip())
        used = int(Path('/sys/fs/cgroup/memory.current').read_text().strip())
        total, available = min(total, limit), min(available, max(0, limit - used))
    except (OSError, ValueError):
        pass
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        cores = min(cores, max(1, math.floor(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    return Resources(total, available, cores, psutil.cpu_percent(interval), psutil.swap_memory().used)


def reserve_bytes(resources):
    return max(1 * GIB, int(resources.total * .15))


def worker_memory(peak_rss=0, duration=0):
    # NeMo buffers audio/features; account for long recordings in addition to measured model RSS.
    return max(3 * GIB, int(peak_rss * 1.4)) + int(duration * 240_000)


def validate_parallel(value):
    if value != "auto" and (type(value) is not int or not 1 <= value <= 5):
        raise ValueError("Выберите «Авто» или число от 1 до 5.")
    return value


def plan(resources, count, peak_rss=0, duration=0, parallel="auto"):
    validate_parallel(parallel)
    memory = worker_memory(peak_rss, duration)
    memory_slots = max(0, (resources.available - reserve_bytes(resources)) // memory)
    free_cores = max(1, math.floor(resources.cores * (1 - resources.cpu_busy / 100)))
    cpu_slots = max(1, free_cores // 2)
    slots = min(5, count, memory_slots, cpu_slots if parallel == "auto" else parallel)
    threads = max(1, min(6, free_cores // max(1, slots)))
    return dict(mode=parallel, parallel=int(slots), no_work=count == 0, threads=threads, worker_gb=round(memory / GIB, 2),
                reserve_gb=round(reserve_bytes(resources) / GIB, 2), resources=resources.public(),
                reason=f"Доступно {resources.available / GIB:.1f} ГБ; резерв {reserve_bytes(resources) / GIB:.1f} ГБ; "
                       f"оценка на запись {memory / GIB:.1f} ГБ; свободных ядер ≈ {free_cores}.")
