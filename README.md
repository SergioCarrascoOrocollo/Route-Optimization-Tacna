# 🚑 Optimización de Rutas de Emergencia Médica — Provincia de Tacna

**Agente inteligente basado en Recocido Simulado (Simulated Annealing) sobre grafos viales reales.**

> Proyecto de Sistemas Expertos — Universidad Nacional Jorge Basadre Grohmann  
> Escuela Profesional de Ingeniería en Informática y Sistemas

---

## 📋 Descripción

Este sistema implementa un agente de IA que optimiza el ciclo operativo de ambulancias en la Provincia de Tacna:

```
Posta de salud → Lugar del incidente → Destino médico
```

El agente utiliza la metaheurística de **Recocido Simulado (SA)** para encontrar el orden óptimo de paradas minimizando el tiempo total de viaje sobre la red vial real de Tacna (30,668 nodos / 87,109 aristas extraída de OpenStreetMap).

### Resultados obtenidos

| Caso    | SA (min) | Greedy (min) | Mejora |
| ------- | -------- | ------------ | ------ |
| Grave-1 | 11.45    | 22.89        | 50.0%  |
| Grave-2 | 23.74    | 34.96        | 32.1%  |
| Grave-3 | 36.07    | 64.86        | 44.4%  |
| Leve-1  | 3.53     | 8.71         | 59.4%  |
| Leve-2  | 9.45     | 14.35        | 34.1%  |
| Leve-3  | 22.43    | 44.80        | 49.9%  |

**Mejora promedio: 45.0% | Tiempo de ejecución: < 5 ms por caso**

---

## 🛠️ Instalación

### Requisitos previos

- Python 3.12 o superior
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes recomendado) o pip

### Opción A — Con `uv` (recomendado)

```bash
# Clonar el repositorio
git clone <url-del-repositorio>
cd Route-Optimization-Tacna

# Instalar dependencias automáticamente desde uv.lock
uv sync
```

### Opción B — Con `pip`

```bash
# Clonar el repositorio
git clone <url-del-repositorio>
cd Route-Optimization-Tacna

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

# Instalar dependencias
pip install streamlit osmnx networkx numpy shapely folium supabase python-dotenv matplotlib
```

### Dependencias principales

| Librería     | Versión | Propósito                                        |
| ------------ | ------- | ------------------------------------------------ |
| `streamlit`  | ≥ 1.56  | Interfaz web interactiva                         |
| `osmnx`      | ≥ 2.0   | Extracción del grafo vial de OpenStreetMap       |
| `networkx`   | ≥ 3.4   | Cálculo de rutas mínimas (Dijkstra)              |
| `numpy`      | ≥ 2.0   | Matrices de costos                               |
| `shapely`    | ≥ 2.0   | Geometría vial (proyección de puntos en aristas) |
| `folium`     | ≥ 0.19  | Visualización cartográfica                       |
| `supabase`   | ≥ 2.0   | Base de datos en tiempo real                     |
| `matplotlib` | ≥ 3.9   | Gráficos de convergencia y resultados            |

---

## ⚙️ Configuración

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-anon-key-aqui
```

> ⚠️ **Nunca subas el `.env` al repositorio.** Ya está en `.gitignore`.

---

## 🚀 Ejecución

### Interfaz web (aplicación principal)

```bash
# Con uv
uv run streamlit run src/app.py

# Con pip
streamlit run src/app.py
```

La aplicación se abrirá en `http://localhost:8501`

### Experimentos (reproduce los resultados del artículo)

```bash
# Con uv
uv run python experimentos.py

# Con pip
python experimentos.py
```

Genera en `resultados/`:

- `tabla_experimentos.csv` — Datos numéricos completos
- `figura_convergencia.png` — Curvas de convergencia SA
- `figura_comparacion.png` — SA vs Greedy por caso
- `figura_tiempos.png` — Tiempos de ejecución

---

## 📁 Estructura del Proyecto

```
Route-Optimization-Tacna/
├── src/
│   ├── engine.py           # Motor principal: agente SA + grafo vial
│   ├── app.py              # Interfaz web Streamlit
│   ├── app_helpers.py      # Helpers de la interfaz
│   ├── db_helpers.py       # Conexión y operaciones con Supabase
│   ├── geo_utils.py        # Utilidades geoespaciales
│   └── tacna_provincia.graphml  # Grafo vial (generado automáticamente)
├── experimentos.py         # Script de benchmarking
├── resultados/             # Figuras y tablas generadas
├── SQL_SUPABASE/           # Scripts SQL de la base de datos
├── DATOS.MD/               # Documentación de los datos utilizados
├── pyproject.toml          # Configuración del proyecto
├── .env                    # Variables de entorno (no en git)
└── README.md               # Este archivo
```

---

## 📊 Datos Utilizados

### Red vial

- **Fuente:** [OpenStreetMap](https://www.openstreetmap.org) vía OSMnx
- **Cobertura:** Provincia de Tacna, Perú (radio ~85 km desde el centro)
- **Formato:** GraphML (`src/tacna_provincia.graphml`, ~49 MB)
- **Nodos:** 30,668 intersecciones viales
- **Aristas:** 87,109 tramos con atributos `length`, `speed_kph`, `travel_time`
- **Nota:** El grafo se genera automáticamente la primera vez que se ejecuta la app si no existe el archivo `.graphml`

### Establecimientos de salud

- **Fuente:** Directorio MINSA 2024 — Región Tacna
- **Contenido:** Postas de salud, centros de salud y hospitales con coordenadas GPS
- **Almacenamiento:** Base de datos Supabase (tabla `postas`)
- **Hospital de referencia para emergencias graves:** Hospital Hipólito Unanue de Tacna

### Casos de prueba

- **6 escenarios** definidos con coordenadas GPS reales de Tacna
- **3 de gravedad alta** (3–5 paradas): derivación al Hospital Hipólito Unanue
- **3 de gravedad leve** (2–3 paradas): derivación a postas periféricas
- Los casos se definen en `experimentos.py` y son reproducibles

---

## 🧠 Arquitectura del Agente SA

El agente (`AgenteRecocidoSimulado` en `src/engine.py`) opera con los siguientes parámetros:

| Parámetro          | Valor    | Descripción                                  |
| ------------------ | -------- | -------------------------------------------- |
| `temp_inicial`     | 5000.0   | Temperatura inicial (alta = más exploración) |
| `alfa`             | 0.98     | Factor de enfriamiento geométrico            |
| `iteraciones_max`  | 2000     | Máximo de iteraciones                        |
| Criterio de parada | T ≤ 0.01 | Temperatura mínima (convergencia)            |

**Función de aceptación (criterio de Metropolis):**

```
P(aceptar) = 1.0              si ΔC < 0  (mejora)
P(aceptar) = exp(-ΔC / T)     si ΔC ≥ 0  (empeoramiento)
```

---

## 👥 Autores

| Nombre                           | Contribución                                               |
| -------------------------------- | ---------------------------------------------------------- |
| Angel Santiago Cruz Pari         | Base de datos Supabase (tablas, funciones, procedimientos) |
| Diego Emanuel Chambi Centeno     | Datos geoespaciales (postas, semáforos, hospitales)        |
| Bryanna Audrey Chavez Bautista   | Diseño inicial del sistema y lógica de despacho            |
| Sergio Gabriel Carrasco Orocollo | Integración de módulos y conexión del sistema              |

---

## 📄 Licencia

Uso académico — Universidad Nacional Jorge Basadre Grohmann, 2026.
