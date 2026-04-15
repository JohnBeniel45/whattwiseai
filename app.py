from flask import Flask, render_template, request
import random

app = Flask(__name__)

UNIT_COST = 6
OVERALL_LIMIT = 24
APPLIANCE_LIMITS = {"AC": 9.0, "Fan": 1.6, "Iron": 2.2, "TV": 1.1}
SHOPPING_LINKS = {
    "AC": "https://www.amazon.in/s?k=5+star+inverter+ac",
    "Fan": "https://www.amazon.in/s?k=energy+efficient+ceiling+fan",
    "Iron": "https://www.amazon.in/s?k=energy+efficient+iron+box",
    "TV": "https://www.amazon.in/s?k=energy+efficient+smart+tv",
}
DEFAULT_APPLIANCES = {
    "AC": {"power": 1500, "hours": 6, "age": 4, "condition": "good", "maintenance": "yes"},
    "Fan": {"power": 75, "hours": 10, "age": 3, "condition": "good", "maintenance": "yes"},
    "Iron": {"power": 1200, "hours": 1, "age": 5, "condition": "slow", "maintenance": "no"},
    "TV": {"power": 100, "hours": 4, "age": 4, "condition": "standby", "maintenance": "yes"},
}
EXPECTED_HOURS = {"AC": 8, "Fan": 14, "Iron": 1.5, "TV": 6}


def format_hour(hour):
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def parse_float(value, fallback, minimum=0, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return round(parsed, 1)


def build_appliance_state(form_data):
    appliances = {}
    for name, defaults in DEFAULT_APPLIANCES.items():
        slug = name.lower()
        appliances[name] = {
            "power": parse_float(form_data.get(f"{slug}_power"), defaults["power"], minimum=1),
            "hours": parse_float(form_data.get(f"{slug}_hours"), defaults["hours"], minimum=0, maximum=24),
            "age": parse_float(form_data.get(f"{slug}_age"), defaults["age"], minimum=0, maximum=20),
            "condition": form_data.get(f"{slug}_condition", defaults["condition"]),
            "maintenance": form_data.get(f"{slug}_maintenance", defaults["maintenance"]),
        }
    return appliances


def generate_data(appliances, saving_mode=False):
    hours = list(range(24))
    base_usage = [
        0.28, 0.22, 0.2, 0.2, 0.26, 0.4,
        0.74, 1.05, 0.96, 0.71, 0.64, 0.67,
        0.78, 0.72, 0.66, 0.69, 0.82, 1.06,
        1.35, 1.5, 1.3, 1.0, 0.74, 0.46,
    ]
    appliance_load = sum((row["power"] * row["hours"]) / 1000 for row in appliances.values())
    profile_boost = appliance_load / 62
    saving_adjustment = -0.18 if saving_mode else 0
    usage = []
    for idx, value in enumerate(base_usage):
        peak_bonus = 0.12 if idx in (18, 19, 20) else 0.07 if idx in (7, 8) else 0
        variation = random.uniform(-0.06, 0.06)
        adjusted = max(0.14, value + profile_boost + saving_adjustment + peak_bonus + variation)
        usage.append(round(adjusted, 2))
    return hours, usage


def calculate_bill(total_usage):
    daily_cost = round(total_usage * UNIT_COST, 2)
    monthly_bill = round(daily_cost * 30, 2)
    return daily_cost, monthly_bill


def build_history(total_usage, saving_mode):
    baseline = total_usage * (0.92 if saving_mode else 1.0)
    multipliers = [1.08, 1.02, 0.96, 1.04, 0.93, 0.89, 1.0]
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    history = []
    for label, multiplier in zip(labels, multipliers):
        daily_total = round(max(10.5, baseline * multiplier + random.uniform(-0.4, 0.4)), 2)
        history.append({"label": label, "usage": daily_total})
    return history


def summarize_fault_reason(details, energy_kwh):
    reasons = []
    if details["age"] >= 6:
        reasons.append("older appliance efficiency drop")
    if details["condition"] in {"slow", "overheat"}:
        reasons.append("heating cycle taking too long")
    if details["condition"] == "noise":
        reasons.append("motor strain detected")
    if details["condition"] == "standby":
        reasons.append("standby drain likely active")
    if details["maintenance"] == "no":
        reasons.append("maintenance overdue")
    if energy_kwh > 3:
        reasons.append("consumption beyond normal operating range")
    return ", ".join(reasons[:2]) if reasons else "unusual load pattern detected"


def appliance_analysis(appliances, total_usage):
    rows = []
    alerts = []
    recommendations = []
    faulty_rows = []
    usage_reasons = []

    for name, details in appliances.items():
        energy_kwh = round((details["power"] * details["hours"]) / 1000, 2)
        cost = round(energy_kwh * UNIT_COST, 2)
        share = round((energy_kwh / total_usage) * 100, 1) if total_usage else 0
        expected_hours = EXPECTED_HOURS[name]
        limit = APPLIANCE_LIMITS[name]
        standby_load = 0.06 if name == "TV" and details["condition"] == "standby" else 0
        faulty = (
            energy_kwh + standby_load > limit
            or details["hours"] > expected_hours * 1.35
            or details["age"] >= 7
            or details["condition"] in {"slow", "overheat"}
            or details["maintenance"] == "no"
        )
        reason = summarize_fault_reason(details, energy_kwh)
        recommendation = None
        if faulty:
            recommendation = f"Replace {name.lower()} with a high-efficiency model from your shopping site"
            alerts.append(f"{name} exceeded safe usage limits and may need inspection")
            recommendations.append(
                {
                    "name": name,
                    "message": recommendation,
                    "reason": reason,
                    "link": SHOPPING_LINKS[name],
                }
            )
            faulty_rows.append(name)

        if energy_kwh > limit * 0.85:
            alerts.append(f"{name} is nearing its daily energy limit")

        if share >= 18:
            usage_reasons.append(f"{name} drove {share}% of today's consumption")

        phantom_load = "TV standby may be wasting power" if name == "TV" and details["condition"] == "standby" else ""

        rows.append(
            {
                "name": name,
                "power": details["power"],
                "hours": details["hours"],
                "age": details["age"],
                "condition": details["condition"],
                "maintenance": details["maintenance"],
                "energy_kwh": energy_kwh,
                "cost": cost,
                "share": share,
                "faulty": faulty,
                "reason": reason,
                "limit": limit,
                "shopping_link": SHOPPING_LINKS[name],
                "phantom_load": phantom_load,
                "recommendation": recommendation,
            }
        )
    return rows, alerts, recommendations, faulty_rows, usage_reasons


def get_peak_window(usage):
    peak_index = max(range(len(usage)), key=lambda idx: usage[idx])
    start = max(0, peak_index - 1)
    end = min(23, peak_index + 1)
    return f"{format_hour(start)} - {format_hour(end)}"


def get_pet_status(total_usage, faulty_count, score):
    if total_usage <= 19 and faulty_count == 0 and score >= 80:
        return "happy", "Great job! Efficient usage", 26, "Your pet feels energetic because the home stayed efficient today."
    if total_usage <= 26 and faulty_count <= 1:
        return "tired", "Usage rising, reduce load", 64, "Your pet is tired. A little saving today will help it recover."
    return "sick", "High usage detected!", 94, "Your pet is suffering because heavy usage or a faulty appliance is stressing the home."


def build_scores(total_usage, weekly_history):
    score = max(0, min(100, int(round(100 - (total_usage - 10) * 3.6))))
    eco_score = max(0, min(100, int(round(score - 5 + (weekly_history[-1]["usage"] - weekly_history[0]["usage"])) * -1)))
    return score, eco_score


def build_predictions(total_usage, weekly_history):
    yesterday_usage = weekly_history[-2]["usage"]
    weekly_average = round(sum(day["usage"] for day in weekly_history) / len(weekly_history), 2)
    tomorrow_usage = round((total_usage * 0.65) + (weekly_average * 0.35), 2)
    monthly_bill = round(total_usage * UNIT_COST * 30, 2)
    next_bill = round(((weekly_average + total_usage) / 2) * UNIT_COST * 30, 2)
    return {
        "yesterday_usage": yesterday_usage,
        "weekly_average": weekly_average,
        "tomorrow_usage": tomorrow_usage,
        "monthly_bill": monthly_bill,
        "next_bill": next_bill,
    }


def build_personalized_tips(rows, peak_window, saving_mode):
    tips = [f"Highest usage is during {peak_window}. Shift ironing or cooling to morning to save cost."]
    heavy = sorted(rows, key=lambda row: row["energy_kwh"], reverse=True)
    top = heavy[0]
    tips.append(f"You use {top['name']} heavily. Cut 1 hour to quickly lower tomorrow's bill.")
    phantom = next((row for row in rows if row["phantom_load"]), None)
    if phantom:
        tips.append(phantom["phantom_load"])
    if saving_mode:
        tips.append("Saving mode is on. Prioritize fans over AC and switch off standby loads for better scores.")
    return tips[:4]


def explain_usage_change(total_usage, predictions, rows):
    delta = round(total_usage - predictions["yesterday_usage"], 2)
    direction = "increased" if delta > 0 else "decreased"
    main_driver = max(rows, key=lambda row: row["energy_kwh"])
    reason = f"{main_driver['name']} contributed the most energy today at {main_driver['share']}%."
    return {
        "delta": abs(delta),
        "direction": direction,
        "reason": reason,
    }


def build_alerts(total_usage, peak_usage, average_usage, appliance_alerts, pet_status, saving_mode):
    alerts = []
    if total_usage > OVERALL_LIMIT:
        alerts.append(f"Overall usage limit exceeded: {total_usage} kWh today")
    if peak_usage > average_usage * 1.65:
        alerts.append("Sudden spike detected during the peak demand window")
    if pet_status == "sick":
        alerts.append("Your energy pet is suffering and needs attention")
    if saving_mode:
        alerts.append("Energy Saving Mode is active with cost-cutting recommendations enabled")
    alerts.extend(appliance_alerts)
    if not alerts:
        alerts.append("System stable: no major anomalies detected")
    return alerts


def build_pet_rewards(score, weekly_history):
    efficient_days = sum(1 for day in weekly_history if day["usage"] <= 20)
    streak = max(1, min(7, efficient_days))
    badge = "Spark Saver" if score >= 85 else "Steady Guardian" if score >= 70 else "Recovery Mode"
    return streak, badge


@app.route("/", methods=["GET", "POST"])
def index():
    saving_mode = request.form.get("saving_mode") == "on"
    appliances = build_appliance_state(request.form if request.method == "POST" else {})
    hours, usage = generate_data(appliances, saving_mode=saving_mode)
    total_usage = round(sum(usage), 2)
    peak_usage = max(usage)
    peak_hour_index = usage.index(peak_usage)
    average_usage = round(total_usage / 24, 2)
    peak_hour = format_hour(peak_hour_index)
    peak_window = get_peak_window(usage)
    hour_labels = [format_hour(hour) for hour in hours]

    weekly_history = build_history(total_usage, saving_mode)
    daily_cost, monthly_bill = calculate_bill(total_usage)
    appliance_rows, appliance_alerts, recommendations, faulty_rows, usage_reasons = appliance_analysis(appliances, total_usage)
    score, eco_score = build_scores(total_usage, weekly_history)
    pet_status, pet_message, pet_meter, pet_alert = get_pet_status(total_usage, len(faulty_rows), score)
    predictions = build_predictions(total_usage, weekly_history)
    usage_change = explain_usage_change(total_usage, predictions, appliance_rows)
    personalized_tips = build_personalized_tips(appliance_rows, peak_window, saving_mode)
    alerts = build_alerts(total_usage, peak_usage, average_usage, appliance_alerts, pet_status, saving_mode)
    streak, pet_badge = build_pet_rewards(score, weekly_history)

    suggestion = (
        "WattWise AI acts like a smart energy pet. Keep checking in so it can warn you early, coach better habits, and reduce your bill."
    )
    prediction_message = f"At current usage, your bill may reach Rs. {predictions['next_bill']:,.0f}"
    home_story = (
        "We built WattWise AI, a smart energy assistant that not only analyzes usage but also behaves like a virtual pet, "
        "encouraging users to adopt better energy habits through emotional engagement and actionable insights."
    )

    return render_template(
        "index.html",
        title="WattWise AI",
        hours=hour_labels,
        usage=usage,
        total_usage=total_usage,
        peak_usage=peak_usage,
        peak_hour=peak_hour,
        peak_window=peak_window,
        average_usage=average_usage,
        suggestion=suggestion,
        pet_status=pet_status,
        pet_message=pet_message,
        pet_meter=pet_meter,
        pet_alert=pet_alert,
        daily_cost=daily_cost,
        monthly_bill=monthly_bill,
        unit_cost=UNIT_COST,
        appliance_rows=appliance_rows,
        alerts=alerts,
        recommendations=recommendations,
        score=score,
        eco_score=eco_score,
        prediction_message=prediction_message,
        personalized_tips=personalized_tips,
        weekly_history=weekly_history,
        saving_mode=saving_mode,
        predictions=predictions,
        usage_change=usage_change,
        streak=streak,
        pet_badge=pet_badge,
        home_story=home_story,
        usage_reasons=usage_reasons,
    )


if __name__ == "__main__":
    app.run(debug=True)
