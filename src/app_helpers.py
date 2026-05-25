from __future__ import annotations


def short_location_label(value):
    if not value:
        return "Dirección no disponible"
    text = str(value).strip()
    if not text:
        return "Dirección no disponible"
    parts = [part.strip() for part in text.split(',') if part.strip()]
    if not parts:
        return "Dirección no disponible"
    street_keywords = (
        "calle",
        "avenida",
        "av.",
        "jirón",
        "jiron",
        "pasaje",
        "pje",
        "prolongación",
        "prolongacion",
        "carretera",
        "camino",
        "urbanización",
        "urbanizacion",
    )
    for part in parts:
        lowered = part.lower()
        if any(keyword in lowered for keyword in street_keywords):
            return part[:90]
    return parts[0][:90]


def tipo_label_from_codigo(tipo_codigo):
    if tipo_codigo == "menor":
        return "leve / menor"
    if tipo_codigo == "mayor":
        return "grave / mayor"
    return "Selecciona..."


def tipo_codigo_from_label(tipo_label):
    if tipo_label == "leve / menor":
        return "menor"
    if tipo_label == "grave / mayor":
        return "mayor"
    return None


def format_minutes(seconds_value):
    try:
        return f"{float(seconds_value) / 60:.1f} min"
    except Exception:
        return "0.0 min"


def format_km(meters_value):
    try:
        return f"{float(meters_value) / 1000:.2f} km"
    except Exception:
        return "0.00 km"