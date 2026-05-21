import streamlit as st
import folium
from folium.plugins import AntPath, Fullscreen
from streamlit_folium import st_folium
import numpy as np
import pandas as pd
import engine 

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(layout="wide", page_title="NavExpert Pro v5", page_icon="🚗")

# 2. INICIALIZACIÓN DE ESTADO
if 'puntos' not in st.session_state: st.session_state.puntos = []
if 'res' not in st.session_state: st.session_state.res = None
if 'mostrar_traza' not in st.session_state: st.session_state.mostrar_traza = True

map_center_default = [-18.014, -70.250]
map_zoom_default = 15

G = engine.get_graph()
colores = ['#FF4B4B', '#00CC96', "#4E59F8", '#FECB52', "#4D2018", '#AB63FA', "#00D1F6", "#FF457A", "#C6FB63", '#FF97FF']

# --- SIDEBAR (Panel de Control y Leyenda) ---
with st.sidebar:
    st.title("🚗 NavExpert Pro")
    st.write(f"Puntos activos: {len(st.session_state.puntos)}")
    st.session_state.mostrar_traza = st.checkbox("Mostrar explicación paso a paso", value=st.session_state.mostrar_traza)
    
    if st.button(" CALCULAR RUTA", type="primary", width="stretch"):
        if len(st.session_state.puntos) >= 2:
            with st.spinner("Calculando precisión geométrica..."):
                seg, dist, tiempos, traza = engine.resolver_tsp_pro(G, st.session_state.puntos, con_traza=True)
                st.session_state.res = (seg, dist, tiempos, traza)
        else: st.error("Mínimo 2 puntos")
            
    if st.button(" REINICIAR", width="stretch"):
        st.session_state.puntos, st.session_state.res = [], None
        st.rerun()

    if st.session_state.res:
        seg, d, t_list, _ = st.session_state.res
        st.divider()
        st.markdown(f"### Total: **{int(sum(t_list)/60)}m {int(sum(t_list)%60)}s**")
        st.markdown(f"### Distancia: **{d/1000:.2f} km**")
        st.write("---")
        for i, t in enumerate(t_list):
            color = colores[i % len(colores)]
            st.markdown(f"""
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <div style="width: 15px; height: 15px; background-color: {color}; border-radius: 3px; margin-right: 10px;"></div>
                    <span><b>Tramo {i+1}:</b> {int(t/60)}m {int(t%60)}s</span>
                </div>
            """, unsafe_allow_html=True)

# 3. CREACIÓN DEL MAPA
center = st.session_state.puntos[0] if st.session_state.puntos else map_center_default

m = folium.Map(location=center, zoom_start=map_zoom_default, tiles='OpenStreetMap')
Fullscreen().add_to(m)

# Dibujar Marcadores fijos
for i, p in enumerate(st.session_state.puntos):
    color = 'green' if i == 0 else 'blue'
    folium.Marker(p, icon=folium.Icon(color=color), tooltip=f"Punto {i}").add_to(m)

# Dibujar Ruta
if st.session_state.res:
    segmentos, _, _, _ = st.session_state.res
    for idx, s in enumerate(segmentos):
        shift = 0.000003 * idx 
        c_off = []
        for i in range(len(s)-1):
            p1, p2 = np.array(s[i]), np.array(s[i+1])
            v = p2-p1; mag = np.linalg.norm(v); n = np.array([-v[1], v[0]])/(mag if mag>0 else 1)
            c_off.append(tuple(p1 + n * shift))
            if i == len(s)-2: c_off.append(tuple(p2 + n * shift))
        AntPath(locations=c_off if c_off else s, color=colores[idx % len(colores)], weight=6).add_to(m)

# 4. CAPTURA DE DATOS
map_data = st_folium(
    m, 
    width="100%", 
    height=600, 
    key="mapa_final_estable",
    returned_objects=["last_clicked", "last_object_moved", "last_object_moved_tooltip", "last_object_clicked_tooltip"]
)

# 5. LÓGICA DE INTERACCIÓN
if map_data:
    if map_data.get('last_object_clicked_tooltip'):
        tooltip = map_data['last_object_clicked_tooltip']
        if "Punto" in tooltip:
            idx = int(tooltip.split(" ")[1])
            st.session_state.puntos.pop(idx)
            st.session_state.res = None
            st.rerun()

    elif map_data.get('last_clicked'):
        click = (map_data['last_clicked']['lat'], map_data['last_clicked']['lng'])
        if click not in st.session_state.puntos:
            st.session_state.puntos.append(click)
            st.session_state.res = None
            st.rerun()

if st.session_state.res and st.session_state.mostrar_traza:
    _, _, _, traza = st.session_state.res
    if traza:
        st.divider()
        st.subheader("Explicación del TSP")
        st.caption("La tabla muestra el costo local entre el nodo actual y los no visitados. OR-Tools optimiza el costo total de la ruta, no solo el vecino más cercano.")
        st.markdown("### Ruta final")
        st.write(" → ".join(traza["ruta"]))

        for paso in traza["pasos"]:
            with st.expander(f"Paso {paso['paso']}: {paso['desde']} → {paso['hacia']}", expanded=(paso["paso"] == 1)):
                st.write(f"Criterio: {paso['criterio']}")
                st.dataframe(pd.DataFrame(paso["candidatos"]), width="stretch", hide_index=True)

        st.markdown("### Matriz resumen")
        st.dataframe(pd.DataFrame(traza["matriz"]), width="stretch", hide_index=True)