# InkPi

InkPi is a single-character calligraphy evaluation project that combines:

- `PyQt6` desktop UI
- local `WebUI` for debugging and result inspection
- `Cloud API` for shared history and remote OCR fallback
- `MiniApp` result browsing
- ONNX-based scoring and four-dimension explanation scores

Current main pipeline:

`capture/upload -> preprocessing -> OCR -> ONNX quality scoring -> four-dimension explanation -> local SQLite -> cloud sync`

## Main Entry Points

- Qt desktop UI: `python main.py`
- Local WebUI: `python -m web_ui.app`
- Cloud API: `python cloud_api/app.py`

Default ports:

- WebUI: `http://127.0.0.1:5000`
- Cloud API: `http://127.0.0.1:5001`

## Four-Dimension Scoring

The primary score remains `total_score`.  
The explanation layer adds four dimension scores:

- `structure` / 结构
- `stroke` / 笔画
- `integrity` / 完整
- `stability` / 稳定

Implementation notes:

- `services/quality_scorer_service.py` keeps the main ONNX scoring pipeline
- `services/dimension_scorer_service.py` builds four explanation scores
- `models/evaluation_result.py` stores `dimension_scores` and `score_debug`
- Qt shows user-facing scores only
- WebUI shows debug data for evaluation inspection
- Cloud API returns `dimension_scores` in list/detail payloads

## Runtime Layout

- `views/`: PyQt6 UI pages
- `services/`: camera, preprocessing, OCR, scoring, database, cloud sync
- `models/`: runtime models and ONNX assets
- `web_ui/`: local browser UI and Flask routes
- `cloud_api/`: shared cloud-facing Flask API
- `miniapp/`: mobile result viewer
- `training/`: scoring model training pipeline
- `docs/`: flow chart, project documentation, PPT assets

## Linux / XFCE Deployment

The project now targets Linux/XFCE for graphical Qt deployment.  
The old Windows desktop simulator scripts have been removed.

Server setup:

```bash
bash scripts/setup_server_runtime.sh
```

Start the full stack:

```bash
bash scripts/start_server_stack.sh
```

Stop the full stack:

```bash
bash scripts/stop_server_stack.sh
```

What the stack script starts:

- `Cloud API` on `INKPI_CLOUD_PORT` (default `5001`)
- `WebUI` on `INKPI_WEB_PORT` (default `5000`)
- `Qt UI` inside the current XFCE session

Useful environment overrides:

```bash
export INKPI_WEB_HOST=0.0.0.0
export INKPI_WEB_PORT=5000
export INKPI_CLOUD_PORT=5001
export INKPI_WINDOW_WIDTH=480
export INKPI_WINDOW_HEIGHT=320
export INKPI_FULLSCREEN=0
```

Optional runtime env files:

- `.inkpi/cloud.env`
- `.inkpi/server.env`

Example cloud sync configuration:

```env
INKPI_CLOUD_BACKEND_URL=http://127.0.0.1:5001
INKPI_CLOUD_DEVICE_KEY=your-device-key
INKPI_CLOUD_DEVICE_NAME=InkPi-XFCE
```

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Qt:

```bash
python main.py
```

Run WebUI:

```bash
python -m web_ui.app
```

Run Cloud API:

```bash
python cloud_api/app.py
```

## Tests

Common regression checks:

```bash
python -m unittest test_web_ui.py
python -m unittest test_all.py
python -m unittest test_cloud_api.py
python -m unittest test_cloud_ocr_api.py
python -m unittest test_cloud_sync_integration.py
```

## CI Notes

GitHub Actions should focus on cross-platform Python logic.  
Raspberry Pi specific hardware paths such as `GPIO`, camera hardware, `SPI`, and `libcamera` are better covered on the real device or a self-hosted runner.

## Docs

- Flow chart source: `docs/inkpi-project-flow.drawio`
- Flow chart preview: `docs/inkpi-project-flow.png`
- Training notes: `training/README.md`
