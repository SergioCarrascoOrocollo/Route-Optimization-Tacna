import streamlit as st
import folium
from folium.plugins import AntPath, Fullscreen
from streamlit_folium import st_folium
import numpy as np
import engine 

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(layout="wide", page_title="NavExpert Pro v5", page_icon="🚗")

# 2. INICIALIZACIÓN DE ESTADO
if 'puntos' not in st.session_state: st.session_state.puntos = []
if 'res' not in st.session_state: st.session_state.res = None

# Solo para el arranque inicial (No se actualizarán en bucle)
map_center_default = [-18.014, -70.250]
map_zoom_default = 15

G = engine.get_graph()
colores = ['#FF4B4B', '#00CC96', '#636EFA', '#FECB52', '#EF553B']

# --- SIDEBAR (Panel de Control y Leyenda) ---
with st.sidebar:
    st.title("🚗 NavExpert Pro")
    st.write(f"Puntos activos: {len(st.session_state.puntos)}")
    
    if st.button("🚀 CALCULAR RUTA", type="primary", use_container_width=True):
        if len(st.session_state.puntos) >= 2:
            with st.spinner("Calculando precisión geométrica..."):
                seg, dist, tiempos = engine.resolver_tsp_pro(G, st.session_state.puntos)
                st.session_state.res = (seg, dist, tiempos)
        else: st.error("Mínimo 2 puntos")
            
    if st.button("🗑️ REINICIAR", use_container_width=True):
        st.session_state.puntos, st.session_state.res = [], None
        st.rerun()

    if st.session_state.res:
        seg, d, t_list = st.session_state.res
        st.divider()
        st.markdown(f"### ⏱️ Total: **{int(sum(t_list)/60)}m {int(sum(t_list)%60)}s**")
        st.markdown(f"### 📏 Distancia: **{d/1000:.2f} km**")
        st.write("---")
        # LEYENDA RECUPERADA
        for i, t in enumerate(t_list):
            color = colores[i % len(colores)]
            st.markdown(f"""
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <div style="width: 15px; height: 15px; background-color: {color}; border-radius: 3px; margin-right: 10px;"></div>
                    <span><b>Tramo {i+1}:</b> {int(t/60)}m {int(t%60)}s</span>
                </div>
            """, unsafe_allow_html=True)

# 3. CREACIÓN DEL MAPA
# La cámara se basa en el primer punto si existe, o en Tacna centro.
# Al no usar center/zoom del map_data, el mapa es fluido al navegar.
center = st.session_state.puntos[0] if st.session_state.puntos else map_center_default

m = folium.Map(location=center, zoom_start=map_zoom_default, tiles='OpenStreetMap')
Fullscreen().add_to(m)

# Dibujar Marcadores Arrastrables
for i, p in enumerate(st.session_state.puntos):
    color = 'green' if i == 0 else 'blue'
    folium.Marker(p, icon=folium.Icon(color=color), tooltip=f"Punto {i}", draggable=True).add_to(m)

# Dibujar Ruta (Geometría fluida)
if st.session_state.res:
    segmentos, _, _ = st.session_state.res
    for idx, s in enumerate(segmentos):
        # Micro-offset casi invisible para evitar solape
        shift = 0.000003 * idx 
        c_off = []
        for i in range(len(s)-1):
            p1, p2 = np.array(s[i]), np.array(s[i+1])
            v = p2-p1; mag = np.linalg.norm(v); n = np.array([-v[1], v[0]])/(mag if mag>0 else 1)
            c_off.append(tuple(p1 + n * shift))
            if i == len(s)-2: c_off.append(tuple(p2 + n * shift))
        AntPath(locations=c_off if c_off else s, color=colores[idx % len(colores)], weight=6).add_to(m)

# 4. CAPTURA DE DATOS (SIN CENTER NI ZOOM PARA EVITAR BUCLE)
map_data = st_folium(
    m, 
    width="100%", 
    height=600, 
    key="mapa_final_estable",
    returned_objects=["last_clicked", "last_object_moved", "last_object_moved_tooltip", "last_object_clicked_tooltip"]
)

# 5. LÓGICA DE INTERACCIÓN (Solo acciones reales disparan el refresh)
if map_data:
    # --- MOVER PUNTO (DRAG) ---
    if map_data.get('last_object_moved'):
        lat_m = map_data['last_object_moved']['lat']
        lng_m = map_data['last_object_moved']['lng']
        tooltip = map_data.get('last_object_moved_tooltip', "")
        if "Punto" in tooltip:
            idx = int(tooltip.split(" ")[1])
            # ACTUALIZAMOS LA COORDENADA
            st.session_state.puntos[idx] = (lat_m, lng_m)
            st.session_state.res = None # Resetear ruta para obligar a recalcular
            st.rerun()

    # --- ELIMINAR PUNTO (CLICK) ---
    elif map_data.get('last_object_clicked_tooltip'):
        tooltip = map_data['last_object_clicked_tooltip']
        if "Punto" in tooltip:
            idx = int(tooltip.split(" ")[1])
            st.session_state.puntos.pop(idx)
            st.session_state.res = None
            st.rerun()

    # --- AÑADIR PUNTO (CLICK MAPA) ---
    elif map_data.get('last_clicked'):
        click = (map_data['last_clicked']['lat'], map_data['last_clicked']['lng'])
        if click not in st.session_state.puntos:
            st.session_state.puntos.append(click)
            st.session_state.res = None
            st.rerun()