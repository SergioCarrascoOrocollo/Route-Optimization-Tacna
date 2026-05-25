-- SQL 004: políticas y permisos opcionales para usar el cliente con `anon`
--
-- IMPORTANTE:
-- - Si tu app local usa `SUPABASE_SERVICE_KEY`, NO necesitas ejecutar este script.
-- - Si quieres usar `SUPABASE_ANON_KEY` desde el cliente, entonces sí debes aplicar
--   estas políticas. Este script deja el acceso amplio para una demo/control local.

BEGIN;

-- ----------------------------------------------------------------------------
-- Permisos básicos de esquema
-- ----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Tabla: incidentes
-- ----------------------------------------------------------------------------
ALTER TABLE public.incidentes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS incidentes_select_anon ON public.incidentes;
DROP POLICY IF EXISTS incidentes_insert_anon ON public.incidentes;
DROP POLICY IF EXISTS incidentes_update_anon ON public.incidentes;

CREATE POLICY incidentes_select_anon
ON public.incidentes
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY incidentes_insert_anon
ON public.incidentes
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

CREATE POLICY incidentes_update_anon
ON public.incidentes
FOR UPDATE
TO anon, authenticated
USING (true)
WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.incidentes TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Tabla: ambulancias
-- ----------------------------------------------------------------------------
ALTER TABLE public.ambulancias ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ambulancias_select_anon ON public.ambulancias;
DROP POLICY IF EXISTS ambulancias_update_anon ON public.ambulancias;

CREATE POLICY ambulancias_select_anon
ON public.ambulancias
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY ambulancias_update_anon
ON public.ambulancias
FOR UPDATE
TO anon, authenticated
USING (true)
WITH CHECK (true);

GRANT SELECT, UPDATE ON public.ambulancias TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Tabla: postas_medicas
-- ----------------------------------------------------------------------------
ALTER TABLE public.postas_medicas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS postas_select_anon ON public.postas_medicas;

CREATE POLICY postas_select_anon
ON public.postas_medicas
FOR SELECT
TO anon, authenticated
USING (true);

GRANT SELECT ON public.postas_medicas TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Tabla: rutas
-- ----------------------------------------------------------------------------
ALTER TABLE public.rutas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rutas_select_anon ON public.rutas;
DROP POLICY IF EXISTS rutas_insert_anon ON public.rutas;

CREATE POLICY rutas_select_anon
ON public.rutas
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY rutas_insert_anon
ON public.rutas
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.rutas TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Tablas de referencia / lectura
-- ----------------------------------------------------------------------------
ALTER TABLE public.semaforos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zonas_congestion ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS semaforos_select_anon ON public.semaforos;
DROP POLICY IF EXISTS zonas_select_anon ON public.zonas_congestion;

CREATE POLICY semaforos_select_anon
ON public.semaforos
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY zonas_select_anon
ON public.zonas_congestion
FOR SELECT
TO anon, authenticated
USING (true);

GRANT SELECT ON public.semaforos TO anon, authenticated;
GRANT SELECT ON public.zonas_congestion TO anon, authenticated;

-- ----------------------------------------------------------------------------
-- Funciones: permitir ejecución desde anon/authenticated
-- ----------------------------------------------------------------------------
ALTER FUNCTION public.obtener_postas_cercanas(numeric, numeric, numeric) SECURITY DEFINER;
ALTER FUNCTION public.obtener_posta_destino_optima(numeric, numeric, varchar) SECURITY DEFINER;
ALTER FUNCTION public.despachar_incidente(uuid) SECURITY DEFINER;
ALTER FUNCTION public.registrar_retorno_ambulancia(uuid, uuid) SECURITY DEFINER;
ALTER FUNCTION public.estimar_trafico_ruta(jsonb) SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.obtener_postas_cercanas(numeric, numeric, numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.obtener_posta_destino_optima(numeric, numeric, varchar) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.despachar_incidente(uuid) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.registrar_retorno_ambulancia(uuid, uuid) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.estimar_trafico_ruta(jsonb) TO anon, authenticated;

COMMIT;
