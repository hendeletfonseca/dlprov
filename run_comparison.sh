#!/bin/bash
set -e -o pipefail

RUNS=${RUNS:-5}
SCRIPTS=(
    "Example/mnist-simple.py"
    "Example/mnist-torch.py"
    "Example/alexnet_dnnprov.py"
)

err() {
    local script="$1" scenario="$2" run="$3" exit_code="$4"
    echo "[ERRO] Script=$script | Cenário=$scenario | Run=$run | Exit=$exit_code" >&2
    if [[ -n "$OUTPUT_FILE" && -f "$OUTPUT_FILE" ]]; then
        echo "[ERRO] Últimas linhas da saída:" >&2
        tail -20 "$OUTPUT_FILE" >&2
    fi
}
trap 'err "$CUR_SCRIPT" "$CUR_SCENARIO" "$CUR_RUN" $?' ERR

echo "=== Experimento Comparativo DLProv ==="
echo "Repetições por cenário: $RUNS"
echo ""

OUTPUT_DIR=$(mktemp -d)
trap 'rm -rf "$OUTPUT_DIR"' EXIT

for script in "${SCRIPTS[@]}"; do
    CUR_SCRIPT=$script
    name=$(basename "$script" .py)
    echo "========== Script: $script =========="

    for i in $(seq 1 $RUNS); do
        CUR_RUN=$i
        CUR_SCENARIO="$name-com-prov"
        OUTPUT_FILE="$OUTPUT_DIR/${CUR_SCENARIO}_run${i}.log"
        echo "--- $name | Com DLProv | Run $i/$RUNS ---"
        docker compose --profile com-prov run --rm \
            treinamento-com-prov \
            python monitor.py --script "$script" --scenario "$CUR_SCENARIO" --run "$i" 2>&1 | tee "$OUTPUT_FILE"
        echo "[OK] Run $i concluída"
        echo ""
    done

    for i in $(seq 1 $RUNS); do
        CUR_RUN=$i
        CUR_SCENARIO="$name-sem-prov"
        OUTPUT_FILE="$OUTPUT_DIR/${CUR_SCENARIO}_run${i}.log"
        echo "--- $name | Sem DLProv | Run $i/$RUNS ---"
        docker compose --profile sem-prov run --rm \
            treinamento-sem-prov \
            python monitor.py --script "$script" --scenario "$CUR_SCENARIO" --run "$i" 2>&1 | tee "$OUTPUT_FILE"
        echo "[OK] Run $i concluída"
        echo ""
    done
done

echo "=== Experimento concluído. Resultados em ./results/ ==="
