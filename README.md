# WattWise AI

WattWise AI is a Flask-based smart energy dashboard designed for hackathon demos that need to feel like a real product. It keeps the original dark dashboard layout and animated energy pet while adding appliance intelligence, bill prediction, energy scoring, and actionable alerts.

## Features

- 24-hour energy monitoring with total usage, peak usage, and peak hour
- Animated energy pet with happy, tired, and sick states
- Daily cost and monthly bill prediction at `Rs. 6` per unit
- Editable appliance simulation for AC, Fan, Iron, and TV
- Appliance health detection with fault alerts and smart replacement suggestions
- Appliance health monitoring with age, condition, maintenance, and standby-loss inputs
- Energy score from 0 to 100
- Eco score, daily streaks, and pet-style engagement loops
- Alert engine for high usage, appliance faults, and sudden spikes
- Peak-highlighted hourly bar chart with preserved animation
- Weekly report, previous-vs-current usage comparison, and future bill prediction
- Progressive Web App support for installable mobile use and notifications
- One-year synthetic dataset powering analytics, appliance health, pet state, and recommendations
- Luminous-inspired mobile UI with glass cards, bottom navigation, and phone-first layout

## Project Structure

```text
app.py
data/
  wattwise_synthetic_2026.csv
scripts/
  generate_synthetic_dataset.py
templates/
  index.html
static/
  reference-ui.webp
  style.css
requirements.txt
render.yaml
```

## Run Locally

1. Install Flask:

```bash
pip install -r requirements.txt
```

2. Start the app:

```bash
python app.py
```

3. Open `http://127.0.0.1:5000`

## Deploy on Render

1. Push the repo to GitHub.
2. Go to [Render](https://render.com/) and create a new Web Service.
3. Connect this repository and select the `codex/wattwise-ai-dashboard` branch.
4. Render can auto-detect `render.yaml`, or use:

```bash
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
```

5. After deploy, open the Render URL on mobile and install it as a PWA.

## Notes

- Appliance values can be edited directly from the dashboard.
- Appliance health details can be adjusted to simulate faults and replacement advice.
- The app uses the synthetic dataset directly, and the selected date changes the loaded daily profile.
- Fault detection is rule-based to keep the app fast and hackathon-friendly.
- The app can be installed on mobile as a PWA with offline caching support.
