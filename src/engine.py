import streamlit as st
import osmnx as ox
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString
import os
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

MAP_FILE = "tacna.graphml"

@st.cache_resource
def get_graph():
    if os.path.exists(MAP_FILE): return ox.load_graphml(MAP_FILE)
    G = ox.graph_from_point([-18.014, -70.250], dist=3000, network_type="drive")
    G = ox.add_edge_speeds(G); G = ox.add_edge_travel_times(G)
    G = ox.truncate.largest_component(G, strongly=True)
    ox.save_graphml(G, MAP_FILE)
    return G

def resolver_tsp_pro(G, puntos_reales):
    if len(puntos_reales) < 2: return [], 0, []
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
    matriz = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                try: matriz[i][j] = nx.shortest_path_length(G_work, n_ids[i], n_ids[j], weight='travel_time')
                except: matriz[i][j] = 1e7
                
    manager = pywrapcp.RoutingIndexManager(n, 1, 0); routing = pywrapcp.RoutingModel(manager)
    def cb(f, t): return int(matriz[manager.IndexToNode(f)][manager.IndexToNode(t)])
    transit_idx = routing.RegisterTransitCallback(cb); routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)
    sol = routing.SolveWithParameters(pywrapcp.DefaultRoutingSearchParameters())

    segmentos, dist_total, tiempos_segmentos = [], 0, []
    if sol:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            u_i = manager.IndexToNode(index)
            v_i = manager.IndexToNode(sol.Value(routing.NextVar(index)))
            if v_i == 0 and index != routing.Start(0): break
            path = nx.shortest_path(G_work, n_ids[u_i], n_ids[v_i], weight='travel_time')
            dist_total += nx.shortest_path_length(G_work, n_ids[u_i], n_ids[v_i], weight='length')
            tiempos_segmentos.append(matriz[u_i][v_i])
            coords_seg = []
            for k in range(len(path)-1):
                d = G_work.get_edge_data(path[k], path[k+1], 0)
                if d and 'geometry' in d: coords_seg.extend([(c[1], c[0]) for c in d['geometry'].coords])
                else: coords_seg.append((G_work.nodes[path[k]]['y'], G_work.nodes[path[k]]['x']))
            segmentos.append(coords_seg)
            index = sol.Value(routing.NextVar(index))
            
    return segmentos, dist_total, tiempos_segmentos