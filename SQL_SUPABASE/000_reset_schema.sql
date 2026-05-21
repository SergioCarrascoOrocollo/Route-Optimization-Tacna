-- Reset limpio para Supabase antes de aplicar el schema SEM
-- Ejecutar solo si quieres borrar el esquema anterior y empezar de cero.

DROP TABLE IF EXISTS incident_logs CASCADE;
DROP TABLE IF EXISTS kpi_diarios CASCADE;
DROP TABLE IF EXISTS rutas_historicas CASCADE;
DROP TABLE IF EXISTS rutas CASCADE;
DROP TABLE IF EXISTS incidentes CASCADE;
DROP TABLE IF EXISTS ambulancias CASCADE;
DROP TABLE IF EXISTS semaforos CASCADE;
DROP TABLE IF EXISTS zonas_congestion CASCADE;
DROP TABLE IF EXISTS postas_medicas CASCADE;

-- Opcional: limpiar extensiones si el proyecto se recrea completamente.
-- No se eliminan por defecto porque pueden estar siendo usadas por otros objetos.
