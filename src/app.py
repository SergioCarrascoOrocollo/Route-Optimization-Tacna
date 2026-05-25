import streamlit as st
import folium
from folium.plugins import AntPath, Fullscreen
from streamlit_folium import st_folium
import numpy as np
import pandas as pd
import engine 
import geo_utils
import os
import threading
import time
import json
import requests
from app_helpers import (
    format_km,
    format_minutes,
    short_location_label,
    tipo_codigo_from_label,
    tipo_label_from_codigo,
)

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(layout="wide", page_title="NavExpert Pro v5", page_icon="🚗")

# 2. INICIALIZACIÓN DE ESTADO
if 'incidente' not in st.session_state: st.session_state.incidente = None
if 'res' not in st.session_state: st.session_state.res = None
if 'posta_origen' not in st.session_state: st.session_state.posta_origen = None
if 'posta_destino' not in st.session_state: st.session_state.posta_destino = None
if 'operational' not in st.session_state: st.session_state.operational = None
if 'incidente_db_id' not in st.session_state: st.session_state.incidente_db_id = None
if 'tabla_postas_cercanas' not in st.session_state: st.session_state.tabla_postas_cercanas = None
if 'tabla_destino_candidatos' not in st.session_state: st.session_state.tabla_destino_candidatos = None


def _supabase_rpc(func_name, payload):
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_service_key = (
        os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    )
    if not supabase_url or not supabase_service_key:
        return None, 'No SUPABASE credentials found'
    url = supabase_url.rstrip('/') + '/rest/v1/rpc/' + func_name
    headers = {
        'apikey': supabase_service_key,
        'Authorization': f'Bearer {supabase_service_key}',
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        return data, None if resp.status_code in (200, 201, 204) else f'HTTP {resp.status_code}: {resp.text}'
    except Exception as exc:
        return None, str(exc)


def _rank_destination_candidates(candidates, tipo_codigo):
    tipo_codigo = (tipo_codigo or 'menor').strip().lower()

    def priority(row):
        tipo = str(row.get('tipo', '')).strip().lower()
        nombre = str(row.get('nombre', '')).strip().lower()
        if tipo_codigo == 'menor':
            if tipo == 'posta_basica':
                base = 0
            elif tipo == 'posta_avanzada':
                base = 1
            elif tipo == 'hospital':
                base = 2
            else:
                base = 3
            return (base, float(row.get('distancia_km', 999999.0)), nombre)

        if tipo == 'hospital':
            base = 0
        elif tipo == 'posta_avanzada':
            base = 2
        elif tipo == 'posta_basica':
            base = 3
        else:
            base = 4
        return (base, float(row.get('distancia_km', 999999.0)), nombre)

    return sorted(candidates, key=priority)


def _normalize_postas_table(records):
    if not records:
        return None
    df = pd.DataFrame(records)
    if df.empty:
        return None
    columns = [col for col in ['nombre', 'tipo', 'distancia_km'] if col in df.columns]
    if not columns:
        return None
    return df.loc[:, columns].head(5)

map_center_default = [-18.014, -70.250]
map_zoom_default = 15

G = engine.get_graph()
colores = ['#FF4B4B', '#00CC96', "#4E59F8", '#FECB52', "#4D2018", '#AB63FA', "#00D1F6", "#FF457A", "#C6FB63", '#FF97FF']

# --- SIDEBAR (Panel de Control y Leyenda) ---
with st.sidebar:
    st.title("🚗 NavExpert Pro")
    if st.session_state.incidente:
        st.write("Incidente activo: 1")
    else:
        st.write("Incidente activo: 0")

    tipo_incidente_opciones = ["Selecciona...", "leve / menor", "grave / mayor"]
    tipo_incidente_actual = None
    if st.session_state.incidente:
        tipo_label_inicial = tipo_label_from_codigo(st.session_state.incidente.get('tipo'))
        tipo_incidente_actual = st.selectbox(
            "Tipo de incidente",
            tipo_incidente_opciones,
            index=tipo_incidente_opciones.index(tipo_label_inicial) if tipo_label_inicial in tipo_incidente_opciones else 0,
            key="tipo_incidente_selector",
        )
        if tipo_incidente_actual == "Selecciona...":
            st.session_state.incidente['tipo'] = None
            st.session_state.incidente['tipo_label'] = None
        else:
            st.session_state.incidente['tipo'] = tipo_codigo_from_label(tipo_incidente_actual)
            st.session_state.incidente['tipo_label'] = tipo_incidente_actual
        st.caption(f"Incidente: {short_location_label(st.session_state.incidente.get('direccion'))}")
    
    if st.button(" CALCULAR RUTA", type="primary", width="stretch"):
        if st.session_state.incidente:
            if not st.session_state.incidente.get('tipo'):
                st.warning("Selecciona primero el tipo de incidente.")
                st.stop()

            # Calcular ruta de forma silenciosa; el despacho automático ocurre después.
            # Preparar credenciales SUPABASE desde entorno o .env
            def _load_dotenv(path='.env'):
                if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
                    return
                try:
                    base = os.path.dirname(__file__)
                    env_path = os.path.join(base, '..', path)
                    env_path = os.path.abspath(env_path)
                    if not os.path.exists(env_path):
                        env_path = os.path.join(os.getcwd(), path)
                    if os.path.exists(env_path):
                        with open(env_path, 'r', encoding='utf8') as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith('#') or '=' not in line:
                                    continue
                                k, v = line.split('=', 1)
                                k = k.strip(); v = v.strip().strip('"').strip("'")
                                if k not in os.environ:
                                    os.environ[k] = v
                except Exception:
                    pass

            _load_dotenv()

            SUPABASE_URL = os.environ.get('SUPABASE_URL')
            SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

            # 1) Crear incidente en la BD
            incidente_local = st.session_state.incidente
            incidente_db = None
            ubic = f"({incidente_local['lon']},{incidente_local['lat']})"
            payload = {
                'ubicacion': ubic,
                'tipo': incidente_local.get('tipo') or 'menor',
            }
            insert_url = SUPABASE_URL.rstrip('/') + '/rest/v1/incidentes' if SUPABASE_URL else None
            if not insert_url:
                st.error('Falta SUPABASE_URL en .env')
                st.stop()

            if not SUPABASE_SERVICE_KEY:
                st.error('Falta SUPABASE_SERVICE_KEY en .env')
                st.stop()

            insert_headers = {
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation',
            }
            try:
                insert_resp = requests.post(insert_url, headers=insert_headers, json=payload, timeout=30)
                try:
                    insert_data = insert_resp.json()
                except Exception:
                    insert_data = None
                if insert_resp.status_code not in (200, 201):
                    st.error(f'No se pudo crear incidente en Supabase: HTTP {insert_resp.status_code}: {insert_resp.text}')
                    st.stop()
                if isinstance(insert_data, list) and len(insert_data) > 0:
                    incidente_db = insert_data[0].get('id')
                    st.session_state.incidente_db_id = incidente_db
            except Exception as exc:
                st.error(f'No se pudo crear incidente en Supabase: {exc}')
                st.stop()

            # 2) Obtener posta destino óptima y una posta origen (RPCs)
            lat = incidente_local['lat']
            lon = incidente_local['lon']
            destino_resp, destino_err = _supabase_rpc('obtener_posta_destino_optima', {'p_lat': lat, 'p_lon': lon, 'p_tipo_incidente': incidente_local.get('tipo') or 'menor'})
            origen_resp, origen_err = _supabase_rpc('obtener_postas_cercanas', {'p_lat': lat, 'p_lon': lon, 'p_radio_km': 10})

            st.session_state.tabla_postas_cercanas = origen_resp if isinstance(origen_resp, list) else ([origen_resp] if origen_resp else [])
            st.session_state.tabla_destino_candidatos = _rank_destination_candidates(
                st.session_state.tabla_postas_cercanas,
                incidente_local.get('tipo') or 'menor'
            )[:5]

            posta_origen = None
            posta_destino = None
            try:
                if origen_resp and isinstance(origen_resp, list) and len(origen_resp) > 0:
                    posta_origen = origen_resp[0]
                if destino_resp and (isinstance(destino_resp, list) or isinstance(destino_resp, dict)):
                    if isinstance(destino_resp, list) and len(destino_resp) > 0:
                        posta_destino = destino_resp[0]
                    elif isinstance(destino_resp, dict):
                        posta_destino = destino_resp
            except Exception:
                posta_origen = posta_destino = None

            # fallback: usar centro de provincia si no hay postas
            G = engine.get_graph()
            if posta_origen:
                posta_origen_latlon = (float(posta_origen['latitud']), float(posta_origen['longitud']))
            else:
                posta_origen_latlon = engine.PROVINCE_CENTER

            if posta_destino:
                posta_destino_latlon = (float(posta_destino['latitud']), float(posta_destino['longitud']))
            else:
                posta_destino_latlon = engine.PROVINCE_CENTER

            # 3) Calcular ruta operacional (A/B/C)
            ruta = engine.compute_operational_route(G, posta_origen_latlon, (lat, lon), posta_destino_latlon)
            # Convertir a formato esperado por la UI: una lista de segmentos (coords)
            segmentos = [ruta['segmento_a']['coords'], ruta['segmento_b']['coords'], ruta['segmento_c']['coords']]
            tiempo_total = ruta.get('tiempo_total_seg')
            st.session_state.res = (segmentos, ruta.get('dist_total_seg'), tiempo_total, None)
            # Guardar postas y resumen operativo en session_state para sidebar y marcadores
            st.session_state.posta_origen = posta_origen
            st.session_state.posta_destino = posta_destino
            st.session_state.operational = {
                'incidente_label': short_location_label(incidente_local.get('direccion')),
                'tipo_incidente': incidente_local.get('tipo_label') or tipo_label_from_codigo(incidente_local.get('tipo')),
                'posta_origen_nombre': (posta_origen or {}).get('nombre', 'N/A'),
                'posta_destino_nombre': (posta_destino or {}).get('nombre', 'N/A'),
                'tiempo_a': ruta['segmento_a'].get('tiempo_seg', 0),
                'tiempo_b': ruta['segmento_b'].get('tiempo_seg', 0),
                'tiempo_c': ruta['segmento_c'].get('tiempo_seg', 0),
                'tiempo_total': ruta.get('tiempo_total_seg', 0),
                'dist_total': ruta.get('dist_total_seg', 0),
                'dist_a': ruta['segmento_a'].get('dist_seg', 0),
                'dist_b': ruta['segmento_b'].get('dist_seg', 0),
                'dist_c': ruta['segmento_c'].get('dist_seg', 0),
            }

            # 4) Programar despacho automático en hilo (5s)
            def _delayed_dispatch(incidente_id):
                time.sleep(5)
                if not incidente_id:
                    return
                resp, err = _supabase_rpc('despachar_incidente', {'p_incidente_id': incidente_id})
                if err:
                    return
                dispatch_payload = resp[0] if isinstance(resp, list) and resp else resp
                ambulancia_id = dispatch_payload.get('ambulancia_id') if isinstance(dispatch_payload, dict) else None
                if ambulancia_id:
                    _supabase_rpc('registrar_retorno_ambulancia', {
                        'p_ambulancia_id': ambulancia_id,
                        'p_incidente_id': incidente_id,
                    })

            if incidente_db:
                t = threading.Thread(target=_delayed_dispatch, args=(incidente_db,))
                t.daemon = True
                t.start()
        else:
            st.error("Primero crea un incidente con click izquierdo")
            
    if st.button(" REINICIAR", width="stretch"):
        st.session_state.incidente, st.session_state.res = None, None
        st.session_state.posta_origen = None
        st.session_state.posta_destino = None
        st.session_state.operational = None
        st.session_state.incidente_db_id = None
        st.session_state.tabla_postas_cercanas = None
        st.session_state.tabla_destino_candidatos = None
        if os.environ.get('SUPABASE_URL') and (os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')):
            try:
                _supabase_rpc('reiniciar_estado_operativo', {})
            except Exception:
                pass
        st.rerun()

    if st.session_state.incidente:
        st.divider()
        st.markdown("### Incidente actual")
        st.write(f"Incidente: {short_location_label(st.session_state.incidente.get('direccion'))}")
        st.write(f"Tipo: {st.session_state.incidente.get('tipo_label') or 'Selecciona...'}")
        if not st.session_state.get('operational'):
            st.caption("Selecciona la severidad y calcula la ruta.")

        if st.session_state.get('operational'):
            op = st.session_state.operational
            st.divider()
            st.markdown("### Resumen operativo")
            st.write(f"Incidente: {op.get('incidente_label', 'Dirección no disponible')}")
            st.write(f"Puesto de salud mas cercano: {op.get('posta_origen_nombre', 'N/A')}")
            st.write(f"Tipo de incidente: {op.get('tipo_incidente', 'N/A')}")
            st.write(f"Punto de envio: {op.get('posta_destino_nombre', 'N/A')}")
            st.write(f"🔴 Tiempo de llegada (puesto a incidente): {format_minutes(op.get('tiempo_a', 0))}")
            st.write(f"🟢 Tiempo de llegada (incidente a destino): {format_minutes(op.get('tiempo_b', 0))}")
            st.write(f"🔵 Tiempo de llegada (destino a puesto): {format_minutes(op.get('tiempo_c', 0))}")
            st.write(f"Tiempo total aproximado (total): {format_minutes(op.get('tiempo_total', 0))}")
            st.write(f"Distancia total aproximada (puesto a destino): {format_km(op.get('dist_total', 0))}")

# 3. CREACIÓN DEL MAPA
center = (
    [st.session_state.incidente['lat'], st.session_state.incidente['lon']]
    if st.session_state.incidente
    else map_center_default
)

m = folium.Map(location=center, zoom_start=map_zoom_default, tiles='OpenStreetMap')
Fullscreen().add_to(m)

# Dibujar Marcadores fijos
if st.session_state.incidente:
    folium.Marker(
        [st.session_state.incidente['lat'], st.session_state.incidente['lon']],
        icon=folium.Icon(color='red'),
        tooltip='Incidente activo',
    ).add_to(m)

# Dibujar marcadores de posta origen/destino si existen
if st.session_state.get('posta_origen'):
    po = st.session_state.posta_origen
    try:
        lat = float(po.get('latitud') or po.get('lat') or po.get('latitud'))
        lon = float(po.get('longitud') or po.get('lon') or po.get('longitud'))
        folium.Marker([lat, lon], icon=folium.Icon(color='green'), tooltip=f"Posta origen: {po.get('nombre', po.get('id', 'origen'))}").add_to(m)
    except Exception:
        pass

if st.session_state.get('posta_destino'):
    posta_destino_data = st.session_state.posta_destino
    try:
        lat = float(posta_destino_data.get('latitud') or posta_destino_data.get('lat') or posta_destino_data.get('latitud'))
        lon = float(posta_destino_data.get('longitud') or posta_destino_data.get('lon') or posta_destino_data.get('longitud'))
        folium.Marker([lat, lon], icon=folium.Icon(color='blue'), tooltip=f"Posta destino: {posta_destino_data.get('nombre', posta_destino_data.get('posta_id', 'destino'))}").add_to(m)
    except Exception:
        pass

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
            st.info("El flujo actual usa un solo incidente. Usa Reiniciar para borrar el incidente activo.")

    elif map_data.get('last_clicked'):
        if st.session_state.incidente is not None:
            st.warning("Ya existe un incidente activo. Presiona Reiniciar para registrar otro.")
        else:
            raw = (map_data['last_clicked']['lat'], map_data['last_clicked']['lng'])
            try:
                click = geo_utils.ensure_latlon(raw)
            except ValueError:
                click = (float(raw[0]), float(raw[1]))

            direccion = geo_utils.reverse_geocode(click[0], click[1])

            st.session_state.incidente = {
                "lat": click[0],
                "lon": click[1],
                "tipo": None,
                "tipo_label": None,
                "direccion": direccion,
            }
            st.session_state.res = None
            st.rerun()

if st.session_state.tabla_postas_cercanas or st.session_state.tabla_destino_candidatos:
    st.divider()
    st.markdown("### Resultados de Supabase")
    cols = st.columns(2)
    with cols[0]:
        st.subheader("Postas cercanas")
        df_postas = _normalize_postas_table(st.session_state.tabla_postas_cercanas)
        if df_postas is not None and not df_postas.empty:
            st.dataframe(df_postas)
        else:
            st.write("No se encontraron postas cercanas.")
    with cols[1]:
        st.subheader("Candidatos a destino")
        df_destinos = _normalize_postas_table(st.session_state.tabla_destino_candidatos)
        if df_destinos is not None and not df_destinos.empty:
            st.dataframe(df_destinos)
        else:
            st.write("No se encontraron candidatos a destino.")

if st.session_state.get('operational'):
    op = st.session_state.operational
    st.divider()
    st.markdown("### Explicación paso a paso")
    st.write(
        f"1. La ambulancia sale de la posta más cercana con disponibilidad real: {op.get('posta_origen_nombre', 'N/A')}."
    )
    st.write(
        "2. Supabase ordena las postas por distancia; si la más cercana no tiene ambulancias libres, se usa la siguiente."
    )
    st.write(
        f"3. El destino se eligió por severidad y distancia: {op.get('posta_destino_nombre', 'N/A')}."
    )
    st.write(
        "4. Si registras un segundo incidente cercano, las ambulancias ya ocupadas siguen ocupadas en Supabase y el despacho omite esa posta."
    )
    st.write(
        "5. El siguiente caso puede salir desde la segunda posta más cercana disponible."
    )
