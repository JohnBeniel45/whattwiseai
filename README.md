# WattWise AI

WattWise AI is a Flask-based smart energy dashboard designed for hackathon demos that need to feel like a real product. It keeps the original dark dashboard layout and animated energy pet while adding appliance intelligence, bill prediction, energy scoring, and actionable alerts.

## Features

- 24-hour energy monitoring with total usage, peak usage, and peak hour
- Animated energy pet with happy, tired, and sick states
- Daily cost and monthly bill prediction at `Rs. 6` per unit
- Editable appliance simulation for AC, Fan, Iron, and TV
- Appliance health detection with fault alerts and smart replacement suggestions
- Energy score from 0 to 100
- Alert engine for high usage, appliance faults, and sudden spikes
- Peak-highlighted hourly bar chart with preserved animation

## Project Structure

```text
app.py
templates/
  index.html
static/
  style.css
```

## Run Locally

1. Install Flask:

```bash
pip install flask
```

2. Start the app:

```bash
python app.py
```

3. Open `http://127.0.0.1:5000`

## Notes

- Appliance values can be edited directly from the dashboard.
- Every refresh regenerates the 24-hour usage profile.
- Fault detection is rule-based to keep the app fast and hackathon-friendly.
