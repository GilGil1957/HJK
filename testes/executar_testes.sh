#!/usr/bin/env bash
# Executa todos os testes automatizados. Requer: PostgreSQL 14+, Python 3 com
# psycopg e playwright (pip install "psycopg[binary]" playwright && playwright install chromium), Node.js.
# Uso: bash testes/executar_testes.sh "host=localhost port=5432 user=postgres password=..."
set -e
cd "$(dirname "$0")/.."
DSN="${1:-host=/tmp port=5433 user=postgres}"
node testes/testar_funcoes.js
python3 testes/testar_banco.py "$DSN"
python3 testes/testar_navegador.py "$DSN"
