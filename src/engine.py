# =============================================================================
# engine.py — Motor principal del sistema de optimización de rutas
# =============================================================================
# Contiene:
#   1. AgenteRecocidoSimulado : clase del agente IA (metaheurística SA)
#   2. get_graph()            : carga/construye el grafo vial de Tacna
#   3. compute_route_segment(): calcula la ruta mínima entre dos puntos
#   4. resolver_tsp_pro()     : resuelve el TSP completo con el agente SA
# =============================================================================

import streamlit as st      # Framework de interfaz web
import osmnx as ox          # Extracción y manejo de grafos viales (OpenStreetMap)
import networkx as nx       # Algoritmos de grafos (Dijkstra, rutas mínimas)
import numpy as np          # Matrices de costos y cálculos numéricos
from shapely.geometry import Point, LineString  # Geometría vial (proyecciones)
import os
from pathlib import Path

import math    # Función exp() para el criterio de Metropolis
import random  # Selección aleatoria para la mutación del SA

class AgenteRecocidoSimulado:
    """
    Agente de Inteligencia Artificial basado en la metaheurística de Recocido Simulado
    (Simulated Annealing, SA) para resolver el Problema del Viajante (TSP).

    El agente modela el problema de optimización de rutas de emergencia como un TSP
    sobre una matriz de costos temporales precalculada. Utiliza el criterio de
    Metropolis para escapar de óptimos locales, aceptando temporalmente soluciones
    peores con una probabilidad que decrece conforme la temperatura disminuye.

    Parámetros
    ----------
    matriz_costos : list[list[float]]
        Matriz n×n de tiempos de viaje mínimos entre los n puntos de parada (segundos).
        matriz_costos[i][j] = tiempo en segundos de ir del punto i al punto j.
    temp_inicial : float
        Temperatura inicial T₀. Valores altos favorecen la exploración.
        Default: 10000.0
    alfa : float
        Factor de enfriamiento geométrico α ∈ (0, 1).
        La temperatura se actualiza como: T_{k+1} = α · T_k
        Default: 0.95
    iteraciones_max : int
        Número máximo de iteraciones del bucle principal.
        Default: 1000
    """

    def __init__(self, matriz_costos, temp_inicial=10000.0, alfa=0.95, iteraciones_max=1000):
        self.matriz = matriz_costos          # Matriz de costos temporales M[i][j]
        self.n = len(matriz_costos)          # Número de puntos de parada
        self.temp_inicial = temp_inicial     # Temperatura inicial T₀
        self.alfa = alfa                     # Tasa de enfriamiento geométrico α
        self.iteraciones = iteraciones_max   # Límite de iteraciones k_max

    def _calcular_costo(self, ruta):
        """
        Calcula el costo total de una ruta sumando los tiempos de viaje entre paradas consecutivas.

        Función objetivo: C(R) = Σ M[R_i][R_{i+1}] para i = 0..n-2

        Parámetros
        ----------
        ruta : list[int]
            Permutación de índices de puntos (e.g., [0, 2, 1, 3]).

        Retorna
        -------
        float : Costo total de la ruta en segundos.
        """
        costo = 0.0
        for i in range(len(ruta) - 1):
            costo += self.matriz[ruta[i]][ruta[i+1]]
        return costo

    def optimizar(self):
        """
        Ejecuta el algoritmo de Recocido Simulado para encontrar la ruta de menor costo.

        El algoritmo:
        1. Fija el punto 0 como origen (posta de salud) y mezcla el resto aleatoriamente.
        2. En cada iteración, genera un vecino intercambiando dos paradas aleatorias.
        3. Acepta el vecino si mejora la solución, o con probabilidad exp(-ΔC/T) si la empeora.
        4. Reduce la temperatura geométricamente: T_{k+1} = α · T_k.
        5. Se detiene si T ≤ 0.01 (convergencia) o se alcanza el límite de iteraciones.

        Retorna
        -------
        mejor_ruta : list[int]
            Permutación óptima encontrada (orden de visita de los puntos).
        mejor_costo : float
            Costo total de la mejor ruta (segundos).
        historial_costos : list[float]
            Costo del mejor estado en cada iteración (útil para graficar convergencia).
        """
        # Caso trivial: con 2 o menos puntos no hay optimización posible
        if self.n <= 2:
            return list(range(self.n)), self._calcular_costo(list(range(self.n))), []

        # --- 1. Estado inicial ---
        # El nodo 0 (posta de origen) siempre es el punto de partida.
        # Solo se mezclan aleatoriamente los índices 1..n-1 (incidente, destinos).
        ruta_actual = list(range(1, self.n))
        random.shuffle(ruta_actual)
        ruta_actual = [0] + ruta_actual  # [0, σ₁, σ₂, ..., σ_{n-1}]

        costo_actual = self._calcular_costo(ruta_actual)

        # Guardamos la mejor solución global encontrada durante toda la búsqueda
        mejor_ruta = ruta_actual[:]
        mejor_costo = costo_actual
        temp = self.temp_inicial  # Temperatura inicial T = T₀

        # Historial para graficar la curva de convergencia del agente
        historial_costos = []

        # --- 2. Bucle principal de Recocido Simulado ---
        for iteracion in range(self.iteraciones):

            # Criterio de parada por temperatura mínima (el sistema se ha "enfriado")
            if temp <= 0.01:
                break

            # --- Operador de mutación: swap de dos paradas ---
            # Se seleccionan dos índices aleatorios de {1,...,n-1} (nunca el origen 0)
            # y se intercambian sus posiciones en la ruta para generar un vecino R'.
            idx1, idx2 = random.sample(range(1, self.n), 2)
            vecino = ruta_actual[:]
            vecino[idx1], vecino[idx2] = vecino[idx2], vecino[idx1]

            costo_vecino = self._calcular_costo(vecino)

            # =========================================================================
            # 3. CRITERIO DE ACEPTACIÓN DE METROPOLIS (La "magia" del algoritmo)
            # =========================================================================
            # Calcula la diferencia de costo: ΔC = Costo(Ruta Nueva) - Costo(Ruta Actual)
            #
            # REGLA 1: Si ΔC < 0 (la ruta nueva es más rápida), se acepta SIEMPRE (Probabilidad = 1.0).
            # REGLA 2: Si ΔC ≥ 0 (la ruta nueva es más lenta), NO se rechaza automáticamente.
            #          Se acepta con una probabilidad = exp(-ΔC / Temperatura).
            #
            # ¿Por qué? Para evitar quedarse atascado en "óptimos locales". Aceptar temporalmente 
            # rutas peores permite al algoritmo saltar y seguir explorando el mapa.
            # =========================================================================
            
            if costo_vecino < costo_actual:
                probabilidad = 1.0  # REGLA 1: Mejora garantizada, siempre aceptar
            else:
                delta = costo_vecino - costo_actual
                try:
                    # REGLA 2: Ecuación de Metropolis (Distribución de Boltzmann)
                    probabilidad = math.exp(-delta / temp)  
                except OverflowError:
                    probabilidad = 0.0  # Si la ruta es exageradamente peor, probabilidad casi 0

            # Transición de estado según la probabilidad calculada
            if random.random() < probabilidad:
                ruta_actual = vecino
                costo_actual = costo_vecino

                # Actualizar el óptimo global si la nueva solución es mejor
                if costo_actual < mejor_costo:
                    mejor_ruta = ruta_actual[:]
                    mejor_costo = costo_actual

            # Registrar el mejor costo de esta iteración para el historial
            historial_costos.append(mejor_costo)

            # --- 4. Enfriamiento geométrico ---
            # T_{k+1} = α · T_k  (reduce la temperatura en cada iteración)
            temp *= self.alfa

        return mejor_ruta, mejor_costo, historial_costos


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
    """Devuelve la etiqueta legible de un punto: 'Origen' para el índice 0, 'Punto N' para el resto."""
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
    """
    Verifica si el grafo cargado desde disco es válido para la Provincia de Tacna.

    Un grafo se considera insuficiente si tiene menos de 10,000 nodos o
    si su cobertura geográfica es menor a 0.20° en alguna dimensión
    (lo que indicaría que solo cubre el centro urbano, no toda la provincia).

    Retorna True si el grafo es demasiado pequeño y debe regenerarse.
    """
    xs = [data.get("x") for _, data in G.nodes(data=True) if data.get("x") is not None]
    ys = [data.get("y") for _, data in G.nodes(data=True) if data.get("y") is not None]
    if not xs or not ys:
        return True  # Grafo vacío o sin coordenadas

    width = max(xs) - min(xs)   # Extensión longitudinal en grados
    height = max(ys) - min(ys)  # Extensión latitudinal en grados
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
    """
    Carga o construye el grafo vial de la Provincia de Tacna.

    Flujo:
    1. Intenta cargar el grafo desde el archivo GraphML local (tacna_provincia.graphml).
    2. Si el archivo no existe o el grafo es insuficiente, lo descarga desde OpenStreetMap
       usando múltiples URLs de Overpass API como fallback.
    3. Calcula velocidades de viaje y tiempos reales por arista.
    4. Aplica una penalización de curvatura a las aristas sinuosas.
    5. Persiste el grafo resultante en disco para futuras ejecuciones.

    El decorador @st.cache_resource garantiza que el grafo se carga una sola vez
    por sesión de Streamlit, evitando operaciones costosas repetidas.

    Retorna
    -------
    G : networkx.MultiDiGraph
        Grafo dirigido de la red vial con atributos 'length', 'speed_kph', 'travel_time'.
    """
    # Intentar cargar desde disco para evitar descarga repetida
    if os.path.exists(MAP_FILE):
        G = ox.load_graphml(MAP_FILE)
        if not _graph_looks_too_small(G):
            return G  # Grafo válido encontrado en caché local

    # El grafo no existe o es insuficiente: descargarlo de OpenStreetMap
    ox.settings.requests_timeout = None          # Sin límite de tiempo para la descarga
    ox.settings.overpass_settings = "[out:json]" # Formato de respuesta de Overpass API

    G = _build_province_graph()  # Descarga con fallback entre múltiples servidores

    # Enriquecer el grafo con velocidades y tiempos de viaje estándar de OSMnx
    G = ox.add_edge_speeds(G)        # Asigna velocidades según tipo de vía
    G = ox.add_edge_travel_times(G)  # Calcula travel_time = length / speed

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
    """
    Calcula la ruta mínima entre dos puntos geoespaciales sobre el grafo vial.

    Proyecta ambos puntos sobre la arista más cercana del grafo y luego
    aplica Dijkstra sobre el atributo 'travel_time' para encontrar el camino
    de menor tiempo de viaje.

    Parámetros
    ----------
    G : networkx.MultiDiGraph
        Grafo vial de la Provincia de Tacna.
    origen_latlon : tuple(float, float)
        Coordenadas (latitud, longitud) del punto de origen.
    destino_latlon : tuple(float, float)
        Coordenadas (latitud, longitud) del punto de destino.

    Retorna
    -------
    coords : list[tuple]
        Lista de coordenadas (lat, lon) que forman la polilínea de la ruta.
    tiempo_seg : float
        Tiempo de viaje en segundos.
    dist_seg : float
        Distancia en metros.
    """
    if G is None:
        return [], 0, 0

    G_work = G.copy()  # Copia de trabajo para no modificar el grafo global
    # IDs virtuales para los nodos proyectados (fuera del rango de nodos OSM)
    origen_id = 990000
    destino_id = 990001

    try:
        # Proyectar origen y destino sobre las aristas más cercanas del grafo
        _project_point_on_graph(G_work, origen_latlon, origen_id)
        _project_point_on_graph(G_work, destino_latlon, destino_id)

        # Calcular ruta mínima usando Dijkstra con peso 'travel_time'
        path = nx.shortest_path(G_work, origen_id, destino_id, weight='travel_time')
        tiempo_seg = nx.shortest_path_length(G_work, origen_id, destino_id, weight='travel_time')
        dist_seg = nx.shortest_path_length(G_work, origen_id, destino_id, weight='length')
        coords = _path_to_coords(G_work, path)  # Convertir nodos a coordenadas para el mapa
        return coords, tiempo_seg, dist_seg
    except Exception:
        return [], 0, 0  # Si no existe ruta conectada, retornar valores vacíos


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
                
    # 5. Resolver ruta usando Inteligencia Artificial (Recocido Simulado)
    print("Iniciando optimización con Recocido Simulado...")
    agente_ia = AgenteRecocidoSimulado(
        matriz_costos=matriz_tiempo, 
        temp_inicial=5000.0, 
        alfa=0.98, 
        iteraciones_max=2000
    )
    
    mejor_ruta_indices, costo_total, historial = agente_ia.optimizar()
    mejor_ruta_indices.append(0) # Cerrar el ciclo volviendo a la posta (origen)
    
    segmentos, dist_total, tiempos_segmentos = [], 0, []
    ruta_nodos = []
    
    if len(mejor_ruta_indices) > 0:
        # 6. Reconstruir los trazos en el mapa
        ruta_nodos.append(mejor_ruta_indices[0])
        for i in range(len(mejor_ruta_indices) - 1):
            u_i = mejor_ruta_indices[i]
            v_i = mejor_ruta_indices[i+1]
            ruta_nodos.append(v_i)
            
            path = nx.shortest_path(G_work, n_ids[u_i], n_ids[v_i], weight='travel_time')
            dist_total += nx.shortest_path_length(G_work, n_ids[u_i], n_ids[v_i], weight='length')
            tiempos_segmentos.append(matriz_tiempo[u_i][v_i])
            
            coords_seg = []
            for k in range(len(path)-1):
                d = G_work.get_edge_data(path[k], path[k+1], 0)
                if d and 'geometry' in d: 
                    coords_seg.extend([(c[1], c[0]) for c in d['geometry'].coords])
                else: 
                    coords_seg.append((G_work.nodes[path[k]]['y'], G_work.nodes[path[k]]['x']))
            coords_seg.append((G_work.nodes[path[-1]]['y'], G_work.nodes[path[-1]]['x']))
            segmentos.append(coords_seg)
            
    traza = _build_traza(puntos_reales, matriz_distancia, matriz_tiempo, ruta_nodos) if (con_traza and ruta_nodos) else None
    
    if con_traza:
        return segmentos, dist_total, tiempos_segmentos, traza
    return segmentos, dist_total, tiempos_segmentos