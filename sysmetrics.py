import os
import psutil


def _read_cgroup(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _read_cgroup_int(path):
    val = _read_cgroup(path)
    return int(val) if val is not None else None


def container_memory_mb():
    val = _read_cgroup_int("/sys/fs/cgroup/memory.current")
    if val is not None:
        return val / (1024 * 1024)
    val = _read_cgroup_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if val is not None:
        return val / (1024 * 1024)
    return 0.0


def container_cpu_ns():
    val = _read_cgroup("/sys/fs/cgroup/cpu.stat")
    if val is not None:
        for line in val.splitlines():
            if line.startswith("usage_usec"):
                return int(line.split()[1]) * 1000
    val = _read_cgroup_int("/sys/fs/cgroup/cpuacct/cpuacct.usage")
    if val is not None:
        return val
    return 0


def host_cpu_percent():
    return psutil.cpu_percent(interval=0)


def host_memory_mb():
    return psutil.virtual_memory().used / (1024 * 1024)


def machine_specs():
    host_cores = os.cpu_count() or 1

    total_ram_bytes = None
    val = _read_cgroup("/proc/meminfo")
    if val is not None:
        for line in val.splitlines():
            if line.startswith("MemTotal:"):
                total_ram_bytes = int(line.split()[1]) * 1024
                break

    container_cpu_limit = None
    quota = _read_cgroup_int("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period = _read_cgroup_int("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if quota is not None and period is not None and quota > 0:
        container_cpu_limit = quota / period

    container_ram_limit = None
    val = _read_cgroup_int("/sys/fs/cgroup/memory/memory.max_in_bytes")
    if val is None:
        val = _read_cgroup_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if val is not None and val > 0 and val < 10**18:
        container_ram_limit = val / (1024**3)

    return {
        "host_cpu_cores": host_cores,
        "host_ram_gb": round(total_ram_bytes / (1024**3), 1) if total_ram_bytes else None,
        "container_cpu_limit_cores": container_cpu_limit,
        "container_ram_limit_gb": container_ram_limit,
        "cpu_metric": "percentual de 1 core (ex: 200% = 2 cores)",
    }
