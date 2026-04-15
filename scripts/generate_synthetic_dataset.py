from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT = Path("data/wattwise_synthetic_2026.csv")
YEAR = 2026
UNIT_COST = 6
OVERALL_LIMIT = 24
APPLIANCES = {
    "ac": {"power": 1500, "hours": 6, "age": 4, "limit": 9.0},
    "fan": {"power": 75, "hours": 11, "age": 3, "limit": 1.6},
    "iron": {"power": 1200, "hours": 1.0, "age": 5, "limit": 2.2},
    "tv": {"power": 100, "hours": 4.5, "age": 4, "limit": 1.1},
}
CONDITIONS = {
    "ac": ["good", "noise", "overheat"],
    "fan": ["good", "noise", "slow"],
    "iron": ["good", "slow", "overheat"],
    "tv": ["good", "standby", "slow"],
}


def format_hour(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def season_factor(day_of_year: int) -> float:
    return 1 + 0.18 * math.sin((2 * math.pi * (day_of_year - 40)) / 365)


def build_hourly_profile(day_of_year: int, saving_mode: int, rainfall: float) -> list[float]:
    baseline = [
        0.28, 0.24, 0.22, 0.21, 0.27, 0.41,
        0.76, 1.04, 0.95, 0.7, 0.65, 0.69,
        0.79, 0.73, 0.68, 0.71, 0.84, 1.08,
        1.33, 1.48, 1.31, 1.02, 0.77, 0.49,
    ]
    seasonal = season_factor(day_of_year)
    rain_adjust = -0.03 if rainfall > 3 else 0
    saving_adjust = -0.16 if saving_mode else 0
    values = []
    for idx, value in enumerate(baseline):
        peak_bonus = 0.12 if idx in (18, 19, 20) else 0.06 if idx in (7, 8) else 0
        noise = random.uniform(-0.06, 0.06)
        adjusted = max(0.14, (value * seasonal) + peak_bonus + rain_adjust + saving_adjust + noise)
        values.append(round(adjusted, 2))
    return values


def appliance_state(name: str, current_date: date, day_of_year: int) -> dict[str, object]:
    base = APPLIANCES[name]
    season = season_factor(day_of_year)
    weekend = current_date.weekday() >= 5
    power = base["power"] + random.randint(-80, 120)
    hours = base["hours"] + random.uniform(-1.2, 1.4)
    age = min(12, max(1, base["age"] + (day_of_year // 130)))

    if name == "ac":
        hours += 1.8 * max(0.7, season)
    if name == "fan":
        hours += 1.2 * max(0.5, season)
    if name == "iron" and weekend:
        hours += 0.5
    if name == "tv":
        hours += 1.0 if weekend else 0.2

    maintenance = "no" if random.random() < 0.22 else "yes"
    condition = "good"
    if maintenance == "no" and random.random() < 0.45:
        condition = random.choice(CONDITIONS[name][1:])
    elif name == "tv" and random.random() < 0.18:
        condition = "standby"

    hours = round(max(0.2, min(16, hours)), 1)
    energy = round((power * hours) / 1000, 2)
    faulty = int(
        energy > base["limit"]
        or maintenance == "no"
        or age >= 7
        or condition in {"slow", "overheat"}
    )
    cost = round(energy * UNIT_COST, 2)
    return {
        "power": power,
        "hours": hours,
        "age": age,
        "condition": condition,
        "maintenance": maintenance,
        "energy": energy,
        "cost": cost,
        "faulty": faulty,
        "limit": base["limit"],
    }


def pet_state(total_usage: float, faulty_count: int, score: int) -> tuple[str, int, str, str]:
    if total_usage <= 19 and faulty_count == 0 and score >= 82:
        return (
            "happy",
            26,
            "Great job! Efficient usage",
            "Your pet feels energetic because the home stayed efficient today.",
        )
    if total_usage <= 26 and faulty_count <= 1:
        return (
            "tired",
            64,
            "Usage rising, reduce load",
            "Your pet is tired. A little saving today will help it recover.",
        )
    return (
        "sick",
        94,
        "High usage detected!",
        "Your pet is suffering because heavy usage or a faulty appliance is stressing the home.",
    )


def main() -> None:
    random.seed(42)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    start = date(YEAR, 1, 1)
    end = date(YEAR, 12, 31)

    rows: list[dict[str, object]] = []
    efficient_streak = 0
    previous_total = 18.5
    history_window: list[float] = []

    current = start
    while current <= end:
        day_of_year = current.timetuple().tm_yday
        weekend = int(current.weekday() >= 5)
        rainfall_mm = round(max(0, random.gauss(2.4, 2.1)), 1)
        outdoor_temp_c = round(28 + (season_factor(day_of_year) - 1) * 18 + random.uniform(-4, 4), 1)
        saving_mode = int(random.random() < 0.32)
        occupancy_level = random.choice(["low", "medium", "high"])

        hourly = build_hourly_profile(day_of_year, saving_mode, rainfall_mm)
        appliances = {name: appliance_state(name, current, day_of_year) for name in APPLIANCES}
        appliance_total = sum(float(item["energy"]) for item in appliances.values())
        total_usage = round(sum(hourly) + appliance_total * 0.22, 2)
        peak_usage = max(hourly)
        peak_hour_idx = hourly.index(peak_usage)
        peak_window = f"{format_hour(max(0, peak_hour_idx - 1))}-{format_hour(min(23, peak_hour_idx + 1))}"
        average_hourly = round(total_usage / 24, 2)
        daily_cost = round(total_usage * UNIT_COST, 2)
        monthly_bill = round(daily_cost * 30, 2)
        future_bill_prediction = round(monthly_bill * random.uniform(0.96, 1.12), 2)
        tomorrow_usage_prediction = round((total_usage * 0.7) + (previous_total * 0.3), 2)
        weekly_average = round(((sum(history_window[-6:]) + total_usage) / max(1, len(history_window[-6:]) + 1)), 2)
        usage_change_kwh = round(total_usage - previous_total, 2)
        usage_change_direction = "increased" if usage_change_kwh > 0 else "decreased"
        energy_score = max(0, min(100, int(round(100 - (total_usage - 10) * 3.6))))
        eco_score = max(0, min(100, int(round(energy_score - 4 + (previous_total - total_usage)))))
        carbon_kg = round(total_usage * 0.82, 2)
        carbon_saved_kg = round(max(0, (previous_total - total_usage) * 0.82), 2)

        faulty_appliances = [name for name, state in appliances.items() if state["faulty"]]
        efficient_streak = efficient_streak + 1 if total_usage <= 20 and not faulty_appliances else 0
        pet_status, pet_meter, pet_message, pet_alert = pet_state(total_usage, len(faulty_appliances), energy_score)

        if faulty_appliances:
            usage_reason = f"{faulty_appliances[0].upper()} health issue increased consumption"
        else:
            main_driver = max(appliances.items(), key=lambda item: item[1]["energy"])[0]
            usage_reason = f"{main_driver.upper()} contributed the highest appliance load"

        alerts = []
        if total_usage > OVERALL_LIMIT:
            alerts.append("overall_limit_exceeded")
        if peak_usage > average_hourly * 1.65:
            alerts.append("sudden_spike")
        if pet_status == "sick":
            alerts.append("pet_suffering")
        for name in faulty_appliances:
            alerts.append(f"{name}_fault")
        if appliances["tv"]["condition"] == "standby":
            alerts.append("phantom_load_tv")

        recommendations = []
        for name in faulty_appliances:
            recommendations.append(f"replace_{name}_efficient_model")
        if saving_mode:
            recommendations.append("saving_mode_optimizations")
        if peak_hour_idx >= 18:
            recommendations.append("shift_usage_to_morning")

        row: dict[str, object] = {
            "date": current.isoformat(),
            "day_name": current.strftime("%A"),
            "month": current.strftime("%B"),
            "season_factor": round(season_factor(day_of_year), 3),
            "weekend": weekend,
            "occupancy_level": occupancy_level,
            "outdoor_temp_c": outdoor_temp_c,
            "rainfall_mm": rainfall_mm,
            "saving_mode": saving_mode,
            "total_usage_kwh": total_usage,
            "peak_usage_kwh": peak_usage,
            "peak_hour_label": format_hour(peak_hour_idx),
            "peak_window": peak_window,
            "average_hourly_kwh": average_hourly,
            "daily_cost_rs": daily_cost,
            "monthly_predicted_bill_rs": monthly_bill,
            "future_bill_prediction_rs": future_bill_prediction,
            "tomorrow_usage_prediction_kwh": tomorrow_usage_prediction,
            "previous_day_usage_kwh": round(previous_total, 2),
            "weekly_average_kwh": weekly_average,
            "usage_change_kwh": usage_change_kwh,
            "usage_change_direction": usage_change_direction,
            "usage_change_reason": usage_reason,
            "energy_score": energy_score,
            "eco_score": eco_score,
            "carbon_impact_kg": carbon_kg,
            "carbon_saved_kg": carbon_saved_kg,
            "pet_status": pet_status,
            "pet_meter_pct": pet_meter,
            "pet_message": pet_message,
            "pet_alert": pet_alert,
            "streak_days": efficient_streak,
            "reward_badge": "Spark Saver" if energy_score >= 85 else "Steady Guardian" if energy_score >= 70 else "Recovery Mode",
            "alert_count": len(alerts),
            "recommendation_count": len(recommendations),
            "alerts_pipe": "|".join(alerts),
            "recommendations_pipe": "|".join(recommendations),
            "personalized_tip_1": f"Highest usage is during {peak_window}. Shift ironing or cooling to morning to save cost.",
            "personalized_tip_2": "Saving mode is active. Prioritize fans over AC and switch off standby loads." if saving_mode else "You can improve efficiency by cutting AC usage by 1 hour.",
            "personalized_tip_3": "TV standby may be wasting power" if appliances["tv"]["condition"] == "standby" else "Your appliance mix is stable today.",
        }

        for hour, value in enumerate(hourly):
            row[f"hour_{hour:02d}_kwh"] = value

        appliance_energy_total = sum(state["energy"] for state in appliances.values()) or 1
        for name, state in appliances.items():
            row[f"{name}_power_w"] = state["power"]
            row[f"{name}_hours"] = state["hours"]
            row[f"{name}_age_years"] = state["age"]
            row[f"{name}_condition"] = state["condition"]
            row[f"{name}_maintenance"] = state["maintenance"]
            row[f"{name}_energy_kwh"] = state["energy"]
            row[f"{name}_cost_rs"] = state["cost"]
            row[f"{name}_share_pct"] = round((state["energy"] / appliance_energy_total) * 100, 1)
            row[f"{name}_faulty"] = state["faulty"]
            row[f"{name}_limit_kwh"] = state["limit"]

        rows.append(row)
        history_window.append(total_usage)
        previous_total = total_usage
        current += timedelta(days=1)

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
