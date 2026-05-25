import streamlit as st
import osmnx as ox
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString
import os
from pathlib import Path
from ortools.constraint_solver import pywrapcp

try:
    from . import geo_utils
except ImportError:
    import geo_utils

BASE_DIR = Path(__file__).resolve().parent
MAP_FILE = BASE_DIR / "tacna_provincia.graphml"
OVERPASS_URLS = [
    "https://z.overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://lz4.overpass-api.de/api",
    "https://overpass-api.de/api",
]
PROVINCE_CENTER = (-18.014, -70.250)
PROVINCE_DISTANCES = [85000, 65000, 45000]
GRAPH_PLACES = [
    "Provincia de Tacna, Tacna, Peru",
    "Tacna Province, Tacna, Peru",
    "Tacna, Peru",
]


def _label_punto(indice):
    return "Origen" if indice == 0 else f"Punto {indice}"


def _build_traza(puntos_reales, matriz_distancia, matriz_tiempo, ruta_nodos):
    etiquetas = [_label_punto(i) for i in range(len(puntos_reales))]
    pasos = []
    visited = {0}

    for paso, (actual, siguiente) in enumerate(zip(ruta_nodos[:-1], ruta_nodos[1:]), start=1):
        candidatos = []
        no_visitados = [i for i in range(1, len(puntos_reales)) if i not in visited]

        for destino in no_visitados:
            candidatos.append({
                "punto": etiquetas[destino],
                "latitud": f"{puntos_reales[destino][0]:.8f}",
                "longitud": f"{puntos_reales[destino][1]:.8f}",
                "distancia_km": f"{matriz_distancia[actual][destino] / 1000:.2f}",
                "tiempo_min": f"{matriz_tiempo[actual][destino] / 60:.2f}",
                "elegido": "SÍ" if destino == siguiente else "No",
                "razon": "Menor costo local entre los no visitados" if destino == siguiente else "",
            })

        candidatos = sorted(candidatos, key=lambda fila: float(fila["tiempo_min"]))

        pasos.append({
            "paso": paso,
            "desde": etiquetas[actual],
            "hacia": etiquetas[siguiente],
            "criterio": "Menor costo local según travel_time",
            "candidatos": candidatos,
        })

        if siguiente != 0:
            visited.add(siguiente)

    matriz_resumen = []
    visited = {0}
    for paso, (actual, siguiente) in enumerate(zip(ruta_nodos[:-1], ruta_nodos[1:]), start=1):
        fila = {"Desde": etiquetas[actual]}
        for destino in range(len(puntos_reales)):
            if destino == actual:
                fila[etiquetas[destino]] = "—"
            elif destino == siguiente:
                if destino == 0:
                    fila[etiquetas[destino]] = f"{matriz_distancia[actual][destino] / 1000:.2f} (Regreso)"
                else:
                    fila[etiquetas[destino]] = f"{matriz_distancia[actual][destino] / 1000:.2f} ({paso}°)"
            elif destino in visited and destino != 0:
                fila[etiquetas[destino]] = "Visitado"
            else:
                fila[etiquetas[destino]] = f"{matriz_distancia[actual][destino] / 1000:.2f}"

        matriz_resumen.append(fila)

        if siguiente != 0:
            visited.add(siguiente)

    return {
        "etiquetas": etiquetas,
        "ruta": [etiquetas[nodo] for nodo in ruta_nodos],
        "pasos": pasos,
        "matriz": matriz_resumen,
    }


def _graph_looks_too_small(G):
    xs = [data.get("x") for _, data in G.nodes(data=True) if data.get("x") is not None]
    ys = [data.get("y") for _, data in G.nodes(data=True) if data.get("y") is not None]
    if not xs or not ys:
        return True

    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return G.number_of_nodes() < 10000 or width < 0.20 or height < 0.20


def _build_province_graph():
    last_error = None
    for overpass_url in OVERPASS_URLS:
        ox.settings.overpass_url = overpass_url
        for dist in PROVINCE_DISTANCES:
            try:
                return ox.graph_from_point(PROVINCE_CENTER, dist=dist, network_type="drive")
            except Exception as exc:
                last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("No se pudo construir el grafo de Tacna")

@st.cache_resource
def get_graph():
    if os.path.exists(MAP_FILE):
        G = ox.load_graphml(MAP_FILE)
        if not _graph_looks_too_small(G):
            return G

    ox.settings.requests_timeout = None
    ox.settings.overpass_settings = "[out:json]"

    G = _build_province_graph()

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    def _apply_fixed_speed_and_curvature(G_work, speed_kph=10):
        speed_ms = speed_kph / 3.6
        for u, v, key, data in G_work.edges(keys=True, data=True):
            length_m = data.get('length')
            if length_m is None or length_m <= 0:
                continue

            curve_penalty = 1.0
            geom = data.get('geometry')
            if geom is not None and hasattr(geom, 'coords'):
                coords = list(geom.coords)
                if len(coords) > 2:
                    lon0, lat0 = coords[0]
                    lon1, lat1 = coords[-1]
                    lat_avg = np.deg2rad((lat0 + lat1) / 2)
                    dx = (lon1 - lon0) * 111320.0 * np.cos(lat_avg)
                    dy = (lat1 - lat0) * 111320.0
                    straight_m = np.hypot(dx, dy)
                    if straight_m > 0:
                        curve_factor = max(1.0, length_m / straight_m)
                        curve_penalty = 1.0 + min(0.8, max(0.0, curve_factor - 1.0) * 0.5)

            travel_time = length_m / speed_ms * curve_penalty
            data['travel_time'] = travel_time
            data['speed_kph'] = speed_kph

    _apply_fixed_speed_and_curvature(G, speed_kph=10)
    G = ox.truncate.largest_component(G, strongly=True)

    ox.save_graphml(G, str(MAP_FILE))
    return G


def _project_point_on_graph(G_work, raw_point, node_id):
    lat, lon = geo_utils.ensure_latlon(raw_point)
    u, v, key = ox.nearest_edges(G_work, lon, lat)
    edge_data = G_work.get_edge_data(u, v, key)
    p_real = Point(lon, lat)

    full_geom = edge_data.get(
        'geometry',
        LineString([
            (G_work.nodes[u]['x'], G_work.nodes[u]['y']),
            (G_work.nodes[v]['x'], G_work.nodes[v]['y'])
        ])
    )
    dist_p = full_geom.project(p_real)
    p_proy = full_geom.interpolate(dist_p)

    G_work.add_node(node_id, x=p_proy.x, y=p_proy.y)

    coords = list(full_geom.coords)
    idx_corte = 0
    for k in range(len(coords) - 1):
        if LineString([coords[k], coords[k + 1]]).distance(p_proy) < 1e-8:
            idx_corte = k + 1
            break

    geom_u = LineString(coords[:idx_corte] + [(p_proy.x, p_proy.y)])
    geom_v = LineString([(p_proy.x, p_proy.y)] + coords[idx_corte:])

    if G_work.has_edge(u, v, key):
        G_work.remove_edge(u, v, key)

    speed = edge_data.get('speed_kph', 30)
    len_u = geom_u.length * 111320
    len_v = geom_v.length * 111320
    time_u = len_u / (speed / 3.6)
    time_v = len_v / (speed / 3.6)

    G_work.add_edge(u, node_id, geometry=geom_u, length=len_u, travel_time=time_u)
    G_work.add_edge(node_id, v, geometry=geom_v, length=len_v, travel_time=time_v)

    if not edge_data.get('oneway', False):
        if G_work.has_edge(v, u, key):
            G_work.remove_edge(v, u, key)
        G_work.add_edge(v, node_id, geometry=geom_v.reverse(), length=len_v, travel_time=time_v)
        G_work.add_edge(node_id, u, geometry=geom_u.reverse(), length=len_u, travel_time=time_u)

    return node_id


def _path_to_coords(G_work, path):
    coords = []
    for k in range(len(path) - 1):
        edge_data = G_work.get_edge_data(path[k], path[k + 1], 0)
        if edge_data and 'geometry' in edge_data:
            tramo = [(c[1], c[0]) for c in edge_data['geometry'].coords]
            if coords and tramo and coords[-1] == tramo[0]:
                coords.extend(tramo[1:])
            else:
                coords.extend(tramo)
        else:
            coords.append((G_work.nodes[path[k]]['y'], G_work.nodes[path[k]]['x']))

    if path:
        coords.append((G_work.nodes[path[-1]]['y'], G_work.nodes[path[-1]]['x']))

    deduplicated = []
    for coord in coords:
        if not deduplicated or deduplicated[-1] != coord:
            deduplicated.append(coord)
    return deduplicated


def compute_route_segment(G, origen_latlon, destino_latlon):
    if G is None:
        return [], 0, 0

    G_work = G.copy()
    origen_id = 990000
    destino_id = 990001

    try:
        _project_point_on_graph(G_work, origen_latlon, origen_id)
        _project_point_on_graph(G_work, destino_latlon, destino_id)

        path = nx.shortest_path(G_work, origen_id, destino_id, weight='travel_time')
        tiempo_seg = nx.shortest_path_length(G_work, origen_id, destino_id, weight='travel_time')
        dist_seg = nx.shortest_path_length(G_work, origen_id, destino_id, weight='length')
        coords = _path_to_coords(G_work, path)
        return coords, tiempo_seg, dist_seg
    except Exception:
        return [], 0, 0


def compute_operational_route(G, posta_latlon, incidente_latlon, destino_latlon):
    coords_a, tiempo_a, dist_a = compute_route_segment(G, posta_latlon, incidente_latlon)
    coords_b, tiempo_b, dist_b = compute_route_segment(G, incidente_latlon, destino_latlon)
    coords_c, tiempo_c, dist_c = compute_route_segment(G, destino_latlon, posta_latlon)
    return {
        "segmento_a": {
            "coords": coords_a,
            "tiempo_seg": tiempo_a,
            "dist_seg": dist_a,
        },
        "segmento_b": {
            "coords": coords_b,
            "tiempo_seg": tiempo_b,
            "dist_seg": dist_b,
        },
        "segmento_c": {
            "coords": coords_c,
            "tiempo_seg": tiempo_c,
            "dist_seg": dist_c,
        },
        "tiempo_total_seg": tiempo_a + tiempo_b + tiempo_c,
        "dist_total_seg": dist_a + dist_b + dist_c,
    }

def resolver_tsp_pro(G, puntos_reales, con_traza=False):
    if len(puntos_reales) < 2:
        return ([], 0, [], None) if con_traza else ([], 0, [])
    G_work = G.copy()
    n_ids = []

    for i, raw in enumerate(puntos_reales):
        n_id = 990000 + i
        n_ids.append(_project_point_on_graph(G_work, raw, n_id))

    n = len(n_ids)
    matriz_tiempo = np.zeros((n, n))
    matriz_distancia = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                try:
                    matriz_tiempo[i][j] = nx.shortest_path_length(G_work, n_ids[i], n_ids[j], weight='travel_time')
                    matriz_distancia[i][j] = nx.shortest_path_length(G_work, n_ids[i], n_ids[j], weight='length')
                except:
                    matriz_tiempo[i][j] = 1e7
                    matriz_distancia[i][j] = 1e7
                
    manager = pywrapcp.RoutingIndexManager(n, 1, 0); routing = pywrapcp.RoutingModel(manager)
    def cb(f, t): return int(matriz_tiempo[manager.IndexToNode(f)][manager.IndexToNode(t)])
    transit_idx = routing.RegisterTransitCallback(cb); routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)
    sol = routing.SolveWithParameters(pywrapcp.DefaultRoutingSearchParameters())

    segmentos, dist_total, tiempos_segmentos = [], 0, []
    ruta_nodos = []
    if sol:
        index = routing.Start(0)
        ruta_nodos.append(manager.IndexToNode(index))
        while not routing.IsEnd(index):
            u_i = manager.IndexToNode(index)
            siguiente_index = sol.Value(routing.NextVar(index))
            v_i = manager.IndexToNode(siguiente_index)
            ruta_nodos.append(v_i)
            path = nx.shortest_path(G_work, n_ids[u_i], n_ids[v_i], weight='travel_time')
            dist_total += nx.shortest_path_length(G_work, n_ids[u_i], n_ids[v_i], weight='length')
            tiempos_segmentos.append(matriz_tiempo[u_i][v_i])
            coords_seg = []
            for k in range(len(path)-1):
                d = G_work.get_edge_data(path[k], path[k+1], 0)
                if d and 'geometry' in d: coords_seg.extend([(c[1], c[0]) for c in d['geometry'].coords])
                else: coords_seg.append((G_work.nodes[path[k]]['y'], G_work.nodes[path[k]]['x']))
            segmentos.append(coords_seg)
            index = siguiente_index
            
    traza = _build_traza(puntos_reales, matriz_distancia, matriz_tiempo, ruta_nodos) if (con_traza and ruta_nodos) else None
    if con_traza:
        return segmentos, dist_total, tiempos_segmentos, traza
    return segmentos, dist_total, tiempos_segmentos