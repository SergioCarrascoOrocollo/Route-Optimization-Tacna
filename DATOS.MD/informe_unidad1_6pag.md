# Informe de Avance — Unidad 1 (Versión Extendida, ~6 páginas)

**Proyecto:** SISTEMA EXPERTO PARA LA OPTIMIZACIÓN DE RUTAS PARA EMERGENCIAS MÉDICAS EN LA CIUDAD DE TACNA

**Tipo de entrega:** Avance (Unidad 1)

**Integrantes:** (añadir nombres completos)

**Fecha:** 24/05/2026

---

## Resumen ejecutivo

Este documento presenta el avance de la Unidad 1 para el proyecto “Sistema experto para la optimización de rutas para emergencias médicas en la ciudad de Tacna”. Se propone un agente inteligente basado en búsqueda sobre un grafo vial, justifica la elección metodológica, describe el modelado y la arquitectura propuesta, y expone un caso de ejemplo que demuestra la funcionalidad parcial alcanzada. El alcance funcional actual considera 1 incidente por ambulancia y 1 paciente por ambulancia. Además se listan conclusiones preliminares y tareas para las siguientes unidades, incluyendo la evolución hacia escenarios multiincidente.

---

## 1. Introducción

La optimización del despacho y la navegación de unidades de emergencia es crítica para reducir tiempos de respuesta y salvar vidas. Este proyecto desarrolla un sistema experto que, a partir de la representación de la red vial de la Provincia de Tacna y datos de incidentes, calcula rutas óptimas para ambulancias y unidades de respuesta.

El objetivo de este avance es presentar la especificación conceptual del agente inteligente que realizará la optimización de rutas, demostrando su modelo, técnicas elegidas y un caso de ejemplo que muestre la solución parcial disponible al finalizar la Unidad 1.

---

## 2. Descripción del problema y contexto operativo

2.1 Alcance geográfico

El sistema abarca la Provincia de Tacna, integrando áreas urbanas y periurbanas. Los datos de red provienen de OpenStreetMap y se gestionan localmente mediante archivos caché (`src/tacna_provincia.graphml`).

2.2 Actores y roles

- Central de despacho: operador humano que reporta incidentes y solicita rutas.
- Conductores/paramédicos: ejecutan las rutas calculadas.
- Plataforma del sistema experto: recibe entrada (ubicación incidente, recursos) y devuelve rutas optimizadas.
- Administradores: mantienen la base de datos, cargas y parámetros.

2.3 Necesidades y restricciones

- Objetivo principal: minimizar el tiempo de respuesta hasta el primer contacto con la víctima.
- Restricciones operativas: sentidos únicos, cierres viales, velocidad variable, capacidad limitada de ambulancias.
- Requisitos no funcionales: robustez ante fallos de red (descarga de grafo), tiempos de cálculo razonables en condiciones reales.

---

## 3. Enfoque y tipo de agente propuesto

3.1 Enfoque seleccionado

Se propone un agente basado en búsqueda sobre grafos. En el diseño actual se trabaja con un modelo de red vial ponderada por tiempo de viaje, donde cada arista tiene un coste de `travel_time` y el agente selecciona caminos de costo mínimo entre puntos de interés. El proyecto se mantiene dentro del enfoque de agentes basados en búsqueda para resolver despacho y navegación de ambulancias.

3.2 Técnicas y herramientas

- OSMnx + NetworkX: modelado y manipulación de la red vial como grafo dirigido.
- Camino mínimo sobre coste temporal (`travel_time`): la técnica usada actualmente es búsqueda de ruta de menor costo en el grafo ponderado.
- OR-Tools (Routing): contemplado como evolución para escenarios multiincidente con asignación y ordenamiento de rutas.
- Supabase + SQL/RPC: para modelar el estado de incidentes, postas y ambulancias, y para aplicar regras operativas de despacho.
- Folium + Streamlit: visualización del mapa, interacción y presentación de resultados.

3.3 Justificación

- El problema requiere optimización sobre una red vial con costos métricos, lo que encaja naturalmente en un agente de búsqueda en grafos.
- La representación de costos en aristas permite comparar tiempos de viaje y seleccionar la ruta de menor costo.
- El enfoque de búsqueda es apropiado para la fase actual, que considera un incidente y una ambulancia por corrida.
- La elección de búsqueda sobre grafos tiene sentido frente a un enfoque puramente lógico, porque aquí se evalúan distancias y tiempos continuos en una red espacial.

---

## 4. Modelado del agente (especificación técnica)

4.1 Representación del entorno

El entorno se modela como el grafo dirigido G=(V,E) asociado a la red vial de Tacna. Cada arista E(u,v) contiene atributos de `length` (metros), `speed_kph` (velocidad estimada) y `travel_time` (segundos). Las coordenadas geográficas de cada nodo permiten proyectar ubicaciones de origen, incidente y destino médico.

4.2 Estado inicial y objetivo

- Estado inicial: ubicación de una posta o ambulancia y un único incidente activo en la red.
- Estado objetivo actual: llegar al incidente y, en la fase operativa, continuar hacia el establecimiento de salud más adecuado.
- Estado objetivo futuro: gestionar múltiples incidentes y unidades minimizando tiempo global y priorizando gravedad.

4.3 Acciones y transición

- Acción: avanzar por una arista conectada al nodo actual.
- Transición: mover el estado al nodo siguiente y sumar el costo `travel_time` de la arista.

4.4 Función de costo y criterio de optimización

- Costo de arista: `travel_time`, calculado actualmente a partir de una velocidad base de 30 km/h y una penalización por curva en tramos sinuosos.
- Objetivo: minimizar el tiempo total de la ruta.
- En el modelo operativo actual se considera un ciclo de tres tramos: posta → incidente, incidente → destino y destino → posta.

4.5 Heurística para búsqueda

En la propuesta conceptual se usa una heurística admisible basada en distancia euclidiana dividida por una velocidad máxima teórica. En la implementación actual, el criterio práctico es peso de `travel_time` en el grafo ponderado.

4.6 Representación actual y evolución a TSP/VRP

- Estado actual: origen de ambulancia + incidente + destino médico, con un único incidente activo.
- Evolución: origen + varios incidentes + destinos médicos, con asignación de unidades y ordenación de rutas.
- Para la evolución se contempla calcular matrices O-D de tiempos mínimos usando `nx.shortest_path_length` con peso `travel_time` y resolver el problema con OR-Tools.

4.7 Reglas operativas y restricciones adicionales

- Respetar sentidos únicos y condiciones de la red vial.
- Priorizar hospitales para incidentes graves y postas/clínicas para incidentes leves.
- Considerar la disponibilidad de ambulancias y el estado actual de despacho almacenado en Supabase.

---

## 5. Funcionamiento y arquitectura del sistema

5.1 Componentes y responsabilidades

- Capa de datos: descarga y cache del grafo provincial (`src/tacna_provincia.graphml`) y estado operativo en Supabase para incidentes, postas y ambulancias.
- Módulo de grafo (`src/engine.py`): carga del grafo, proyección de coordenadas del incidente y cálculo de rutas con costo `travel_time`.
- Lógica de despacho: RPC/SQL en Supabase para seleccionar posta de origen, destino médico y registrar estados de ambulancias e incidentes.
- Interfaz (`src/app.py`): Streamlit + Folium para interacción, dibujo de rutas y presentación de tablas con resultados.

5.2 Flujo de datos (resumido)

1. Entrada: se registra un incidente único mediante clic en el mapa y se define la gravedad.
2. Capa de datos: el agente consulta Supabase para obtener postas cercanas y candidatos a destino médico.
3. Proyección y modelado: se proyectan las coordenadas de la posta, el incidente y el destino sobre el grafo vial.
4. Cálculo de costos: se computa `travel_time` sobre cada tramo de la ruta considerando velocidad base y penalización por curvas.
5. Optimización: se selecciona la ruta de menor costo en el grafo ponderado.
6. Salida: el sistema muestra el recorrido en el mapa y tablas con tiempos, distancias y candidatos.

En la evolución multiincidente, el flujo añadirá asignación de incidentes a diferentes unidades, selección de destino con reglas de gravedad y optimización de varias rutas en un mismo mapa.

5.3 Pseudocódigo del comportamiento del agente

```
función calcular_ruta_operativa(origen_posta, incidente, destino_medico):
    nodo_origen = proyectar(origen_posta)
    nodo_incidente = proyectar(incidente)
    nodo_destino = proyectar(destino_medico)
    tramo_a = ruta_minima(nodo_origen, nodo_incidente, peso='travel_time')
    tramo_b = ruta_minima(nodo_incidente, nodo_destino, peso='travel_time')
    tramo_c = ruta_minima(nodo_destino, nodo_origen, peso='travel_time')
    retornar {tramo_a, tramo_b, tramo_c, tiempo_total, distancia_total}
```

```
función seleccionar_destino_por_gravedad(postas_cercanas, candidatos, gravedad):
    si gravedad == 'grave':
        escoger el hospital más cercano entre candidatos
    sino:
        escoger la posta o clínica más cercana disponible
    retornar destino_seleccionado
```

---

## 6. Caso de ejemplo (demostración de avance)

6.1 Datos concretos de ejemplo (simulados)

- Origen (Ambulancia A): -18.012345, -70.253210
- Incidente único: -18.013500, -70.247800
- Gravedad del incidente: grave

6.2 Proceso (ejecución real parcial con la implementación actual)

1. Un incidente se coloca en el mapa y se define su gravedad.
2. El sistema consulta Supabase para obtener la posta de origen y candidatos de destino médico.
3. Se proyectan las ubicaciones de posta, incidente y destino sobre el grafo vial.
4. Se calcula el tiempo de viaje de cada tramo usando `travel_time` con velocidad base de 30 km/h y penalización por curvas.
5. Se selecciona la ruta operativa de menor costo y se dibuja en el mapa.
6. Se presenta el resultado en tablas: postas cercanas, candidatos de destino y tiempos/distancias de cada tramo.

6.3 Resultados esperados y métricas mostradas

- Ruta operativa en el mapa con los tres tramos: posta → incidente → destino → posta.
- Tiempos estimados de cada tramo y tiempo total.
- Distancias de cada tramo y distancia total.
- Visualización de candidatos a destino y postas cercanas para justificar la decisión.

6.4 Observaciones prácticas del avance

- La generación del grafo provincial requiere descarga OSM y puede tardar; el sistema implementa caché en `src/tacna_provincia.graphml`.
- Se solucionaron problemas de tiempo de espera a Overpass ajustando `ox.settings.requests_timeout`.

---

## 7. Conclusiones preliminares y trabajo pendiente

7.1 Conclusiones

- El modelo basado en búsqueda es apropiado y ya se dispone de una implementación parcial funcional para cálculo de rutas y trazas.
- El alcance actual queda claramente definido como 1 incidente por ambulancia y 1 paciente por ambulancia, permitiendo validar la base técnica con menor complejidad.
- La evolución prevista mantiene coherencia: multiincidente, asignación por cercanía/disponibilidad y derivación por gravedad clínica.

7.2 Trabajo pendiente (priorizado)

- Mantener la orientación conceptual del informe, sin depender de la implementación, pero validar con pruebas de concepto.
- Refinar el modelo de destino para incidentes graves: priorizar hospitales más cercanos y revisar reglas de negocio en Supabase.
- Extender a multiincidente: asignación de incidentes a varias ambulancias y cálculo de rutas concurrentes.
- Mejorar la interfaz de resultados con tablas de decisión y explicaciones operativas claras.
- Explorar el uso de datos dinámicos (tráfico, cortes) y de heurísticas más precisas en el grafo.
- Preparar la versión final del informe con portada, integrantes y formato solicitado.

---

## 8. Referencias bibliográficas

- Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A Formal Basis for the Heuristic Determination of Minimum Cost Paths.
- Google OR-Tools. https://developers.google.com/optimization
- OSMnx documentation. https://osmnx.readthedocs.io
- NetworkX documentation. https://networkx.org
