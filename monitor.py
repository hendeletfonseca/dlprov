import subprocess
import time
import csv
import json
import os
import sys
import argparse
import threading
from datetime import datetime
from collections import defaultdict

import sysmetrics


def main():
    parser = argparse.ArgumentParser(description="Monitor CPU/RAM during DL training")
    parser.add_argument("--script", required=True, help="Training script path")
    parser.add_argument("--scenario", required=True, help="com-prov or sem-prov")
    parser.add_argument("--run", type=int, required=True, help="Run number (1-5)")
    args = parser.parse_args()

    output_dir = "/opt/dlprov/results"
    os.makedirs(output_dir, exist_ok=True)

    samples = []
    stop_event = threading.Event()
    current_epoch = [0]

    def sample_loop():
        prev_cpu = sysmetrics.container_cpu_ns()
        while not stop_event.is_set():
            time.sleep(1)
            curr_cpu = sysmetrics.container_cpu_ns()
            cpu_container = (curr_cpu - prev_cpu) / 1e7
            ram_container = sysmetrics.container_memory_mb()
            cpu_host = sysmetrics.host_cpu_percent()
            ram_host = sysmetrics.host_memory_mb()
            samples.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "epoch": current_epoch[0],
                    "cpu_percent": round(cpu_container, 2),
                    "ram_mb": round(ram_container, 1),
                    "host_cpu_percent": round(cpu_host, 2),
                    "host_ram_mb": round(ram_host, 1),
                }
            )
            prev_cpu = curr_cpu

    training_proc = subprocess.Popen(
        ["python", args.script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    monitor_thread = threading.Thread(target=sample_loop, daemon=True)
    monitor_thread.start()

    start_time = time.time()
    for line in training_proc.stdout:
        print(line, end="", flush=True)
        stripped = line.strip()
        if stripped.startswith("Epoch "):
            try:
                epoch_num = int(stripped.split("/")[0].split(" ")[-1])
                current_epoch[0] = epoch_num
            except (ValueError, IndexError):
                pass

    training_proc.wait()
    total_elapsed = time.time() - start_time
    stop_event.set()
    monitor_thread.join()

    specs = sysmetrics.machine_specs()

    samples_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_samples.csv"
    )
    with open(samples_path, "w", newline="") as f:
        f.write(f"# container: cpu_percent = % de 1 core, ram_mb = cgroup. host: host_cpu_percent = % total, host_ram_mb = /proc/meminfo\n")
        f.write(f"# host specs: {specs['host_cpu_cores']} CPUs, {specs['host_ram_gb']}GB RAM | container limit: {specs['container_cpu_limit_cores']} CPUs, {specs['container_ram_limit_gb']}GB RAM\n")
        writer = csv.DictWriter(
            f, fieldnames=["timestamp", "epoch", "cpu_percent", "ram_mb", "host_cpu_percent", "host_ram_mb"]
        )
        writer.writeheader()
        writer.writerows(samples)

    epoch_data = defaultdict(list)
    for s in samples:
        epoch_data[s["epoch"]].append(s)

    summary_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_summary.csv"
    )
    with open(summary_path, "w", newline="") as f:
        f.write(f"# container: cpu_percent = % de 1 core, ram_mb = cgroup. host: host_cpu_percent = % total, host_ram_mb = /proc/meminfo\n")
        f.write(f"# host specs: {specs['host_cpu_cores']} CPUs, {specs['host_ram_gb']}GB RAM | container limit: {specs['container_cpu_limit_cores']} CPUs, {specs['container_ram_limit_gb']}GB RAM\n")
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "epoch",
                "mean_cpu",
                "max_cpu",
                "mean_ram_mb",
                "max_ram_mb",
                "mean_host_cpu",
                "max_host_cpu",
                "mean_host_ram_mb",
                "max_host_ram_mb",
                "samples",
            ],
        )
        writer.writeheader()
        for epoch in sorted(epoch_data.keys()):
            rows = epoch_data[epoch]
            cpus = [r["cpu_percent"] for r in rows]
            rams = [r["ram_mb"] for r in rows]
            hcpus = [r["host_cpu_percent"] for r in rows]
            hrams = [r["host_ram_mb"] for r in rows]
            writer.writerow(
                {
                    "epoch": epoch,
                    "mean_cpu": round(sum(cpus) / len(cpus), 2),
                    "max_cpu": round(max(cpus), 2),
                    "mean_ram_mb": round(sum(rams) / len(rams), 1),
                    "max_ram_mb": round(max(rams), 1),
                    "mean_host_cpu": round(sum(hcpus) / len(hcpus), 2),
                    "max_host_cpu": round(max(hcpus), 2),
                    "mean_host_ram_mb": round(sum(hrams) / len(hrams), 1),
                    "max_host_ram_mb": round(max(hrams), 1),
                    "samples": len(rows),
                }
            )

    specs_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_specs.json"
    )
    with open(specs_path, "w") as f:
        json.dump(specs, f, indent=2)

    total_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_total.txt"
    )
    with open(total_path, "w") as f:
        f.write(f"{total_elapsed:.2f}\n")

    print(f"\n[monitor] Cenário: {args.scenario} | Run: {args.run}")
    print(f"[monitor] Tempo total: {total_elapsed:.2f}s")
    print(f"[monitor] Máquina: {specs['host_cpu_cores']} CPUs, {specs['host_ram_gb']}GB RAM host | container limit {specs['container_cpu_limit_cores']} CPUs, {specs['container_ram_limit_gb']}GB RAM")
    print(f"[monitor] Amostras: {samples_path}")
    print(f"[monitor] Sumário:  {summary_path}")
    print(f"[monitor] Specs:    {specs_path}")

    sys.exit(training_proc.returncode)


if __name__ == "__main__":
    main()
