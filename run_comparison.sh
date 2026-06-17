#!/bin/bash
set -e

RUNS=${RUNS:-5}

echo "=== Experimento Comparativo DLProv ==="
echo "Repetições por cenário: $RUNS"
echo ""

for i in $(seq 1 $RUNS); do
    echo "--- Com DLProv | Run $i/$RUNS ---"
    docker compose --profile com-prov run --rm \
        treinamento-com-prov \
        python monitor.py --script Example/filter-prov.py --scenario com-prov --run "$i"
    echo ""
done

for i in $(seq 1 $RUNS); do
    echo "--- Sem DLProv (Baseline) | Run $i/$RUNS ---"
    docker compose --profile sem-prov run --rm \
        treinamento-sem-prov \
        python monitor.py --script Example/filter-prov.py --scenario sem-prov --run "$i"
    echo ""
done

echo "=== Experimento concluído. Resultados em ./results/ ==="
