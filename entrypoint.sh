#!/bin/bash
set -e

echo "=== Starting DLProv stack ==="

# Start MonetDB (required for DL Prov data capture)
echo "Starting MonetDB..."
mkdir -p /opt/dlprov/DfAnalyzer/data
monetdbd create /opt/dlprov/DfAnalyzer/data 2>/dev/null || true
monetdbd start /opt/dlprov/DfAnalyzer/data
monetdb create dataflow_analyzer 2>/dev/null || true
monetdb release dataflow_analyzer 2>/dev/null || true
monetdb start dataflow_analyzer 2>/dev/null || true

# Optional: Neo4j (for post-hoc graph analysis, not needed during training)
# echo "Starting Neo4j..."
# neo4j start &

echo "Initializing MonetDB schema..."
cd /opt/dlprov/DfAnalyzer
./restore-database.sh || true

echo "Starting DfAnalyzer..."
JAR_PATH=""
if ls target/DfAnalyzer-2.0.jar >/dev/null 2>&1; then
	JAR_PATH="target/DfAnalyzer-2.0.jar"
elif ls target/DfAnalyzer-1.0.jar >/dev/null 2>&1; then
	JAR_PATH="target/DfAnalyzer-1.0.jar"
fi

if [ -n "$JAR_PATH" ]; then
	java -jar "$JAR_PATH" &
else
	echo "DfAnalyzer JAR not found in target/. Download it per README and place it in DfAnalyzer/target."
	exit 1
fi
echo "Waiting for DfAnalyzer to be ready..."
for i in {1..60}; do
	if curl -fsS http://localhost:22000/health >/dev/null 2>&1; then
		echo "DfAnalyzer is up."
		break
	fi
	sleep 1
done

if ! curl -fsS http://localhost:22000/health >/dev/null 2>&1; then
	echo "DfAnalyzer did not become ready in time."
	exit 1
fi
cd /opt/dlprov

echo "=== DLProv stack ready ==="
exec "$@"
