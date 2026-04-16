from flask import Flask, jsonify, render_template, request, send_from_directory
from pathlib import Path
import base64
import csv
import hashlib
import hmac
import json
import math
import os
from urllib import error, parse as urllib_parse, request as urllib_request

app = Flask(__name__)

UNIT_COST = 6
DATASET_PATH = Path("data/wattwise_synthetic_2026.csv")
OVERALL_LIMIT = 24
APPLIANCE_LIMITS = {"AC": 9.0, "Fan": 1.6, "Iron": 2.2, "TV": 1.1}
TOU_RATES = {
    "off_peak": {"label": "Off-peak", "rate": 4.25, "hours": list(range(0, 6)) + list(range(22, 24))},
    "standard": {"label": "Standard", "rate": 6.0, "hours": list(range(6, 18))},
    "peak": {"label": "Peak", "rate": 8.5, "hours": list(range(18, 22))},
}
CARBON_FACTOR_KG_PER_KWH = 0.82
TREE_ABSORPTION_KG_PER_MONTH = 21.0
DEFAULT_APPLIANCES = {
    "AC": {"power": 1500, "hours": 6, "age": 4, "condition": "good", "maintenance": "yes"},
    "Fan": {"power": 75, "hours": 10, "age": 3, "condition": "good", "maintenance": "yes"},
    "Iron": {"power": 1200, "hours": 1, "age": 5, "condition": "slow", "maintenance": "no"},
    "TV": {"power": 100, "hours": 4, "age": 4, "condition": "standby", "maintenance": "yes"},
}
EXPECTED_HOURS = {"AC": 8, "Fan": 14, "Iron": 1.5, "TV": 6}
CONDITION_ENCODING = {"good": 0, "standby": 1, "noise": 2, "slow": 3, "overheat": 4}
MAINTENANCE_ENCODING = {"yes": 0, "no": 1}
PRODUCT_CATALOG = [
    {
        "id": "iron-philips-gc1905",
        "category": "Iron",
        "name": "Philips EasySpeed GC1905 1440W Steam Iron",
        "rating": 4.5,
        "review_count": 1000,
        "price": 1799,
        "store": "Croma",
        "review_summary": "Customers consistently praise quick heating, easy glide, and durable steam output.",
        "why_it_fits": "Good upgrade when AI detects overheating or long heating cycles in your current iron.",
        "url": "https://www.croma.com/philips-gc1905-01-steam-iron/p/170449",
        "image_url": "https://media-ik.croma.com/prod/https%3A//media.tatacroma.com/Croma%20Assets/Small%20Appliances/Garment%20Care/Images/170449_0_UQmEb4Kw7.png?updatedAt=1760541417022%3Ftr%3Dw-112",
    },
    {
        "id": "ac-voltas-185v-vectra",
        "category": "AC",
        "name": "Voltas PureAir 185V Verdant Exotica 1.5 Ton 5 Star AC",
        "rating": 4.4,
        "review_count": 820,
        "price": 43290,
        "store": "Voltas",
        "review_summary": "Strong buyer feedback highlights efficient cooling, air purification, copper build, and lower running cost.",
        "why_it_fits": "A 5-star inverter upgrade when AI sees heavy AC-driven bills and cooling inefficiency.",
        "url": "https://www.voltas.com/collections/1-5-ton-5-star-ac/products/voltas-pureair-inverter-split-ac-1-5-ton-5-star-185v-verdant-exotica",
        "image_url": "https://www.voltas.com/cdn/shop/files/4503500.png?v=1759483963&width=1080",
    },
]


def load_dataset():
    if not DATASET_PATH.exists():
        return [], {}
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return rows, {row["date"]: row for row in rows}


DATASET_ROWS, DATASET_ROWS_BY_DATE = load_dataset()


def parse_float(value, fallback, minimum=0, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return round(parsed, 1)


def parse_int(value, fallback=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def format_hour(hour):
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def get_dataset_summary():
    if not DATASET_ROWS:
        return {"available": False}
    return {
        "available": True,
        "rows": len(DATASET_ROWS),
        "features": len(DATASET_ROWS[0].keys()),
        "start": DATASET_ROWS[0]["date"],
        "end": DATASET_ROWS[-1]["date"],
        "path": str(DATASET_PATH),
    }


def get_selected_row(selected_date=None):
    if not DATASET_ROWS:
        return None, []
    dates = [row["date"] for row in DATASET_ROWS]
    if selected_date and selected_date in DATASET_ROWS_BY_DATE:
        return DATASET_ROWS_BY_DATE[selected_date], dates
    return DATASET_ROWS[-1], dates


def build_dataset_defaults(dataset_row):
    defaults = {}
    for name, base in DEFAULT_APPLIANCES.items():
        slug = name.lower()
        if dataset_row:
            defaults[name] = {
                "power": parse_float(dataset_row.get(f"{slug}_power_w"), base["power"], minimum=1),
                "hours": parse_float(dataset_row.get(f"{slug}_hours"), base["hours"], minimum=0, maximum=24),
                "age": parse_float(dataset_row.get(f"{slug}_age_years"), base["age"], minimum=0, maximum=20),
                "condition": dataset_row.get(f"{slug}_condition", base["condition"]),
                "maintenance": dataset_row.get(f"{slug}_maintenance", base["maintenance"]),
            }
        else:
            defaults[name] = dict(base)
    return defaults


def build_appliance_state(form_data, defaults_map):
    appliances = {}
    for name, defaults in defaults_map.items():
        slug = name.lower()
        appliances[name] = {
            "power": parse_float(form_data.get(f"{slug}_power"), defaults["power"], minimum=1),
            "hours": parse_float(form_data.get(f"{slug}_hours"), defaults["hours"], minimum=0, maximum=24),
            "age": parse_float(form_data.get(f"{slug}_age"), defaults["age"], minimum=0, maximum=20),
            "condition": form_data.get(f"{slug}_condition", defaults["condition"]),
            "maintenance": form_data.get(f"{slug}_maintenance", defaults["maintenance"]),
        }
    return appliances


def get_hourly_usage(dataset_row, appliances, saving_mode=False):
    hours = list(range(24))
    if not dataset_row:
        usage = [0.4] * 24
        return hours, usage

    base_usage = [float(dataset_row[f"hour_{hour:02d}_kwh"]) for hour in hours]
    base_appliance_total = sum(float(dataset_row[f"{name.lower()}_energy_kwh"]) for name in DEFAULT_APPLIANCES)
    current_appliance_total = sum((item["power"] * item["hours"]) / 1000 for item in appliances.values())
    delta = current_appliance_total - base_appliance_total
    adjustment = delta / 24
    saving_adjustment = -0.12 if saving_mode else 0
    usage = [round(max(0.14, value + adjustment + saving_adjustment), 2) for value in base_usage]
    return hours, usage


def calculate_bill(total_usage):
    daily_cost = round(total_usage * UNIT_COST, 2)
    monthly_bill = round(daily_cost * 30, 2)
    return daily_cost, monthly_bill


def build_history(selected_date):
    if not DATASET_ROWS:
        return []
    selected_index = next((idx for idx, row in enumerate(DATASET_ROWS) if row["date"] == selected_date), len(DATASET_ROWS) - 1)
    start_index = max(0, selected_index - 6)
    rows = DATASET_ROWS[start_index:selected_index + 1]
    return [{"label": row["day_name"][:3], "usage": round(float(row["total_usage_kwh"]), 2)} for row in rows]


def normalize(value, minimum, maximum):
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def ai_bill_forecast(total_usage, weekly_history, appliance_rows):
    if not weekly_history:
        return {
            "yesterday_usage": total_usage,
            "weekly_average": total_usage,
            "tomorrow_usage": total_usage,
            "monthly_bill": round(total_usage * UNIT_COST * 30, 2),
            "next_bill": round(total_usage * UNIT_COST * 30, 2),
            "confidence": 0.5,
        }

    weighted_week = sum(day["usage"] * weight for day, weight in zip(weekly_history, range(1, len(weekly_history) + 1)))
    weight_total = sum(range(1, len(weekly_history) + 1))
    weighted_average = weighted_week / weight_total
    appliance_pressure = sum(row["energy_kwh"] * (1.2 if row["faulty"] else 1.0) for row in appliance_rows)
    tomorrow_usage = round((weighted_average * 0.58) + (total_usage * 0.27) + (appliance_pressure * 0.15), 2)
    weekly_average = round(sum(day["usage"] for day in weekly_history) / len(weekly_history), 2)
    next_bill = round(((tomorrow_usage * 0.55) + (weekly_average * 0.45)) * UNIT_COST * 30, 2)
    confidence = max(0.58, min(0.94, 1 - abs(tomorrow_usage - weekly_average) / max(weekly_average, 1)))
    return {
        "yesterday_usage": weekly_history[-2]["usage"] if len(weekly_history) >= 2 else total_usage,
        "weekly_average": weekly_average,
        "tomorrow_usage": tomorrow_usage,
        "monthly_bill": round(total_usage * UNIT_COST * 30, 2),
        "next_bill": next_bill,
        "confidence": round(confidence, 2),
    }


def gemini_config():
    return {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }


def extract_gemini_text(payload):
    candidates = payload.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    text_segments = [part.get("text", "") for part in parts if part.get("text")]
    return "".join(text_segments).strip()


def gemini_generate_json(task_prompt, fallback):
    config = gemini_config()
    if not config["api_key"]:
        return fallback

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config['model']}:generateContent?key={urllib_parse.quote(config['api_key'])}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "You are WattWise AI. Return only valid JSON without markdown fences. "
                            "Keep recommendations practical, concise, and grounded in the provided energy data.\n\n"
                            f"{task_prompt}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json",
        },
    }
    http_request = urllib_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(http_request, timeout=18) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return fallback

    text = extract_gemini_text(body)
    if not text:
        return fallback
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return fallback
    return parsed if isinstance(parsed, dict) else fallback


def build_ai_training_rows():
    rows = []
    for row in DATASET_ROWS:
        rows.append(
            {
                "vector": [
                    float(row["total_usage_kwh"]),
                    float(row["monthly_predicted_bill_rs"]),
                    float(row["usage_change_kwh"]),
                    float(row["weekly_average_kwh"]),
                ],
                "label": row["pet_status"],
            }
        )
    return rows


AI_TRAINING_ROWS = build_ai_training_rows()


def nearest_pet_status(monthly_bill, total_usage, weekly_average, usage_delta):
    if not AI_TRAINING_ROWS:
        return "tired"
    target = [total_usage, monthly_bill, usage_delta, weekly_average]
    ranked = sorted(
        AI_TRAINING_ROWS,
        key=lambda item: math.sqrt(sum((item["vector"][idx] - target[idx]) ** 2 for idx in range(4))),
    )[:9]
    votes = {"happy": 0.0, "tired": 0.0, "sick": 0.0}
    for index, item in enumerate(ranked, start=1):
        votes[item["label"]] += 1 / index
    return max(votes, key=votes.get)


def ai_pet_response(monthly_bill, total_usage, predictions):
    predicted_state = nearest_pet_status(
        monthly_bill,
        total_usage,
        predictions["weekly_average"],
        total_usage - predictions["yesterday_usage"],
    )
    if predicted_state == "happy":
        return "happy", "Bill looks healthy and efficient", 24, "Your pet is relaxed because your projected bill stays comfortably low."
    if predicted_state == "tired":
        return "tired", "Bill is rising, trim usage now", 60, "Your pet is uneasy because the bill trend is climbing above your weekly baseline."
    return "sick", "Bill pressure is too high", 92, "Your pet is stressed because the forecasted bill is too expensive for this usage pattern."


def appliance_feature_vector(details, energy_kwh, share):
    return [
        normalize(details["power"], 50, 2000),
        normalize(details["hours"], 0, 24),
        normalize(details["age"], 0, 15),
        normalize(energy_kwh, 0, 12),
        normalize(share, 0, 100),
        CONDITION_ENCODING.get(details["condition"], 0) / max(len(CONDITION_ENCODING) - 1, 1),
        MAINTENANCE_ENCODING.get(details["maintenance"], 0),
    ]


def dataset_vectors_for_appliance(category):
    slug = category.lower()
    vectors = []
    for row in DATASET_ROWS:
        vector = [
            normalize(float(row[f"{slug}_power_w"]), 50, 2000),
            normalize(float(row[f"{slug}_hours"]), 0, 24),
            normalize(float(row[f"{slug}_age_years"]), 0, 15),
            normalize(float(row[f"{slug}_energy_kwh"]), 0, 12),
            normalize(float(row[f"{slug}_share_pct"]), 0, 100),
            CONDITION_ENCODING.get(row[f"{slug}_condition"], 0) / max(len(CONDITION_ENCODING) - 1, 1),
            MAINTENANCE_ENCODING.get(row[f"{slug}_maintenance"], 0),
        ]
        vectors.append((vector, int(row[f"{slug}_faulty"])))
    return vectors


APPLIANCE_AI_ROWS = {name: dataset_vectors_for_appliance(name) for name in DEFAULT_APPLIANCES}


def ai_fault_score(category, details, energy_kwh, share):
    vectors = APPLIANCE_AI_ROWS.get(category, [])
    if not vectors:
        return 0.0
    target = appliance_feature_vector(details, energy_kwh, share)
    ranked = sorted(
        vectors,
        key=lambda item: math.sqrt(sum((item[0][idx] - target[idx]) ** 2 for idx in range(len(target)))),
    )[:12]
    weighted_fault = 0.0
    weighted_total = 0.0
    for index, (_, label) in enumerate(ranked, start=1):
        weight = 1 / index
        weighted_fault += label * weight
        weighted_total += weight
    return round(weighted_fault / weighted_total, 2)


def summarize_fault_reason(details, ai_score, energy_kwh):
    if ai_score >= 0.72:
        return "AI sees a strong fault pattern driven by high energy draw and appliance condition."
    if details["condition"] in {"slow", "overheat"}:
        return "AI flags the operating condition as a likely cause of wasted energy."
    if details["maintenance"] == "no":
        return "AI sees maintenance delay correlating with elevated bill pressure."
    if details["age"] >= 7:
        return "AI sees age-related efficiency loss in similar historical patterns."
    if energy_kwh > 3:
        return "AI detects unusually high consumption for this appliance profile."
    return "AI sees this appliance operating within a healthy range."


def score_product_fit(appliance_name, product, ai_score, monthly_bill):
    category_bonus = 0.45 if product["category"] == appliance_name else 0.0
    rating_bonus = product["rating"] / 5 * 0.3
    reviews_bonus = min(product["review_count"], 20000) / 20000 * 0.15
    urgency_bonus = min(monthly_bill / 10000, 1) * 0.1 + ai_score * 0.2
    return round(min(0.99, category_bonus + rating_bonus + reviews_bonus + urgency_bonus), 3)


def recommend_products(appliance_rows, monthly_bill):
    candidates = []
    for row in appliance_rows:
        if not row["faulty"]:
            continue
        for product in PRODUCT_CATALOG:
            score = score_product_fit(row["name"], product, row["ai_fault_score"], monthly_bill)
            if product["category"] == row["name"]:
                candidates.append(
                    {
                        **product,
                        "score": score,
                        "target_appliance": row["name"],
                        "insight": f"AI matched this product to your {row['name']} issue based on fault risk and savings potential.",
                    }
                )
    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    unique = []
    seen_ids = set()
    for item in ranked:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        unique.append(item)
        if len(unique) == 2:
            break
    return unique


def ai_forecast_and_product_brain(total_usage, monthly_bill, predictions, weekly_history, appliance_rows, recommendations):
    fallback = {
        "next_bill": predictions["next_bill"],
        "confidence": predictions["confidence"],
        "prediction_message": f"AI forecasts your bill may reach Rs. {predictions['next_bill']:,.0f}",
        "usage_story": f"AI sees tomorrow usage near {predictions['tomorrow_usage']} kWh based on your weekly trend and appliance pressure.",
        "pet_message": None,
        "appliances": [],
        "recommendations": [],
    }
    appliance_snapshot = [
        {
            "name": row["name"],
            "energy_kwh": row["energy_kwh"],
            "cost": row["cost"],
            "share": row["share"],
            "ai_fault_score": row["ai_fault_score"],
            "condition": row["condition"],
            "age": row["age"],
            "maintenance": row["maintenance"],
        }
        for row in appliance_rows
    ]
    catalog_snapshot = [
        {
            "id": item["id"],
            "category": item["category"],
            "name": item["name"],
            "rating": item["rating"],
            "review_count": item["review_count"],
            "price": item["price"],
        }
        for item in PRODUCT_CATALOG
    ]
    task_prompt = (
        "Return JSON with keys next_bill, confidence, prediction_message, usage_story, pet_message, appliances, recommendations. "
        "The appliances array must contain objects with keys name, usage_band, health_state, likely_issue, advice. "
        "The recommendations array must contain objects with keys id, reason, image_caption. "
        "Use health_state values from healthy, watch, faulty. Use usage_band values from low, normal, high. "
        "Keep prediction_message and usage_story under 22 words each. Keep advice under 18 words.\n\n"
        f"Total usage kWh: {total_usage}\n"
        f"Current monthly bill estimate Rs: {monthly_bill}\n"
        f"Local next bill forecast Rs: {predictions['next_bill']}\n"
        f"Local tomorrow usage forecast kWh: {predictions['tomorrow_usage']}\n"
        f"Local confidence: {predictions['confidence']}\n"
        f"Weekly history: {json.dumps(weekly_history)}\n"
        f"Appliances: {json.dumps(appliance_snapshot)}\n"
        f"Candidate products: {json.dumps(catalog_snapshot)}\n"
        f"Pre-ranked replacements: {json.dumps([item['id'] for item in recommendations])}"
    )
    result = gemini_generate_json(task_prompt, fallback)
    return {
        "next_bill": round(parse_float(result.get("next_bill"), predictions["next_bill"], minimum=1), 2),
        "confidence": round(parse_float(result.get("confidence"), predictions["confidence"], minimum=0, maximum=1), 2),
        "prediction_message": result.get("prediction_message") or fallback["prediction_message"],
        "usage_story": result.get("usage_story") or fallback["usage_story"],
        "pet_message": result.get("pet_message"),
        "appliances": result.get("appliances") if isinstance(result.get("appliances"), list) else [],
        "recommendations": result.get("recommendations") if isinstance(result.get("recommendations"), list) else [],
    }


def merge_ai_appliance_labels(appliance_rows, ai_output):
    ai_by_name = {
        item.get("name"): item
        for item in ai_output
        if isinstance(item, dict) and item.get("name")
    }
    for row in appliance_rows:
        model_row = ai_by_name.get(row["name"], {})
        row["usage_band"] = model_row.get("usage_band", "high" if row["share"] >= 18 else "normal" if row["share"] >= 8 else "low")
        row["health_state"] = model_row.get("health_state", "faulty" if row["faulty"] else "watch" if row["ai_fault_score"] >= 0.42 else "healthy")
        row["likely_issue"] = model_row.get("likely_issue", row["reason"])
        row["advice"] = model_row.get("advice", "Inspect and reduce usage." if row["faulty"] else "Continue monitoring.")
    return appliance_rows


def merge_ai_recommendations(recommendations, ai_output):
    ai_by_id = {
        item.get("id"): item
        for item in ai_output
        if isinstance(item, dict) and item.get("id")
    }
    merged = []
    for item in recommendations:
        model_item = ai_by_id.get(item["id"], {})
        merged.append(
            {
                **item,
                "reason": model_item.get("reason", item["insight"]),
                "image_caption": model_item.get("image_caption", f"{item['category']} replacement recommended by WattWise AI."),
            }
        )
    return merged


def appliance_analysis(appliances, total_usage, monthly_bill):
    rows = []
    alerts = []
    faulty_rows = []
    usage_reasons = []

    for name, details in appliances.items():
        energy_kwh = round((details["power"] * details["hours"]) / 1000, 2)
        cost = round(energy_kwh * UNIT_COST, 2)
        share = round((energy_kwh / total_usage) * 100, 1) if total_usage else 0
        ai_score = ai_fault_score(name, details, energy_kwh, share)
        faulty = ai_score >= 0.56
        reason = summarize_fault_reason(details, ai_score, energy_kwh)

        if faulty:
            alerts.append(f"{name} AI risk score is {int(ai_score * 100)} percent and needs inspection")
            faulty_rows.append(name)
        elif ai_score >= 0.42:
            alerts.append(f"{name} shows an early AI anomaly pattern")

        if share >= 18:
            usage_reasons.append(f"{name} drove {share}% of today's consumption")

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
                "limit": APPLIANCE_LIMITS[name],
                "shopping_link": next((item["url"] for item in PRODUCT_CATALOG if item["category"] == name), "#"),
                "phantom_load": "TV standby may be wasting power" if name == "TV" and details["condition"] == "standby" else "",
                "ai_fault_score": ai_score,
                "bill_impact": round((cost / max(monthly_bill, 1)) * 100, 1),
            }
        )
    recommendations = recommend_products(rows, monthly_bill)
    return rows, alerts, recommendations, faulty_rows, usage_reasons


def get_peak_window(usage):
    peak_index = max(range(len(usage)), key=lambda idx: usage[idx])
    start = max(0, peak_index - 1)
    end = min(23, peak_index + 1)
    return f"{format_hour(start)} - {format_hour(end)}"


def build_scores(total_usage, weekly_history):
    score = max(0, min(100, int(round(100 - (total_usage - 10) * 3.6))))
    eco_score = max(0, min(100, int(round(score - 5 + (weekly_history[-1]["usage"] - weekly_history[0]["usage"])) * -1))) if weekly_history else score
    return score, eco_score


def get_tou_band(hour):
    for key, band in TOU_RATES.items():
        if hour in band["hours"]:
            return key, band
    return "standard", TOU_RATES["standard"]


def build_tou_optimizer(usage, appliance_rows):
    tou_cost = 0.0
    flat_cost = 0.0
    peak_cost = 0.0
    off_peak_rate = TOU_RATES["off_peak"]["rate"]
    peak_hours = []

    for hour, value in enumerate(usage):
        band_key, band = get_tou_band(hour)
        cost = value * band["rate"]
        tou_cost += cost
        flat_cost += value * UNIT_COST
        if band_key == "peak":
            peak_cost += cost
            peak_hours.append(value)

    heavy = max(appliance_rows, key=lambda row: row["energy_kwh"])
    shiftable_units = min(heavy["energy_kwh"] * 0.45, sum(peak_hours) * 0.45 if peak_hours else heavy["energy_kwh"] * 0.25)
    current_peak_rate = TOU_RATES["peak"]["rate"]
    saving = max(0, shiftable_units * (current_peak_rate - off_peak_rate))
    best_window = "10 PM - 6 AM"
    recommendation = (
        f"Run {heavy['name']} closer to {best_window}. "
        f"Moving {shiftable_units:.1f} kWh from peak hours can save about Rs. {saving:.0f}/day."
    )

    return {
        "tou_cost": round(tou_cost, 2),
        "flat_cost": round(flat_cost, 2),
        "peak_cost": round(peak_cost, 2),
        "saving_daily": round(saving, 2),
        "saving_monthly": round(saving * 30, 2),
        "best_window": best_window,
        "heavy_appliance": heavy["name"],
        "recommendation": recommendation,
        "bands": [
            {"label": "Off-peak", "hours": "10 PM - 6 AM", "rate": TOU_RATES["off_peak"]["rate"]},
            {"label": "Standard", "hours": "6 AM - 6 PM", "rate": TOU_RATES["standard"]["rate"]},
            {"label": "Peak", "hours": "6 PM - 10 PM", "rate": TOU_RATES["peak"]["rate"]},
        ],
    }


def build_carbon_dashboard(total_usage, predictions, weekly_history):
    today_kg = round(total_usage * CARBON_FACTOR_KG_PER_KWH, 2)
    monthly_kg = round(today_kg * 30, 2)
    predicted_kg = round(predictions["tomorrow_usage"] * CARBON_FACTOR_KG_PER_KWH * 30, 2)
    baseline = predictions["weekly_average"] if predictions.get("weekly_average") else total_usage
    saved_today = max(0, baseline - total_usage)
    saved_kg = round(saved_today * CARBON_FACTOR_KG_PER_KWH, 2)
    trees_equivalent = round(monthly_kg / TREE_ABSORPTION_KG_PER_MONTH, 1)
    carbon_score = max(0, min(100, int(round(100 - (today_kg - 12) * 4))))
    weekly_kg = [
        {"label": day["label"], "kg": round(day["usage"] * CARBON_FACTOR_KG_PER_KWH, 2)}
        for day in weekly_history
    ]
    return {
        "today_kg": today_kg,
        "monthly_kg": monthly_kg,
        "predicted_kg": predicted_kg,
        "saved_kg": saved_kg,
        "trees_equivalent": trees_equivalent,
        "score": carbon_score,
        "weekly_kg": weekly_kg,
        "message": f"Today produced about {today_kg} kg CO2. Cutting 2 kWh saves roughly {round(2 * CARBON_FACTOR_KG_PER_KWH, 1)} kg CO2.",
    }


def build_community_leaderboard(score, streak, total_usage, selected_date):
    seed = sum(ord(char) for char in selected_date or "wattwise")
    names = ["You", "Eco Nivas", "GreenNest", "VoltVilla", "SmartHome 42", "Solar Street"]
    community = []
    for index, name in enumerate(names):
        if name == "You":
            entry_score = score
            entry_streak = streak
            entry_usage = total_usage
        else:
            variance = ((seed + index * 17) % 19) - 9
            entry_score = max(45, min(98, score + variance + (3 if index % 2 == 0 else -2)))
            entry_streak = max(1, min(14, streak + ((seed + index * 5) % 7) - 3))
            entry_usage = round(max(8, total_usage + (((seed + index * 11) % 13) - 6) * 0.8), 2)
        community.append(
            {
                "name": name,
                "score": entry_score,
                "streak": entry_streak,
                "usage": entry_usage,
                "badge": "Top Saver" if entry_score >= 86 else "Efficient" if entry_score >= 72 else "Improving",
            }
        )
    ranked = sorted(community, key=lambda item: (item["score"], item["streak"]), reverse=True)
    for position, item in enumerate(ranked, start=1):
        item["rank"] = position
    your_rank = next(item["rank"] for item in ranked if item["name"] == "You")
    percentile = round((len(ranked) - your_rank + 1) / len(ranked) * 100)
    return {
        "rows": ranked,
        "your_rank": your_rank,
        "percentile": percentile,
        "message": f"You rank #{your_rank} among similar homes and beat {percentile}% of the community sample.",
    }


def build_personalized_tips(rows, peak_window, saving_mode, predictions):
    tips = [f"AI sees the highest load during {peak_window}. Shift flexible usage to cheaper hours."]
    heavy = sorted(rows, key=lambda row: row["energy_kwh"], reverse=True)
    top = heavy[0]
    tips.append(f"AI predicts your {top['name']} is the biggest cost lever. Reducing 1 hour can ease the next bill.")
    risky = next((row for row in rows if row["faulty"]), None)
    if risky:
        tips.append(f"AI suggests checking {risky['name']} first because its fault score is {int(risky['ai_fault_score'] * 100)} percent.")
    if saving_mode:
        tips.append("Saving mode stays useful, but AI already factors your weekly bill trend into the recommendation.")
    else:
        tips.append(f"AI confidence for the next-bill forecast is {int(predictions['confidence'] * 100)} percent.")
    return tips[:4]


def explain_usage_change(total_usage, predictions, rows):
    delta = round(total_usage - predictions["yesterday_usage"], 2)
    direction = "increased" if delta > 0 else "decreased"
    main_driver = max(rows, key=lambda row: row["energy_kwh"])
    reason = f"AI attributes the strongest bill pressure to {main_driver['name']} at {main_driver['share']}% of load."
    return {"delta": abs(delta), "direction": direction, "reason": reason}


def build_alerts(total_usage, peak_usage, average_usage, appliance_alerts, pet_status, monthly_bill):
    alerts = []
    if total_usage > OVERALL_LIMIT:
        alerts.append(f"Overall usage limit exceeded: {total_usage} kWh today")
    if peak_usage > average_usage * 1.65:
        alerts.append("Sudden spike detected during the peak demand window")
    if monthly_bill > 4200:
        alerts.append(f"Due amount is high: Rs. {monthly_bill}")
    if pet_status == "sick":
        alerts.append("Your energy pet is suffering because the bill is too high")
    alerts.extend(appliance_alerts)
    if not alerts:
        alerts.append("System stable: no major anomalies detected")
    return alerts


def build_pet_rewards(score, weekly_history):
    efficient_days = sum(1 for day in weekly_history if day["usage"] <= 20)
    streak = max(1, min(7, efficient_days))
    badge = "Spark Saver" if score >= 85 else "Steady Guardian" if score >= 70 else "Recovery Mode"
    return streak, badge


def razorpay_config():
    return {
        "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
        "key_secret": os.getenv("RAZORPAY_KEY_SECRET", ""),
        "currency": os.getenv("RAZORPAY_CURRENCY", "INR"),
    }


def create_razorpay_order(amount_rupees):
    config = razorpay_config()
    if not config["key_id"] or not config["key_secret"]:
        return {"enabled": False, "message": "Add Razorpay API keys to enable payments."}

    payload = json.dumps(
        {
            "amount": int(round(amount_rupees * 100)),
            "currency": config["currency"],
            "receipt": f"wattwise-{int(amount_rupees * 100)}",
            "notes": {"product": "WattWise AI due payment"},
        }
    ).encode("utf-8")

    basic_token = base64.b64encode(f"{config['key_id']}:{config['key_secret']}".encode("utf-8")).decode("utf-8")
    http_request = urllib_request.Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={
            "Authorization": f"Basic {basic_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(http_request, timeout=15) as response:
            return {"enabled": True, "order": json.loads(response.read().decode("utf-8")), "key_id": config["key_id"]}
    except error.URLError:
        return {"enabled": False, "message": "Razorpay order creation failed. Check keys or network access."}


@app.route("/dataset/download")
def download_dataset():
    return send_from_directory(DATASET_PATH.parent, DATASET_PATH.name, as_attachment=True)


@app.route("/payment/order", methods=["POST"])
def payment_order():
    amount = request.get_json(silent=True, force=False) or {}
    amount_rupees = parse_float(amount.get("amount"), 0, minimum=1)
    result = create_razorpay_order(amount_rupees)
    return jsonify(result), (200 if result.get("enabled") else 400)


@app.route("/payment/verify", methods=["POST"])
def payment_verify():
    payload = request.get_json(silent=True, force=False) or {}
    payment_id = payload.get("razorpay_payment_id", "")
    order_id = payload.get("razorpay_order_id", "")
    signature = payload.get("razorpay_signature", "")
    secret = razorpay_config()["key_secret"]
    if not secret:
        return jsonify({"verified": False, "message": "Razorpay secret not configured."}), 400
    generated = hmac.new(secret.encode("utf-8"), f"{order_id}|{payment_id}".encode("utf-8"), hashlib.sha256).hexdigest()
    verified = hmac.compare_digest(generated, signature)
    return jsonify({"verified": verified})


@app.route("/", methods=["GET", "POST"])
def index():
    selected_input = request.values.get("selected_date")
    dataset_row, available_dates = get_selected_row(selected_input)
    dataset_defaults = build_dataset_defaults(dataset_row)
    initial_saving_mode = parse_int(dataset_row.get("saving_mode"), 0) == 1 if dataset_row else False
    saving_mode = request.form.get("saving_mode") == "on" if request.method == "POST" else initial_saving_mode
    appliances = build_appliance_state(request.form if request.method == "POST" else {}, dataset_defaults)

    hours, usage = get_hourly_usage(dataset_row, appliances, saving_mode=saving_mode)
    total_usage = round(sum(usage), 2)
    peak_usage = max(usage)
    peak_hour_index = usage.index(peak_usage)
    average_usage = round(total_usage / 24, 2)
    peak_hour = format_hour(peak_hour_index)
    peak_window = get_peak_window(usage)
    hour_labels = [format_hour(hour) for hour in hours]

    weekly_history = build_history(dataset_row["date"] if dataset_row else None)
    daily_cost, monthly_bill = calculate_bill(total_usage)
    score, eco_score = build_scores(total_usage, weekly_history)
    appliance_rows, appliance_alerts, product_recommendations, faulty_rows, usage_reasons = appliance_analysis(appliances, total_usage, monthly_bill)
    predictions = ai_bill_forecast(total_usage, weekly_history, appliance_rows)
    pet_status, pet_message, pet_meter, pet_alert = ai_pet_response(monthly_bill, total_usage, predictions)
    gemini_brain = ai_forecast_and_product_brain(
        total_usage,
        monthly_bill,
        predictions,
        weekly_history,
        appliance_rows,
        product_recommendations,
    )
    predictions["next_bill"] = gemini_brain["next_bill"]
    predictions["confidence"] = gemini_brain["confidence"]
    product_recommendations = merge_ai_recommendations(product_recommendations, gemini_brain["recommendations"])
    appliance_rows = merge_ai_appliance_labels(appliance_rows, gemini_brain["appliances"])
    tou_optimizer = build_tou_optimizer(usage, appliance_rows)
    carbon_dashboard = build_carbon_dashboard(total_usage, predictions, weekly_history)
    usage_change = explain_usage_change(total_usage, predictions, appliance_rows)
    personalized_tips = build_personalized_tips(appliance_rows, peak_window, saving_mode, predictions)
    alerts = build_alerts(total_usage, peak_usage, average_usage, appliance_alerts, pet_status, monthly_bill)
    streak, pet_badge = build_pet_rewards(score, weekly_history)
    leaderboard = build_community_leaderboard(score, streak, total_usage, dataset_row["date"] if dataset_row else "")
    dataset_summary = get_dataset_summary()
    razorpay_ready = bool(razorpay_config()["key_id"] and razorpay_config()["key_secret"])
    gemini_ready = bool(gemini_config()["api_key"])

    suggestion = "WattWise AI acts like a smart energy pet. Keep checking in so it can warn you early, coach better habits, and reduce your bill."
    prediction_message = gemini_brain["prediction_message"]
    if gemini_brain["pet_message"]:
        pet_message = gemini_brain["pet_message"]
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
        recommendations=product_recommendations,
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
        gemini_ready=gemini_ready,
        usage_story=gemini_brain["usage_story"],
        tou_optimizer=tou_optimizer,
        carbon_dashboard=carbon_dashboard,
        leaderboard=leaderboard,
        dataset_summary=dataset_summary,
        dataset_row=dataset_row,
        available_dates=available_dates,
        selected_date=dataset_row["date"] if dataset_row else "",
        due_amount=round(predictions["next_bill"], 2),
        razorpay_key_id=razorpay_config()["key_id"],
        razorpay_ready=razorpay_ready,
    )


if __name__ == "__main__":
    app.run(debug=True)
