# 🚗 Optimización de Rutas con Python

Este proyecto implementa un sistema de optimización de rutas utilizando el Problema del Vendedor Viajero (TSP) con datos reales de OpenStreetMap. El sistema encuentra la ruta más eficiente para visitar múltiples puntos de interés en una ciudad, visualizando los resultados en mapas interactivos.

## 🌟 Características

- **Optimización de Rutas**: Resuelve el TSP utilizando Google OR-Tools
- **Mapas Interactivos**: Visualización con Folium y OpenStreetMap
- **Datos Reales**: Utiliza OSMnx para obtener redes viales reales
- **Análisis de Distancias**: Calcula rutas óptimas basadas en distancias reales
- **Jupyter Notebooks**: Análisis interactivo y visualizaciones

## 📦 Tecnologías Utilizadas

- **Python 3.10+**
- **UV** - Gestor de paquetes y entornos virtuales
- **OSMnx** - Análisis de redes de OpenStreetMap
- **OR-Tools** - Optimización y resolución del TSP
- **Folium** - Mapas interactivos
- **NetworkX** - Análisis de grafos
- **NumPy & Pandas** - Manipulación de datos
- **Matplotlib** - Visualizaciones

## 🚀 Instalación y Configuración

### Prerrequisitos

1. **Python 3.10 o superior**
2. **UV** - Si no lo tienes instalado:

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Instalación del Proyecto

1. **Clona o descarga el proyecto**:
```bash
git clone <url-del-repositorio>
cd route-optimization
```

2. **Instala las dependencias con UV**:
```bash
# Instalar dependencias del proyecto
uv sync

# Instalar dependencias de desarrollo (incluye Jupyter)
uv sync --group dev
```

3. **Activa el entorno virtual**:
```bash
# Activar el entorno virtual
uv shell
```

## 🎯 Uso del Proyecto

### Opción 1: Jupyter Notebook (Recomendado)

1. **Inicia Jupyter Notebook**:
```bash
uv run jupyter notebook
```

2. **Abre el notebook principal**:
   - Navega a `src/route_optim.ipynb`
   - Ejecuta las celdas secuencialmente

### Opción 2: Script Python

```bash
# Ejecutar el script principal
uv run python main.py
```

### Opción 3: Ejecución directa con UV

```bash
# Ejecutar el notebook desde la línea de comandos
uv run jupyter nbconvert --to notebook --execute src/route_optim.ipynb
```

## 📊 Estructura del Proyecto

```
route-optimization/
├── main.py                    # Script principal
├── pyproject.toml             # Configuración del proyecto y dependencias
├── uv.lock                    # Archivo de bloqueo de dependencias
├── README.md                  # Este archivo
└── src/
    ├── route_optim.ipynb      # Notebook principal de optimización
    ├── route_optimization.ipynb # Notebook alternativo
    ├── data_stores.csv        # Datos de tiendas (ejemplo)
    └── cache/                 # Cache de datos de OSM
        ├── *.json            # Archivos de cache
```

## 🔧 Funcionalidades Principales

### 1. Carga de Red Vial
```python
# Cargar la red vial de una ubicación específica
center_point = [-18.027808, -70.251069]  # Tacna, Perú
G = ox.graph_from_point(center_point, dist=10000, network_type="drive")
```

### 2. Definición de Puntos de Interés
```python
puntos = [
    (-18.025947, -70.251223), # Punto inicial (Puerta de la U Av. Cusco)
    (-18.018047, -70.253128), # Plaza Vea
    (-18.013997, -70.248859), # DM Hotel
    (-18.013682, -70.250590), # Arco parabólico
    (-18.016574, -70.252357), # Ferrocarril
    (-18.013078, -70.254401), # Museo Ferroviario
]
```

### 3. Optimización de Ruta
El sistema:
- Calcula la matriz de distancias entre todos los puntos
- Resuelve el TSP usando Google OR-Tools
- Encuentra la ruta más eficiente
- Visualiza el resultado en un mapa interactivo

## 🗺️ Ejemplo de Uso

El notebook incluye un ejemplo completo que:

1. **Carga la red vial** de Tacna, Perú
2. **Define 6 puntos de interés** turísticos
3. **Calcula la ruta óptima** para visitarlos todos
4. **Visualiza el resultado** en un mapa interactivo con Folium

## 📈 Resultados

El sistema genera:
- **Mapa interactivo** con la ruta optimizada
- **Secuencia óptima** de visita de puntos
- **Distancia total** de la ruta
- **Visualización de la red vial** utilizada

## 🛠️ Comandos Útiles con UV

```bash
# Verificar instalación de UV
uv --version

# Sincronizar dependencias
uv sync

# Agregar nueva dependencia
uv add <nombre-paquete>

# Remover dependencia
uv remove <nombre-paquete>

# Actualizar dependencias
uv sync --upgrade

# Ejecutar comandos en el entorno
uv run <comando>

# Activar shell del entorno
uv shell

# Ver dependencias instaladas
uv pip list
```

## 🔍 Personalización

Para usar el proyecto con tus propios datos:

1. **Modifica las coordenadas** en `puntos` dentro del notebook
2. **Ajusta el punto central** en `center_point`
3. **Modifica la distancia** en el parámetro `dist` según el área de interés
4. **Cambia el tipo de red** en `network_type` (drive, walk, bike)

## 📝 Notas Importantes

- **Conexión a Internet**: Requerida para descargar datos de OpenStreetMap
- **Cache**: Los datos de OSM se guardan en `src/cache/` para uso futuro
- **Rendimiento**: Áreas muy grandes pueden tardar en procesarse
- **Compatibilidad**: Probado en Windows, macOS y Linux

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📞 Soporte

Si tienes problemas o preguntas:

1. Revisa que UV esté instalado correctamente
2. Verifica que todas las dependencias estén instaladas
3. Asegúrate de tener conexión a Internet para OSM
4. Abre un issue en el repositorio para problemas específicos

---

**¡Disfruta optimizando rutas! 🚗📍**