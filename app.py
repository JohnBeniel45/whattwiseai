from flask import Flask, render_template, request
import random

app = Flask(__name__)

UNIT_COST = 6
DEFAULT_APPLIANCES = {
    "AC": {"power": 1500, "hours": 6},
    "Fan": {"power": 75, "hours": 10},
    "Iron": {"power": 1200, "hours": 1},
    "TV": {"power": 100, "hours": 4},
}
EXPECTED_HOURS = {
    "AC": 8,
    "Fan": 14,
    "Iron": 1.5,
    "TV": 6,
}


def format_hour(hour):
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def build_appliance_state(form_data):
    appliances = {}
    for name, defaults in DEFAULT_APPLIANCES.items():
        power_key = f"{name.lower()}_power"
        hours_key = f"{name.lower()}_hours"
        power = form_data.get(power_key, defaults["power"])
        hours = form_data.get(hours_key, defaults["hours"])
        try:
            power = max(1, float(power))
        except (TypeError, ValueError):
            power = defaults["power"]
        try:
            hours = min(24, max(0, float(hours)))
        except (TypeError, ValueError):
            hours = defaults["hours"]
        appliances[name] = {"power": round(power, 1), "hours": round(hours, 1)}
    return appliances


def generate_data(appliances):
    hours = list(range(24))
    base_usage = [
        0.32, 0.25, 0.22, 0.21, 0.28, 0.44,
        0.82, 1.15, 1.01, 0.76, 0.68, 0.72,
        0.84, 0.78, 0.69, 0.73, 0.88, 1.12,
        1.42, 1.58, 1.36, 1.05, 0.78, 0.48,
    ]
    appliance_load = sum(
        (details["power"] * details["hours"]) / 1000 for details in appliances.values()
    )
    profile_boost = appliance_load / 60
    usage = []
    for idx, value in enumerate(base_usage):
        peak_bonus = 0.1 if idx in (7, 8, 18, 19, 20) else 0
        variation = random.uniform(-0.08, 0.08)
        adjusted = max(0.15, value + profile_boost + peak_bonus + variation)
        usage.append(round(adjusted, 2))
    return hours, usage


def calculate_bill(total_usage):
    daily_cost = round(total_usage * UNIT_COST, 2)
    monthly_bill = round(daily_cost * 30, 2)
    return daily_cost, monthly_bill


def appliance_analysis(appliances):
    analysis = []
    alerts = []
    recommendations = []

    for name, details in appliances.items():
        kwh = round((details["power"] * details["hours"]) / 1000, 2)
        cost = round(kwh * UNIT_COST, 2)
        expected_hours = EXPECTED_HOURS[name]
        faulty = details["hours"] > expected_hours * 1.35 or kwh > max(
            2.5, expected_hours * details["power"] / 1000 * 1.35
        )

        if faulty:
            alerts.append(f"{name} may be faulty due to high consumption")
            recommendations.append(f"Replace {name.lower()} with energy-efficient model")

        analysis.append(
            {
                "name": name,
                "power": details["power"],
                "hours": details["hours"],
                "energy_kwh": kwh,
                "cost": cost,
                "faulty": faulty,
            }
        )

    return analysis, alerts, recommendations


def get_pet_status(total_usage):
    if total_usage <= 20:
        return "happy", "Great job! Efficient usage", 28
    if total_usage <= 27:
        return "tired", "Usage rising, reduce load", 62
    return "sick", "High usage detected!", 94


def build_alerts(total_usage, peak_usage, average_usage, appliance_alerts):
    alerts = []
    if total_usage > 24:
        alerts.append("High total usage detected today")
    if peak_usage > average_usage * 1.65:
        alerts.append("Sudden spike detected during peak demand window")
    alerts.extend(appliance_alerts)
    if not alerts:
        alerts.append("System stable: no major anomalies detected")
    return alerts


def build_tip(total_usage, score, alerts):
    if any("faulty" in alert.lower() for alert in alerts):
        return "A device looks inefficient. Review appliance hours and replace older loads to avoid wasted energy."
    if total_usage > 24:
        return "Your home crossed the efficient range. Shift heavy appliance usage away from the evening peak."
    if score >= 80:
        return "Your home is running efficiently today. Maintain this pattern to keep your monthly bill under control."
    return "You are close to an efficient profile. Small cuts in AC or iron usage can boost your score quickly."


@app.route("/", methods=["GET", "POST"])
def index():
    appliances = build_appliance_state(request.form if request.method == "POST" else {})
    hours, usage = generate_data(appliances)
    total_usage = round(sum(usage), 2)
    peak_usage = max(usage)
    peak_hour_index = usage.index(peak_usage)
    average_usage = round(total_usage / 24, 2)
    peak_hour = format_hour(peak_hour_index)
    hour_labels = [format_hour(hour) for hour in hours]

    daily_cost, monthly_bill = calculate_bill(total_usage)
    appliance_rows, appliance_alerts, recommendations = appliance_analysis(appliances)
    pet_status, pet_message, pet_meter = get_pet_status(total_usage)
    score = max(0, min(100, int(round(100 - (total_usage - 10) * 4))))
    alerts = build_alerts(total_usage, peak_usage, average_usage, appliance_alerts)
    prediction_message = f"At current usage, your bill may reach Rs. {monthly_bill:,.0f}"
    tip = build_tip(total_usage, score, alerts)

    return render_template(
        "index.html",
        title="WattWise AI",
        hours=hour_labels,
        usage=usage,
        total_usage=total_usage,
        peak_usage=peak_usage,
        peak_hour=peak_hour,
        average_usage=average_usage,
        suggestion=tip,
        pet_status=pet_status,
        pet_message=pet_message,
        pet_meter=pet_meter,
        daily_cost=daily_cost,
        monthly_bill=monthly_bill,
        unit_cost=UNIT_COST,
        appliance_rows=appliance_rows,
        alerts=alerts,
        recommendations=recommendations,
        score=score,
        prediction_message=prediction_message,
    )


if __name__ == "__main__":
    app.run(debug=True)
