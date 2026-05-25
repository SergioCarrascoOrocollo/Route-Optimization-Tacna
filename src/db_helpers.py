from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from . import geo_utils
except ImportError:  # pragma: no cover - fallback when run as a script
    import geo_utils


def _point_value_to_latlon(value: Any):
    if value is None:
        return None

    if isinstance(value, str):
        return geo_utils.db_point_to_latlon(value)

    if isinstance(value, (list, tuple)) and len(value) == 2:
        first, second = value
        try:
            first_num = float(first)
            second_num = float(second)
        except (TypeError, ValueError):
            raise ValueError(f"Coordenada inválida: {value}") from None
        return (second_num, first_num)

    if isinstance(value, dict):
        if "lon" in value and "lat" in value:
            return (float(value["lat"]), float(value["lon"]))
        if "longitude" in value and "latitude" in value:
            return (float(value["latitude"]), float(value["longitude"]))
        if "x" in value and "y" in value:
            return (float(value["y"]), float(value["x"]))

    if hasattr(value, "x") and hasattr(value, "y"):
        return (float(value.y), float(value.x))

    raise ValueError(f"No se pudo convertir la coordenada: {value!r}")


def normalize_row_points(row: Dict[str, Any], fields: Iterable[str] = ("ubicacion",)) -> Dict[str, Any]:
    normalized = dict(row)
    for field in fields:
        if field in normalized:
            normalized[f"{field}_latlon"] = _point_value_to_latlon(normalized[field])
    return normalized


def normalize_posta_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_row_points(row, fields=("ubicacion",))


def normalize_ambulancia_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_row_points(row, fields=("ubicacion_actual",))


def normalize_incidente_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_row_points(row, fields=("ubicacion",))


def haversine_km(origen_lat: float, origen_lon: float, destino_lat: float, destino_lon: float) -> float:
    """Calcula distancia aproximada en kilómetros entre dos puntos geográficos."""
    radio_tierra_km = 6371.0
    d_lat = radians(destino_lat - origen_lat)
    d_lon = radians(destino_lon - origen_lon)
    lat1 = radians(origen_lat)
    lat2 = radians(destino_lat)

    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radio_tierra_km * c


def _row_to_latlon(row: Dict[str, Any]) -> Tuple[float, float]:
    if row.get("latitud") is not None and row.get("longitud") is not None:
        return float(row["latitud"]), float(row["longitud"])

    if row.get("ubicacion_latlon") is not None:
        return geo_utils.ensure_latlon(row["ubicacion_latlon"])

    if row.get("ubicacion") is not None:
        return geo_utils.db_point_to_latlon(str(row["ubicacion"]))

    raise ValueError(f"La fila no contiene coordenadas válidas: {row!r}")


def _row_available_ambulances(row: Dict[str, Any]) -> Optional[int]:
    for field in (
        "ambulancias_disponibles",
        "ambulancias_disponibles_count",
        "disponibles",
    ):
        value = row.get(field)
        if value is not None:
            return max(int(value), 0)

    if row.get("ambulancias_activas") is not None and row.get("capacidad_ambulancias") is not None:
        capacidad = int(row["capacidad_ambulancias"])
        activas = int(row["ambulancias_activas"])
        return max(capacidad - activas, 0)

    if row.get("capacidad_ambulancias") is not None:
        return max(int(row["capacidad_ambulancias"]), 0)

    return None


def rank_postas_por_distancia(
    incidente_latlon,
    postas: Sequence[Dict[str, Any]],
    tipos_preferidos: Sequence[str] = ("posta_basica", "posta_avanzada"),
    exigir_disponibilidad: bool = True,
) -> List[Dict[str, Any]]:
    incidente_lat, incidente_lon = geo_utils.ensure_latlon(incidente_latlon)
    ranked: List[Dict[str, Any]] = []

    for row in postas:
        normalized = normalize_posta_row(dict(row))
        posta_tipo = normalized.get("tipo")
        if tipos_preferidos and posta_tipo not in tipos_preferidos:
            continue

        disponibles = _row_available_ambulances(normalized)
        if exigir_disponibilidad and disponibles is not None and disponibles <= 0:
            continue

        posta_lat, posta_lon = _row_to_latlon(normalized)
        distancia_km = haversine_km(incidente_lat, incidente_lon, posta_lat, posta_lon)

        normalized["latlon"] = (posta_lat, posta_lon)
        normalized["distancia_km"] = round(distancia_km, 3)
        normalized["ambulancias_disponibles"] = disponibles
        ranked.append(normalized)

    ranked.sort(
        key=lambda fila: (
            float(fila.get("distancia_km", 999999.0)),
            str(fila.get("nombre", "")),
        )
    )
    return ranked


def seleccionar_posta_mas_cercana(
    incidente_latlon,
    postas: Sequence[Dict[str, Any]],
    tipos_preferidos: Sequence[str] = ("posta_basica", "posta_avanzada"),
    exigir_disponibilidad: bool = True,
) -> Optional[Dict[str, Any]]:
    """Devuelve la mejor posta candidata o `None` si no hay postas válidas."""
    ranked = rank_postas_por_distancia(
        incidente_latlon,
        postas,
        tipos_preferidos=tipos_preferidos,
        exigir_disponibilidad=exigir_disponibilidad,
    )
    return ranked[0] if ranked else None


def seleccionar_destino_final(
    incidente_latlon,
    postas: Sequence[Dict[str, Any]],
    tipo_incidente: str,
) -> Optional[Dict[str, Any]]:
    tipo = str(tipo_incidente or "").strip().lower()
    if tipo not in {"menor", "mayor"}:
        raise ValueError(f"Tipo de incidente inválido: {tipo_incidente!r}")

    candidatos = rank_postas_por_distancia(
        incidente_latlon,
        postas,
        tipos_preferidos=("posta_basica", "posta_avanzada", "hospital"),
        exigir_disponibilidad=False,
    )
    if not candidatos:
        return None

    def prioridad_menor(fila: Dict[str, Any]) -> tuple:
        tipo_posta = str(fila.get("tipo", "")).strip().lower()
        if tipo_posta == "posta_basica":
            prioridad = 0
        elif tipo_posta == "posta_avanzada":
            prioridad = 1
        else:
            prioridad = 2
        return (prioridad, float(fila.get("distancia_km", 999999.0)), str(fila.get("nombre", "")))

    def prioridad_mayor(fila: Dict[str, Any]) -> tuple:
        tipo_posta = str(fila.get("tipo", "")).strip().lower()
        nombre = str(fila.get("nombre", "")).strip().lower()
        if tipo_posta == "hospital" and any(
            keyword in nombre for keyword in ("essalud", "seguro social", "referencia", "regional", "general")
        ):
            prioridad = 0
        elif tipo_posta == "hospital":
            prioridad = 1
        elif tipo_posta == "posta_avanzada":
            prioridad = 2
        elif tipo_posta == "posta_basica":
            prioridad = 3
        else:
            prioridad = 4
        return (prioridad, float(fila.get("distancia_km", 999999.0)), nombre)

    if tipo == "menor":
        candidatos = sorted(candidatos, key=prioridad_menor)
    else:
        candidatos = sorted(candidatos, key=prioridad_mayor)

    return candidatos[0] if candidatos else None
