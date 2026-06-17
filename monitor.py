import subprocess
import psutil
import time
import csv
import os
import sys
import argparse
import threading
from datetime import datetime
from collections import defaultdict


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
        psutil.cpu_percent()  # descarta primeira leitura (sempre 0.0)
        while not stop_event.is_set():
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().used / (1024 * 1024)
            samples.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "epoch": current_epoch[0],
                    "cpu_percent": round(cpu, 2),
                    "ram_mb": round(ram, 1),
                }
            )

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

    samples_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_samples.csv"
    )
    with open(samples_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["timestamp", "epoch", "cpu_percent", "ram_mb"]
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
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "epoch",
                "mean_cpu",
                "max_cpu",
                "mean_ram_mb",
                "max_ram_mb",
                "samples",
            ],
        )
        writer.writeheader()
        for epoch in sorted(epoch_data.keys()):
            rows = epoch_data[epoch]
            cpus = [r["cpu_percent"] for r in rows]
            rams = [r["ram_mb"] for r in rows]
            writer.writerow(
                {
                    "epoch": epoch,
                    "mean_cpu": round(sum(cpus) / len(cpus), 2),
                    "max_cpu": round(max(cpus), 2),
                    "mean_ram_mb": round(sum(rams) / len(rams), 1),
                    "max_ram_mb": round(max(rams), 1),
                    "samples": len(rows),
                }
            )

    total_path = os.path.join(
        output_dir, f"{args.scenario}_run{args.run}_total.txt"
    )
    with open(total_path, "w") as f:
        f.write(f"{total_elapsed:.2f}\n")

    print(f"\n[monitor] Cenário: {args.scenario} | Run: {args.run}")
    print(f"[monitor] Tempo total: {total_elapsed:.2f}s")
    print(f"[monitor] Amostras: {samples_path}")
    print(f"[monitor] Sumário:  {summary_path}")

    sys.exit(training_proc.returncode)


if __name__ == "__main__":
    main()
