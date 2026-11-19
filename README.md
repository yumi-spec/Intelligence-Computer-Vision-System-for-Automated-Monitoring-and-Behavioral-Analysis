# Milkfish Monitoring Dashboard

Intelligent computer-vision dashboard for milkfish ponds:
**CLAHE → YOLOv8 detection → DeepSORT tracking → behavior analysis → alerts (optional SMS)**,
shown in a Streamlit dashboard (dark-navy / mint theme).

## Quick start (PyCharm)

1. **Open the folder** `milkfish_monitor` in PyCharm (File → Open).
2. **Create an interpreter**: Settings → Project → Python Interpreter → Add → *Virtualenv*
   (Python 3.10 – 3.12 recommended).
3. **Install libraries** in the PyCharm Terminal:
   ```
   pip install -r requirements.txt
   ```
   (PyTorch comes with `ultralytics`. For an NVIDIA GPU, install the CUDA build of torch first from pytorch.org.)
4. **Add your files**
   - YOLOv8 weights → `models` (e.g. `../models`)
   - Sample videos → `videos` (`.mp4 .avi .mov .mkv`)
5. **Run**: right-click `run.py` → *Run 'run'*. The browser opens the dashboard.
   (Or in the terminal: `streamlit run src/dashboard.py`.)

The first `best.pt` and the first video found are selected automatically. Change them any time in **Settings**
(you can also upload files there).

## Folder layout

```
milkfish_monitor/
├── run.py                 ← press Run on this in PyCharm
├── requirements.txt
├── .env.example           ← copy to .env for SMS keys
├── models/                ← put best.pt here
├── videos/                ← put sample videos here
├── logs/                  ← metrics.csv and alerts.csv are written here
├── settings.json          ← created when you press "Save settings"
└── src/
    ├── dashboard.py       ← Streamlit UI (pages: Dashboard, Live Monitoring, Analytics, Reports, Settings)
    ├── components.py      ← HTML/SVG for each panel     ├── styles.py  ← theme CSS
    ├── pipeline.py        ← CLAHE → YOLO → tracker → behavior, draws boxes
    ├── preprocessing.py   ← CLAHE            ├── detector.py  ← YOLOv8
    ├── tracker.py         ← DeepSORT (IoU fallback if it can't load)
    ├── behavior.py        ← speed, heading, turns, cohesion, status
    ├── alerts.py          ← alert rules + SMS            └── config.py, storage.py
```

## How behavior is decided

Per fish (positions smoothed, time taken from the video clock so results don't depend on processing speed):

| Measure | How it is computed |
|---|---|
| Speed (px/s) | Net displacement over the last 1 s |
| Active / Inactive | Speed ≥ *Active above* threshold |
| Sharp turns / s | Heading changes ≥ *Sharp-turn angle* between 0.5 s samples |
| **Erratic** | Speed ≥ *Erratic speed* **or** turns/s ≥ *Erratic turns per second* |
| **Low Oxygen** | Fish stays in the top *surface zone* of the frame for ≥ *N seconds* (off by default) |
| Schooling cohesion | Closeness of nearest neighbours, plus heading alignment when fish are moving |

The whole school is flagged when at least *Share of fish* (default 30 %, minimum 3 fish) are Erratic or Low Oxygen,
and an alert fires only after the condition lasts *5 s* (then repeats at most every *5 min*).

### Calibrating behavior thresholds — important

The default numbers are **starting values, not validated science.** Speeds are in *pixels*, so they depend on your
camera height, angle, zoom and resolution. Before relying on the Erratic / Low Oxygen labels:

1. Record or pick footage of known-normal behavior and run it; note the typical *Average Speed* and turns/s.
2. Set *Erratic speed* / *turns per second* clearly above that normal range (e.g. mean + 2–3 standard deviations
   of your normal footage, or a value agreed with an aquaculture expert).
3. Check against footage of known abnormal behavior (feeding frenzy, aeration off, disturbance) if you have it.
4. The **Low Oxygen** rule is a *camera-based proxy* (surface gathering). It only makes sense with a side/angled
   camera where the surface is the top of the frame; with a top-down camera leave *Surface zone* at 0.
   It does not replace a dissolved-oxygen sensor.

Write down how you chose each threshold — that is the answer to "where do these parameters come from?".

## SMS alerts (optional)

1. Copy `.env.example` → `.env`; set `SMS_PROVIDER` (`twilio` or `semaphore`), the keys and `SMS_RECIPIENTS`.
2. In **Settings → Alerts & SMS** tick *Send SMS alerts*.

Without a provider configured, alerts are still shown on the dashboard and logged to `logs`; the SMS
status shows `failed`. Need another provider? Add a branch in `SmsSender.send()` in `../src`.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Setup needed" card | Put the model in `models` and a video in `../videos`, then press ▶ Start |
| "Could not load the model" | Check the weights are a YOLOv8 `.pt` and `ultralytics` is installed |
| Status says *IoU fallback* | `deep-sort-realtime` (or torch) didn't load; run `pip install deep-sort-realtime` |
| Slow / low FPS | Lower *Inference size* or *Processing width* in Settings; use a GPU build of torch |
| Page is blank on first load | Wait a few seconds — the model loads on first start |
| Webcam shows nothing | Try another *Camera index* (0, 1, 2…) |
