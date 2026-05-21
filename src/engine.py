import streamlit as st
import osmnx as ox
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString
import os
from pathlib import Path
from ortools.constraint_solver import pywrapcp

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
    G = ox.truncate.largest_component(G, strongly=True)

    ox.save_graphml(G, str(MAP_FILE))
    return G

def resolver_tsp_pro(G, puntos_reales, con_traza=False):
    if len(puntos_reales) < 2:
        return ([], 0, [], None) if con_traza else ([], 0, [])
    G_work = G.copy()
    n_ids = []
    
    for i, (lat, lon) in enumerate(puntos_reales):
        u, v, key = ox.nearest_edges(G_work, lon, lat)
        edge_data = G_work.get_edge_data(u, v, key)
        p_real = Point(lon, lat)
        
        full_geom = edge_data.get('geometry', LineString([(G_work.nodes[u]['x'], G_work.nodes[u]['y']), (G_work.nodes[v]['x'], G_work.nodes[v]['y'])]))
        dist_p = full_geom.project(p_real)
        p_proy = full_geom.interpolate(dist_p)
        
        n_id = 990000 + i
        G_work.add_node(n_id, x=p_proy.x, y=p_proy.y)
        
        coords = list(full_geom.coords)
        idx_corte = 0
        for k in range(len(coords)-1):
            if LineString([coords[k], coords[k+1]]).distance(p_proy) < 1e-8:
                idx_corte = k + 1
                break
        
        geom_u = LineString(coords[:idx_corte] + [(p_proy.x, p_proy.y)])
        geom_v = LineString([(p_proy.x, p_proy.y)] + coords[idx_corte:])

        if G_work.has_edge(u, v, key): G_work.remove_edge(u, v, key)
        speed = edge_data.get('speed_kph', 30)
        G_work.add_edge(u, n_id, geometry=geom_u, length=geom_u.length*111320, travel_time=(geom_u.length*111320)/(speed/3.6))
        G_work.add_edge(n_id, v, geometry=geom_v, length=geom_v.length*111320, travel_time=(geom_v.length*111320)/(speed/3.6))
        
        if not edge_data.get('oneway', False):
            if G_work.has_edge(v, u, key): G_work.remove_edge(v, u, key)
            G_work.add_edge(v, n_id, geometry=geom_v.reverse(), length=geom_v.length*111320, travel_time=(geom_v.length*111320)/(speed/3.6))
            G_work.add_edge(n_id, u, geometry=geom_u.reverse(), length=geom_u.length*111320, travel_time=(geom_u.length*111320)/(speed/3.6))
        n_ids.append(n_id)

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