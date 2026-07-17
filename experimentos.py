"""
experimentos.py
================
Script de diseño experimental para el artículo científico.

Ejecuta el agente de Recocido Simulado sobre casos de prueba reales
de la Provincia de Tacna y genera:
  - resultados/tabla_experimentos.csv  → tabla para el paper
  - resultados/figura_convergencia.png → curva de convergencia SA
  - resultados/figura_comparacion.png  → SA vs Greedy por caso
  - resultados/figura_tiempos.png      → tiempo de ejecución por caso

Uso:
    python experimentos.py
"""

import sys
import os
import time
import csv
import math
import random
from pathlib import Path

# Ajustar path para importar src/engine.py
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import engine  # noqa: E402

# ── Casos de prueba reales de la Provincia de Tacna ───────────────────────────
CASOS = [
    # GRAVES (3+ puntos)
    {
        "id": "Grave-1",
        "tipo": "Grave",
        "descripcion": "Accidente vial - Av. Bolognesi (3 puntos)",
        "puntos": [
            (-18.0165, -70.2541),   # Posta: C.S. Metropolitano
            (-18.0145, -70.2511),   # Incidente: Paseo Civico
            (-18.0065, -70.2465),   # Destino: H. Hipolito Unanue
        ],
    },
    {
        "id": "Grave-2",
        "tipo": "Grave",
        "descripcion": "Emergencia cardiaca - Zona Alto Lima (4 puntos)",
        "puntos": [
            (-18.0132, -70.2488),   # Posta: C.S. Ciudad Nueva
            (-18.0198, -70.2552),   # Incidente: Mercado Central
            (-18.0073, -70.2470),   # Destino 1: H. Hipolito Unanue
            (-18.0110, -70.2430),   # Destino 2: Clinica Solidaridad
        ],
    },
    {
        "id": "Grave-3",
        "tipo": "Grave",
        "descripcion": "Politraumatismo - Calana (5 puntos)",
        "puntos": [
            (-18.0205, -70.2610),   # Posta: C.S. Cono Norte
            (-17.9940, -70.2280),   # Incidente: Carretera Calana
            (-18.0065, -70.2465),   # Destino 1: H. Hipolito Unanue
            (-18.0132, -70.2488),   # Paso: C.S. Ciudad Nueva
            (-18.0090, -70.2510),   # Destino 2: EsSalud Tacna
        ],
    },
    # LEVES (2-3 puntos)
    {
        "id": "Leve-1",
        "tipo": "Leve",
        "descripcion": "Consulta domiciliaria - Centro Historico (2 puntos)",
        "puntos": [
            (-18.0165, -70.2541),   # Posta: C.S. Metropolitano
            (-18.0152, -70.2498),   # Destino: Calle Zela
        ],
    },
    {
        "id": "Leve-2",
        "tipo": "Leve",
        "descripcion": "Traslado menor - Pocollay (3 puntos)",
        "puntos": [
            (-18.0050, -70.2400),   # Posta: Pocollay
            (-18.0080, -70.2420),   # Incidente: Av. Tarapaca
            (-18.0065, -70.2465),   # Destino: H. Hipolito Unanue
        ],
    },
    {
        "id": "Leve-3",
        "tipo": "Leve",
        "descripcion": "Evaluacion rutinaria - Gregorio Albarracin (3 puntos)",
        "puntos": [
            (-18.0320, -70.2480),   # Posta: C.S. Gregorio Albarracin
            (-18.0280, -70.2460),   # Incidente: Mercado G.A.
            (-18.0065, -70.2465),   # Destino: H. Hipolito Unanue
        ],
    },
]


def _greedy_cost(matriz):
    """Calcula el costo greedy (vecino mas cercano) desde nodo 0 como linea base."""
    n = len(matriz)
    visited = {0}
    actual = 0
    costo = 0.0
    for _ in range(n - 1):
        candidatos = [(matriz[actual][j], j) for j in range(n) if j not in visited]
        if not candidatos:
            break
        costo_min, siguiente = min(candidatos)
        costo += costo_min
        visited.add(siguiente)
        actual = siguiente
    costo += matriz[actual][0]
    return costo


def ejecutar_experimentos():
    print("=" * 60)
    print("  EXPERIMENTOS - Recocido Simulado para Rutas de Emergencia")
    print("  Provincia de Tacna, Peru")
    print("=" * 60)

    print("\n[1/3] Cargando grafo vial de Tacna...")
    G = engine.get_graph()
    print(f"      Nodos: {G.number_of_nodes()}  |  Aristas: {G.number_of_edges()}\n")

    out_dir = ROOT / "resultados"
    out_dir.mkdir(exist_ok=True)

    resultados = []
    historiales = {}

    print("[2/3] Ejecutando casos de prueba...\n")

    import networkx as nx
    import numpy as np

    for caso in CASOS:
        cid = caso["id"]
        puntos = caso["puntos"]
        n_puntos = len(puntos)

        print(f"  > {cid}: {caso['descripcion']}")

        # Proyectar puntos en el grafo
        G_work = G.copy()
        n_ids = []
        for i, raw in enumerate(puntos):
            n_id = 990000 + i
            n_ids.append(engine._project_point_on_graph(G_work, raw, n_id))

        n = len(n_ids)
        matriz_t = np.zeros((n, n))
        matriz_d = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    try:
                        matriz_t[i][j] = nx.shortest_path_length(G_work, n_ids[i], n_ids[j], weight='travel_time')
                        matriz_d[i][j] = nx.shortest_path_length(G_work, n_ids[i], n_ids[j], weight='length')
                    except Exception:
                        matriz_t[i][j] = 1e7
                        matriz_d[i][j] = 1e7

        costo_greedy = _greedy_cost(matriz_t)

        # Ejecutar SA y medir tiempo
        t0 = time.perf_counter()
        agente = engine.AgenteRecocidoSimulado(
            matriz_costos=matriz_t,
            temp_inicial=5000.0,
            alfa=0.98,
            iteraciones_max=2000,
        )
        mejor_ruta, costo_sa, historial = agente.optimizar()
        t1 = time.perf_counter()

        tiempo_ms = (t1 - t0) * 1000
        iteraciones_reales = len(historial)
        mejora_pct = (costo_greedy - costo_sa) / costo_greedy * 100 if costo_greedy > 0 else 0

        dist_km = sum(
            matriz_d[mejor_ruta[i]][mejor_ruta[i + 1]]
            for i in range(len(mejor_ruta) - 1)
        ) / 1000

        historiales[cid] = historial

        fila = {
            "Caso": cid,
            "Tipo": caso["tipo"],
            "N_Puntos": n_puntos,
            "Costo_SA_seg": round(costo_sa, 2),
            "Costo_SA_min": round(costo_sa / 60, 2),
            "Costo_Greedy_seg": round(costo_greedy, 2),
            "Costo_Greedy_min": round(costo_greedy / 60, 2),
            "Mejora_pct": round(mejora_pct, 2),
            "Dist_km": round(dist_km, 3),
            "Tiempo_ejec_ms": round(tiempo_ms, 1),
            "Iteraciones": iteraciones_reales,
            "Descripcion": caso["descripcion"],
        }
        resultados.append(fila)

        print(f"    Costo SA: {costo_sa/60:.2f} min  |  Greedy: {costo_greedy/60:.2f} min  |  Mejora: {mejora_pct:.1f}%")
        print(f"    Dist: {dist_km:.3f} km  |  Tiempo ejec.: {tiempo_ms:.1f} ms  |  Iters: {iteraciones_reales}\n")

    # Guardar CSV
    csv_path = out_dir / "tabla_experimentos.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultados[0].keys())
        writer.writeheader()
        writer.writerows(resultados)
    print(f"[3/3] CSV guardado: {csv_path}")

    _generar_figuras(resultados, historiales, out_dir)

    print("\nExperimentos completados exitosamente.")
    print(f"Archivos en: {out_dir}/")
    return resultados


def _generar_figuras(resultados, historiales, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError:
        print("  [!] matplotlib no encontrado. Instala con: pip install matplotlib")
        return

    colores_tipo = {"Grave": "#e74c3c", "Leve": "#3498db"}
    ids = [r["Caso"] for r in resultados]

    # Figura 1: Curvas de convergencia — color distinto por caso
    colores_caso = [
        "#e74c3c", "#c0392b", "#922b21",   # Graves: rojos
        "#2980b9", "#1abc9c", "#8e44ad",   # Leves: distintos
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    casos_con_historial = [r for r in resultados if historiales.get(r["Caso"])]
    for idx, r in enumerate(casos_con_historial):
        h = historiales[r["Caso"]]
        ax.plot(
            [x / 60 for x in h],
            label=r["Caso"],
            color=colores_caso[idx % len(colores_caso)],
            linewidth=1.8,
            linestyle="--" if r["Tipo"] == "Leve" else "-",
        )
    ax.set_xlabel("Iteracion", fontsize=11)
    ax.set_ylabel("Costo mejor solucion (min)", fontsize=11)
    ax.set_title("Convergencia del Recocido Simulado - 6 Casos de Prueba", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, ncol=2, title="Caso (-- = Leve, — = Grave)")
    ax.grid(True, alpha=0.3)
    ax.text(0.99, 0.02, "Leve-1 omitido: caso trivial de 2 puntos (sin iteraciones)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="gray", style="italic")
    fig.tight_layout()
    p = out_dir / "figura_convergencia.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"   Figura: {p}")

    # Figura 2: Comparacion SA vs Greedy
    fig, ax = plt.subplots(figsize=(9, 5))
    x = list(range(len(ids)))
    w = 0.35
    sa_vals = [r["Costo_SA_min"] for r in resultados]
    gr_vals = [r["Costo_Greedy_min"] for r in resultados]
    bars1 = ax.bar([xi - w/2 for xi in x], sa_vals, w, label="Recocido Simulado (SA)", color="#2ecc71", edgecolor="white")
    bars2 = ax.bar([xi + w/2 for xi in x], gr_vals, w, label="Greedy (vecino mas cercano)", color="#95a5a6", edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(ids, fontsize=9)
    ax.set_ylabel("Costo total de ruta (min)", fontsize=11)
    ax.set_title("SA vs. Greedy - Costo Total por Caso", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    p = out_dir / "figura_comparacion.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"   Figura: {p}")

    # Figura 3: Tiempo de ejecucion
    fig, ax = plt.subplots(figsize=(8, 5))
    colores = [colores_tipo[r["Tipo"]] for r in resultados]
    tiempos = [r["Tiempo_ejec_ms"] for r in resultados]
    barras = ax.bar(ids, tiempos, color=colores, edgecolor="white")
    ax.set_ylabel("Tiempo de ejecucion (ms)", fontsize=11)
    ax.set_title("Tiempo de Ejecucion del Agente SA por Caso", fontsize=12, fontweight="bold")
    # Margen superior para que las etiquetas no se corten
    ax.set_ylim(0, max(tiempos) * 1.25 + 1)
    for bar, r in zip(barras, resultados):
        label = "trivial\n(2 pts)" if r["Tiempo_ejec_ms"] == 0.0 else f"{bar.get_height():.1f} ms"
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                label, ha="center", va="bottom", fontsize=8)
    ax.legend(handles=[
        Patch(color="#e74c3c", label="Grave"),
        Patch(color="#3498db", label="Leve"),
    ], fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    p = out_dir / "figura_tiempos.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"   Figura: {p}")


if __name__ == "__main__":
    ejecutar_experimentos()
