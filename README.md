# PGRScore — pipeline NFL (Python / Pandas / SQL / AWS)

Índice próprio **PGRScore** (40–99) sobre o dataset da NFL Big Data Bowl 2022 (temporada 2021, semanas 1–8). O cálculo vive no backend Python; o dashboard só lê o JSON já processado.

## Stack

- Python 3.11+, Pandas, NumPy
- SQLite local (simula a tabela de serviço; no AWS seria DynamoDB)
- Ingestão simulada em S3 (`scripts/aws_s3_upload.py`, handler estilo Lambda)
- Front-end estático (`web/`) — HTML/CSS/JS, sem regras de negócio

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Rodar o pipeline

A partir da raiz do repositório:

```bash
python -m pipeline.run
```

Isso lê `data/raw/` + `data/ref/teams_2021.json`, calcula o PGRScore e grava:

- `output/processed_data.json` — payload consolidado do dashboard
- `output/pgrscore.sqlite` — times, jogadores e série por jogo
- `web/processed_data.json` — cópia para o front-end

Simulação de ingestão S3 (sem credenciais usa o disco local como bucket):

```bash
python scripts/aws_s3_upload.py
```

Testes unitários da matemática do índice:

```bash
python tests/test_pgr_score.py
```

Consulta SQL de exemplo:

```bash
sqlite3 output/pgrscore.sqlite "SELECT name, pos_group, pgr_score, snaps FROM players ORDER BY pgr_score DESC LIMIT 10;"
```

## Dashboard

Sirva a pasta `web/` (o browser bloqueia `fetch` em arquivo local):

```bash
python -m http.server 43127 --directory web
```

Abra `http://127.0.0.1:43127` — Head-to-Head, elencos e gráficos. O JS consome **somente** `processed_data.json`.

## Layout

```
pipeline/                 núcleo Python
  ingest.py               CSV + tracking + joins
  pgr_score_calculator.py índice 40–99 e props
  assemble.py             documento JSON
  persist.py              JSON + SQLite
  run.py                  CLI
scripts/aws_s3_upload.py  S3 / Lambda
data/raw/                 dataset de amostra
data/ref/                 tabela 2021 e cores
web/                      apresentação (tiles usam web/logos/*.png)
ARCHITECTURE.md           fluxo S3 → Lambda/Glue → S3/DynamoDB → UI
```

Tracking posicional completo (~810 MB) não está versionado. `data/raw/tracking_metrics.json` carrega as métricas equivalentes usadas no protótipo original.
