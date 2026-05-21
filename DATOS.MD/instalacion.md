# NavExpert Pro

Aplicación web en Streamlit para optimización de rutas (TSP) sobre red vial real de Tacna, Perú.

## 1) Requisitos mínimos del sistema

- Windows 10/11
- Conexión a internet (necesaria para reconstruir el grafo desde OpenStreetMap)
- Al menos 4 GB RAM recomendados

## 2) Instalar herramientas base

Instala en este orden:

1. Python 3.10 o superior
2. Git
3. Visual Studio Code (opcional, recomendado)

## 3) Verificar instalación de herramientas

Abre PowerShell y ejecuta:

```powershell
python --version
pip --version
git --version
```

Si `python` no aparece, reinicia terminal/PC y confirma que Python esté en PATH.

## 4) Obtener el proyecto

Si lo clonas desde Git:

```powershell
git clone https://github.com/SergioCarrascoOrocollo/Route-Optimization-Tacna
Set-Location Proyecto-SE
```

Si ya lo tienes descargado, entra a la carpeta raíz del proyecto:

```powershell
Set-Location C:\Users\sergi\Downloads\route-optimization-main\Proyecto-SE
```

## 5) Crear y activar entorno virtual

Crear entorno:

```powershell
python -m venv .venv
```

Si falla por versión específica, usa:

```powershell
py -3.10 -m venv .venv
```

Activar entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 6) Instalar dependencias del proyecto

Con el entorno activo:

```powershell
python -m pip install --upgrade pip
python -m pip install .
```

Modo desarrollo (editable):

```powershell
python -m pip install -e .
```

## 7) Comprobar que todo quedó conectado

### 7.1 Comprobar importaciones clave

```powershell
python -c "import streamlit, osmnx, networkx, folium, ortools; print('OK imports')"
```

### 7.2 Comprobar que se usa el Python del entorno

```powershell
python -c "import sys; print(sys.executable)"
```

Debe apuntar a `.venv\Scripts\python.exe`.

### 7.3 Comprobar que Streamlit está disponible

```powershell
python -m streamlit --version
```

## 8) Ejecutar la aplicación

Siempre recomendado con el Python del entorno:

```powershell
python -m streamlit run src/app.py
```

Alternativa equivalente:

```powershell
.\.venv\Scripts\streamlit.exe run src/app.py
```

## 9) Primer arranque y caché del grafo

El motor usa `src/tacna_provincia.graphml` como caché principal.

- Si el archivo ya existe y tiene cobertura grande, se carga directamente.
- Si falta o se detecta demasiado pequeño, `src/engine.py` reconstruye el grafo con OSMnx.
- La reconstrucción puede tardar bastante y depende de disponibilidad de servidores Overpass.

## 10) Verificar cobertura del grafo (opcional pero recomendado)

```powershell
python -c "import os, osmnx as ox; G=ox.load_graphml('src/tacna_provincia.graphml'); xs=[float(d['x']) for _,d in G.nodes(data=True) if 'x' in d]; ys=[float(d['y']) for _,d in G.nodes(data=True) if 'y' in d]; print('nodes', G.number_of_nodes()); print('edges', G.number_of_edges()); print('bbox', (min(xs), min(ys), max(xs), max(ys))); print('size_bytes', os.path.getsize('src/tacna_provincia.graphml'))"
```

Referencia de cobertura provincial ya validada en este entorno:

- nodes: 30631
- edges: 87026
- bbox: (-71.0503845, -18.7751427, -69.4461781, -17.249585)

## 11) Uso básico de la app

1. Haz clic en el mapa para agregar puntos.
2. Los marcadores son fijos (no arrastrables).
3. Pulsa CALCULAR RUTA.
4. Revisa distancia total, tiempo y tramos.
5. Activa "Mostrar explicación paso a paso" para ver tablas de decisión.

## 12) Solución de problemas frecuentes

### Problema: `streamlit` no se reconoce

Causa: entorno virtual no activo o instalación incompleta.

Solución:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install .
python -m streamlit run src/app.py
```

### Problema: se queda en "Running" mucho tiempo en primer arranque

Causa: reconstrucción del grafo en segundo plano.

Solución:

- Esperar a que termine.
- Verificar conectividad internet.
- Reintentar ejecución manteniendo `.venv` activo.

### Problema: errores de Overpass/OpenStreetMap

Causa: saturación o timeout del endpoint.

Solución:

- Reintentar luego.
- Mantener el archivo `src/tacna_provincia.graphml` una vez generado para evitar reconstrucciones frecuentes.

## 13) Estructura relevante actual

```text
Proyecto-SE/
├── pyproject.toml
├── DATOS.MD/
│   ├── README.md
│   └── contexto.md
├── SQL_SUPABASE/
└── src/
    ├── app.py
    ├── engine.py
    └── tacna_provincia.graphml
```