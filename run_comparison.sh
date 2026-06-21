#!/bin/bash
set -e

RUNS=${RUNS:-5}
SCRIPTS=(
    "Example/mnist-simple.py"
    "Example/mnist-torch.py"
    "Example/alexnet_dnnprov.py"
)

echo "=== Experimento Comparativo DLProv ==="
echo "Repetições por cenário: $RUNS"
echo ""

for script in "${SCRIPTS[@]}"; do
    name=$(basename "$script" .py)
    echo "========== Script: $script =========="

    for i in $(seq 1 $RUNS); do
        echo "--- $name | Com DLProv | Run $i/$RUNS ---"
        docker compose --profile com-prov run --rm \
            treinamento-com-prov \
            python monitor.py --script "$script" --scenario "$name-com-prov" --run "$i"
        echo ""
    done

    for i in $(seq 1 $RUNS); do
        echo "--- $name | Sem DLProv | Run $i/$RUNS ---"
        docker compose --profile sem-prov run --rm \
            treinamento-sem-prov \
            python monitor.py --script "$script" --scenario "$name-sem-prov" --run "$i"
        echo ""
    done
done

echo "=== Experimento concluído. Resultados em ./results/ ==="
