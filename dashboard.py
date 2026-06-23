import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS = Path("results")

def read_total(path):
    return float(path.read_text().strip())

def read_summary(path):
    with open(path) as f:
        reader = csv.DictReader(
            [l for l in f if not l.startswith("#")],
            skipinitialspace=True,
        )
        return list(reader)

def discover_experiments():
    pattern = re.compile(r"(.+)_run(\d+)_total\.txt")
    exps = defaultdict(lambda: {"totals": {}, "summaries": {}})
    for f in sorted(RESULTS.glob("*_total.txt")):
        m = pattern.match(f.name)
        if m:
            base, run = m.group(1), int(m.group(2))
            exp_key = base.replace("_run", "").rsplit("_", 1)[0] if "_run" in base else base
            exps[base]["totals"][run] = f
            summary = RESULTS / f"{base}_run{run}_summary.csv"
            if summary.exists():
                exps[base]["summaries"][run] = summary
    return exps

def infer_labels(exp_key):
    if exp_key.startswith("mnist-simple"):
        model = "MNIST Simple"
    elif exp_key.startswith("mnist-torch"):
        model = "MNIST Torch"
    elif exp_key.startswith("alexnet"):
        model = "AlexNet"
    else:
        model = exp_key
    if "sem-prov" in exp_key:
        prov = "Semântica"
    else:
        prov = "Computacional"
    return model, prov

def load_all():
    raw = discover_experiments()
    data = {}
    for exp_key, runs in sorted(raw.items()):
        totals = []
        summaries = []
        for run_num in sorted(runs["totals"]):
            totals.append(read_total(runs["totals"][run_num]))
            if run_num in runs["summaries"]:
                summaries.append(read_summary(runs["summaries"][run_num]))
            else:
                summaries.append([])
        if not totals:
            continue
        model, prov = infer_labels(exp_key)
        data[exp_key] = {
            "label": f"{model} ({prov})",
            "model": model,
            "prov": prov,
            "totals": totals,
            "n_runs": len(totals),
            "mean": statistics.mean(totals),
            "stdev": statistics.stdev(totals) if len(totals) > 1 else 0,
            "summaries": summaries,
            "run_numbers": sorted(runs["totals"].keys()),
        }
    return data

def gen_html(data):
    datasets_json = {}
    for key, d in data.items():
        totals_by_run = {}
        for i, rn in enumerate(d["run_numbers"]):
            totals_by_run[f"Run {rn}"] = d["totals"][i]
        datasets_json[key] = {
            "label": d["label"],
            "model": d["model"],
            "prov": d["prov"],
            "totals": d["totals"],
            "run_numbers": d["run_numbers"],
            "mean": round(d["mean"], 2),
            "stdev": round(d["stdev"], 2),
        }

    epoch_agg = {}
    for key, d in data.items():
        by_epoch = {}
        for run_idx, rows in enumerate(d["summaries"]):
            for row in rows:
                ep = int(row["epoch"])
                if ep not in by_epoch:
                    by_epoch[ep] = {"cpu": [], "ram": []}
                by_epoch[ep]["cpu"].append(float(row["mean_cpu"]))
                by_epoch[ep]["ram"].append(float(row["mean_ram_mb"]))
        agg = []
        for ep in sorted(by_epoch):
            agg.append({
                "epoch": ep,
                "cpu": round(statistics.mean(by_epoch[ep]["cpu"]), 1),
                "ram": round(statistics.mean(by_epoch[ep]["ram"]), 1),
            })
        epoch_agg[key] = agg

    # Group by model for the bar chart
    models_order = ["MNIST Simple", "MNIST Torch", "AlexNet"]
    prov_types = ["Computacional", "Semântica"]
    bar_data = {m: {} for m in models_order}
    for key, d in data.items():
        if d["model"] in bar_data:
            bar_data[d["model"]][d["prov"]] = d["mean"]

    # Build list of experiment groups for the selector
    model_keys = sorted(set(d["model"] for d in data.values()), key=lambda m: models_order.index(m) if m in models_order else 99)
    model_map = {}
    for key, d in data.items():
        model_map.setdefault(d["model"], []).append(key)

    table_headers = sorted(set(rn for d in data.values() for rn in d["run_numbers"]))
    table_headers_json = json.dumps(table_headers)
    models_order_json = json.dumps(models_order)
    prov_types_json = json.dumps(prov_types)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard - dlprov</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
h1 {{ font-size: 1.8rem; margin-bottom: 8px; color: #f8fafc; }}
.subtitle {{ color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 32px; }}
.card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
.card h3 {{ font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
.card .value {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
.card .detail {{ font-size: 0.85rem; color: #64748b; margin-top: 4px; }}
.chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 24px; margin-bottom: 32px; }}
.chart-box {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
.chart-box h3 {{ font-size: 0.95rem; margin-bottom: 12px; color: #f1f5f9; }}
.chart-box canvas {{ width: 100% !important; height: 300px !important; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; }}
th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em; }}
td {{ color: #e2e8f0; }}
tr:hover td {{ background: #1e293b; }}
footer {{ text-align: center; color: #475569; font-size: 0.8rem; margin-top: 32px; }}
</style>
</head>
<body>

<h1>Dashboard dlprov</h1>
<p class="subtitle">Comparação entre proveniência computacional e semântica &mdash; 8 CPUs, 19.3GB RAM (host) · 4 CPUs, 16GB RAM (container)</p>

<div class="cards" id="cards"></div>

<div class="chart-grid">
  <div class="chart-box"><h3>Tempo total médio por experimento</h3><canvas id="chart-total"></canvas></div>
  <div class="chart-box"><h3>CPU por época (média entre runs)</h3><canvas id="chart-cpu"></canvas></div>
  <div class="chart-box"><h3>RAM por época (média entre runs)</h3><canvas id="chart-ram"></canvas></div>
  <div class="chart-box">
    <h3>Tempo por run</h3>
    <div style="margin-bottom:12px">
      <label style="color:#94a3b8;font-size:0.85rem">Experimento: </label>
      <select id="expSelect" style="background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px 10px;font-size:0.9rem">{gen_exp_options(data)}</select>
    </div>
    <canvas id="chart-run"></canvas>
  </div>
</div>

<div class="chart-box" style="margin-bottom:32px">
  <h3>Todas as execuções — tempo total (s)</h3>
  <div style="overflow-x:auto"><table>
    <thead><tr><th>Experimento</th>{"".join(f"<th>Run {rn}</th>" for rn in table_headers)}<th>Média</th><th>Desv. Pad.</th></tr></thead>
    <tbody id="table-body"></tbody>
  </table></div>
</div>

<footer>Gerado por dashboard.py</footer>

<script>
const DATA = {json.dumps(datasets_json)};
const EPOCHS = {json.dumps(epoch_agg)};

// ---- Cards ----
const cardsDiv = document.getElementById('cards');
for (const key of Object.keys(DATA).sort()) {{
  const d = DATA[key];
  const runLabels = d.run_numbers.map(r => `Run ${{r}}: ${{d.totals[d.run_numbers.indexOf(r)]}}s`).join(' &middot; ');
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `<h3>${{d.label}}</h3><div class="value">${{d.mean}}s</div><div class="detail">±${{d.stdev}}s &middot; ${{d.totals.length}} runs &middot; ${{runLabels}}</div>`;
  cardsDiv.appendChild(card);
}}

// ---- Table ----
const tbody = document.getElementById('table-body');
const allRunNums = {table_headers_json};
for (const key of Object.keys(DATA).sort()) {{
  const d = DATA[key];
  const byRun = {{}};
  d.run_numbers.forEach((rn, i) => {{ byRun[rn] = d.totals[i]; }});
  const tr = document.createElement('tr');
  let cells = `<td>${{d.label}}</td>`;
  for (const rn of allRunNums) {{
    cells += `<td>${{byRun[rn] !== undefined ? byRun[rn] + 's' : '—'}}</td>`;
  }}
  cells += `<td><strong>${{d.mean}}s</strong></td><td>±${{d.stdev}}s</td>`;
  tr.innerHTML = cells;
  tbody.appendChild(tr);
}}

// ---- Chart: Total Time ----
const models = {models_order_json};
const provTypes = {prov_types_json};
function buildTotalChart() {{
  const labels = [];
  const comData = [];
  const semData = [];
  for (const m of models) {{
    let com = null, sem = null;
    for (const key of Object.keys(DATA)) {{
      const d = DATA[key];
      if (d.model === m && d.prov === 'Computacional') com = d.mean;
      if (d.model === m && d.prov === 'Semântica') sem = d.mean;
    }}
    labels.push(m);
    comData.push(com);
    semData.push(sem);
  }}
  return {{ labels, comData, semData }};
}}
const tc = buildTotalChart();
new Chart(document.getElementById('chart-total'), {{
  type: 'bar',
  data: {{
    labels: tc.labels,
    datasets: [
      {{ label: 'Computacional', data: tc.comData, backgroundColor: '#3b82f6', borderRadius: 6 }},
      {{ label: 'Semântica', data: tc.semData, backgroundColor: '#10b981', borderRadius: 6 }},
    ],
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, beginAtZero: true, title: {{ display: true, text: 'Segundos', color: '#94a3b8' }} }},
    }},
  }},
}});

// ---- CPU / RAM line charts (all experiments) ----
const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b',
  '#ef4444', '#8b5cf6', '#ec4899',
];

function buildAllEpochChart(metric) {{
  const labelsSet = new Set();
  const expEntries = [];
  for (const key of Object.keys(DATA).sort()) {{
    const d = EPOCHS[key] || [];
    if (d.length === 0) continue;
    d.forEach(e => labelsSet.add(e.epoch));
    expEntries.push({{ key, data: d }});
  }}
  const labels = Array.from(labelsSet).sort((a, b) => a - b);
  const datasets = expEntries.map((entry, i) => ({{
    label: DATA[entry.key].label,
    data: labels.map(ep => {{
      const found = entry.data.find(e => e.epoch === ep);
      return found ? found[metric] : null;
    }}),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: 'transparent',
    tension: 0.3,
    pointRadius: 3,
    spanGaps: true,
  }}));
  return {{ labels, datasets }};
}}

let cpuChart = new Chart(document.getElementById('chart-cpu'), {{
  type: 'line',
  data: buildAllEpochChart('cpu'),
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Época', color: '#94a3b8' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'CPU (%)', color: '#94a3b8' }} }},
    }},
  }},
}});

let ramChart = new Chart(document.getElementById('chart-ram'), {{
  type: 'line',
  data: buildAllEpochChart('ram'),
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Época', color: '#94a3b8' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'RAM (MB)', color: '#94a3b8' }} }},
    }},
  }},
}});

// ---- Per-run bar chart ----
let runChart = null;
function updateRunChart() {{
  const expKey = document.getElementById('expSelect').value;
  const d = DATA[expKey];
  if (!d) return;
  const labels = d.run_numbers.map(r => `Run ${{r}}`);
  if (runChart) runChart.destroy();
  runChart = new Chart(document.getElementById('chart-run'), {{
    type: 'bar',
    data: {{
      labels,
      datasets: [{{ label: d.label, data: d.totals, backgroundColor: '#3b82f6', borderRadius: 4 }}],
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }}, beginAtZero: true, title: {{ display: true, text: 'Segundos', color: '#94a3b8' }} }},
      }},
    }},
  }});
}}

document.getElementById('expSelect').addEventListener('change', updateRunChart);
updateRunChart();
</script>
</body>
</html>"""

def gen_exp_options(data):
    opts = []
    for key in sorted(data.keys()):
        selected = ' selected' if key == list(sorted(data.keys()))[0] else ''
        opts.append(f'<option value="{key}"{selected}>{data[key]["label"]}</option>')
    return "\n".join(opts)

def main():
    data = load_all()
    if not data:
        print("Nenhum resultado encontrado em results/")
        return
    print(f"Encontrados {len(data)} experimentos:")
    for k, d in sorted(data.items()):
        print(f"  {k}: {d['n_runs']} runs, média {d['mean']:.2f}s")

    html = gen_html(data)
    out = Path("dashboard.html")
    out.write_text(html)
    print(f"\nDashboard gerado: {out.resolve()} (abra no navegador)")

if __name__ == "__main__":
    main()
