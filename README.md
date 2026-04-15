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
- Appliance health details can be adjusted to simulate faults and replacement advice.
- Every refresh regenerates the 24-hour usage profile.
- Fault detection is rule-based to keep the app fast and hackathon-friendly.
- The app can be installed on mobile as a PWA with offline caching support.
