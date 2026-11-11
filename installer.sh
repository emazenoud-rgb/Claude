#!/usr/bin/env bash
# Installe les dépendances et télécharge le modèle de voix (≈120 Mo).
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
mkdir -p modeles
base=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  [ -f "modeles/$f" ] || curl -L --fail -o "modeles/$f" "$base/$f"
done
echo "Prêt. Exemple : python3 voixoff.py textes/exemple.txt"
