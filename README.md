## What Changed

Built WattWise AI as a hackathon-ready Flask energy dashboard while preserving the existing dark GitHub-style UI, animated energy pet, cards layout, and hourly bar chart.

Added:
- 24-hour energy monitoring with total usage, peak usage, and peak hour
- Enhanced energy pet with happy, tired, and sick states
- Daily cost and monthly bill prediction at Rs. 6 per unit
- Appliance intelligence for AC, Fan, Iron, and TV
- Editable appliance power and usage-hour simulation
- Appliance fault detection and smart replacement suggestions
- Energy score system
- Alerts for high usage, faults, and sudden spikes
- README with setup and feature overview

## Why

This upgrades the original dashboard into a more complete product experience suitable for hackathon judging, with stronger insights, clearer user value, and realistic smart-home decision support.

## Validation

- `python -m py_compile app.py`
- Flask test client returned `200` for `/`
