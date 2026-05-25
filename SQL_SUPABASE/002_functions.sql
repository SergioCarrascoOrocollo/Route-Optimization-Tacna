-- Migración 2: lógica de negocio en BD para SEM
-- Objetivo: mover despacho, capacidad, semáforos y congestión a PostgreSQL/Supabase.

BEGIN;

-- ============================================================================
-- AJUSTE DE ESQUEMA: permitir estado sin_recursos en incidentes
-- ============================================================================
ALTER TABLE incidentes
    DROP CONSTRAINT IF EXISTS incidentes_estado_check;

ALTER TABLE incidentes
    ADD CONSTRAINT incidentes_estado_check
    CHECK (estado IN ('reportado', 'sin_recursos', 'en_transporte', 'en_posta', 'cerrado'));

-- ============================================================================
-- TRIGGERS DE TIMESTAMP
-- ============================================================================
CREATE OR REPLACE FUNCTION public.fn_touch_timestamps()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME IN ('postas_medicas', 'ambulancias', 'incidentes') THEN
            NEW.updated_at = NOW();
        END IF;

        IF TG_TABLE_NAME = 'ambulancias' THEN
            NEW.ultima_actualizacion = NOW();
        ELSIF TG_TABLE_NAME = 'semaforos' THEN
            NEW.last_updated = NOW();
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_postas_touch_timestamps ON postas_medicas;
CREATE TRIGGER trg_postas_touch_timestamps
BEFORE UPDATE ON postas_medicas
FOR EACH ROW
EXECUTE FUNCTION public.fn_touch_timestamps();

DROP TRIGGER IF EXISTS trg_ambulancias_touch_timestamps ON ambulancias;
CREATE TRIGGER trg_ambulancias_touch_timestamps
BEFORE UPDATE ON ambulancias
FOR EACH ROW
EXECUTE FUNCTION public.fn_touch_timestamps();

DROP TRIGGER IF EXISTS trg_incidentes_touch_timestamps ON incidentes;
CREATE TRIGGER trg_incidentes_touch_timestamps
BEFORE UPDATE ON incidentes
FOR EACH ROW
EXECUTE FUNCTION public.fn_touch_timestamps();

DROP TRIGGER IF EXISTS trg_semaforos_touch_timestamps ON semaforos;
CREATE TRIGGER trg_semaforos_touch_timestamps
BEFORE UPDATE ON semaforos
FOR EACH ROW
EXECUTE FUNCTION public.fn_touch_timestamps();

-- ============================================================================
-- UTILIDADES GEOESPACIALES
-- ============================================================================
CREATE OR REPLACE FUNCTION public.fn_point_to_geom(punto point)
RETURNS geometry
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT ST_SetSRID(
        ST_MakePoint(
            split_part(trim(both '()' from punto::text), ',', 1)::double precision,
            split_part(trim(both '()' from punto::text), ',', 2)::double precision
        ),
        4326
    );
$$;

CREATE OR REPLACE FUNCTION public.fn_horarios_pico_activos(p_horarios jsonb)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM jsonb_array_elements(COALESCE(p_horarios, '[]'::jsonb)) AS horario
        WHERE CURRENT_TIME BETWEEN (horario->>'inicio')::time AND (horario->>'fin')::time
    );
$$;

-- ============================================================================
-- CAPACIDAD DE POSTA / AMBULANCIAS ACTIVAS
-- ============================================================================
CREATE OR REPLACE FUNCTION public.contar_ambulancias_activas_por_posta(p_posta_id uuid)
RETURNS integer
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::integer
    FROM ambulancias
    WHERE posta_base_id = p_posta_id
      AND estado IN ('en_ruta', 'ocupada');
$$;

CREATE OR REPLACE FUNCTION public.puede_despachar_desde_posta(p_posta_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT public.contar_ambulancias_activas_por_posta(p_posta_id) <
           COALESCE((SELECT capacidad_ambulancias FROM postas_medicas WHERE id = p_posta_id), 1);
$$;

CREATE OR REPLACE FUNCTION public.obtener_ambulancia_disponible_por_posta(p_posta_id uuid)
RETURNS TABLE(ambulancia_id uuid, codigo varchar)
LANGUAGE sql
STABLE
AS $$
    SELECT a.id, a.codigo
    FROM ambulancias a
    WHERE a.posta_base_id = p_posta_id
      AND a.estado = 'disponible'
    ORDER BY a.created_at ASC, a.id ASC
    LIMIT 1;
$$;

-- ============================================================================
-- POSTAS CERCANAS Y DESTINO ÓPTIMO
-- ============================================================================
CREATE OR REPLACE FUNCTION public.obtener_postas_cercanas(
    p_lat numeric,
    p_lon numeric,
    p_radio_km numeric DEFAULT 5
)
RETURNS TABLE(
    id uuid,
    nombre varchar,
    tipo varchar,
    latitud numeric,
    longitud numeric,
    capacidad_ambulancias integer,
    distancia_km numeric
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        p.id,
        p.nombre,
        p.tipo,
        p.latitud,
        p.longitud,
        p.capacidad_ambulancias,
        ROUND(
            (
                ST_DistanceSphere(
                    public.fn_point_to_geom(p.ubicacion),
                    ST_SetSRID(ST_MakePoint(p_lon::double precision, p_lat::double precision), 4326)
                ) / 1000.0
            )::numeric,
            2
        ) AS distancia_km
    FROM postas_medicas p
    WHERE ST_DWithin(
        public.fn_point_to_geom(p.ubicacion)::geography,
        ST_SetSRID(ST_MakePoint(p_lon::double precision, p_lat::double precision), 4326)::geography,
        p_radio_km * 1000.0
    )
    ORDER BY distancia_km ASC, p.nombre ASC;
$$;

CREATE OR REPLACE FUNCTION public.obtener_posta_destino_optima(
    p_lat numeric,
    p_lon numeric,
    p_tipo_incidente varchar
)
RETURNS TABLE(
    posta_id uuid,
    nombre varchar,
    tipo varchar,
    latitud numeric,
    longitud numeric,
    distancia_km numeric,
    prioridad integer
)
LANGUAGE sql
STABLE
AS $$
    WITH cercanas AS (
        SELECT *
        FROM public.obtener_postas_cercanas(p_lat, p_lon, 15)
    ),
    clasificadas AS (
        SELECT
            c.*,
            CASE
                WHEN p_tipo_incidente = 'menor' AND c.tipo = 'posta_basica' THEN 0
                WHEN p_tipo_incidente = 'menor' AND c.tipo = 'posta_avanzada' THEN 1
                WHEN p_tipo_incidente = 'mayor' AND c.tipo = 'hospital' THEN 0
                WHEN p_tipo_incidente = 'mayor' AND c.tipo = 'clinica' THEN 1
                ELSE 3
            END AS prioridad
        FROM cercanas c
    )
    SELECT
        c.id AS posta_id,
        c.nombre,
        c.tipo,
        c.latitud,
        c.longitud,
        c.distancia_km,
        c.prioridad
    FROM clasificadas c
    ORDER BY c.prioridad ASC, c.distancia_km ASC, c.nombre ASC
    LIMIT 1;
$$;

-- ============================================================================
-- DESPACHO ATÓMICO DE INCIDENTES
-- ============================================================================
CREATE OR REPLACE FUNCTION public.despachar_incidente(
    p_incidente_id uuid
)
RETURNS TABLE(
    ok boolean,
    mensaje text,
    ambulancia_id uuid,
    posta_destino_id uuid,
    posta_nombre varchar,
    distancia_km numeric
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_incidente incidentes%ROWTYPE;
    v_origen RECORD;
    v_destino RECORD;
    v_ambulancia RECORD;
    v_lat numeric;
    v_lon numeric;
BEGIN
    SELECT *
    INTO v_incidente
    FROM incidentes
    WHERE id = p_incidente_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Incidente no encontrado'::text, NULL::uuid, NULL::uuid, NULL::varchar, NULL::numeric;
        RETURN;
    END IF;

    IF v_incidente.estado = 'cerrado' THEN
        RETURN QUERY SELECT false, 'El incidente ya está cerrado'::text, NULL::uuid, NULL::uuid, NULL::varchar, NULL::numeric;
        RETURN;
    END IF;

    -- Extraer lat/lon desde el campo point (texto: '(lon,lat)')
    v_lon := split_part(trim(both '()' from v_incidente.ubicacion::text), ',', 1)::numeric;
    v_lat := split_part(trim(both '()' from v_incidente.ubicacion::text), ',', 2)::numeric;

    -- Obtener destino óptimo: la función espera (p_lat, p_lon, tipo)
    SELECT *
    INTO v_destino
    FROM public.obtener_posta_destino_optima(
        v_lat,
        v_lon,
        v_incidente.tipo
    );

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'No se encontró destino óptimo'::text, NULL::uuid, NULL::uuid, NULL::varchar, NULL::numeric;
        RETURN;
    END IF;

    -- Buscar postas cercanas: obtener_postas_cercanas espera (p_lat, p_lon, radio)
    FOR v_origen IN
        SELECT *
        FROM public.obtener_postas_cercanas(
            v_lat,
            v_lon,
            CASE WHEN v_incidente.tipo = 'mayor' THEN 10 ELSE 5 END
        )
    LOOP
        IF NOT public.puede_despachar_desde_posta(v_origen.id) THEN
            CONTINUE;
        END IF;

        SELECT a.id, a.codigo
        INTO v_ambulancia
        FROM ambulancias a
        WHERE a.posta_base_id = v_origen.id
          AND a.estado = 'disponible'
        ORDER BY a.created_at ASC, a.id ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED;

        IF FOUND THEN
            UPDATE ambulancias
            SET estado = 'en_ruta',
                ultima_actualizacion = NOW()
            WHERE id = v_ambulancia.id;

            UPDATE incidentes
            SET ambulancia_asignada_id = v_ambulancia.id,
                posta_destino_id = v_destino.posta_id,
                estado = 'en_transporte'
            WHERE id = p_incidente_id;

            RETURN QUERY SELECT
                true,
                'Despacho generado correctamente'::text,
                v_ambulancia.id,
                v_destino.posta_id,
                v_destino.nombre,
                v_destino.distancia_km;
            RETURN;
        END IF;
    END LOOP;

    UPDATE incidentes
    SET estado = 'sin_recursos'
    WHERE id = p_incidente_id;

    RETURN QUERY SELECT false, 'Sin ambulancias disponibles'::text, NULL::uuid, NULL::uuid, NULL::varchar, NULL::numeric;
END;
$$;

-- ============================================================================
-- ESTIMACIÓN DE TRÁFICO SOBRE UNA RUTA (JSONB)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.estimar_trafico_ruta(
    p_ruta_coords jsonb
)
RETURNS TABLE(
    semaforos_encontrados integer,
    tiempo_semaforos_seg integer,
    factor_congestion numeric,
    zonas_detectadas integer
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_semaforos integer := 0;
    v_tiempo_semaforos integer := 0;
    v_factor numeric := 1.0;
    v_zonas integer := 0;
BEGIN
    WITH puntos AS (
        SELECT
            (coord->>0)::numeric AS lat,
            (coord->>1)::numeric AS lon
        FROM jsonb_array_elements(COALESCE(p_ruta_coords, '[]'::jsonb)) AS coord
    ),
    semaforos_detectados AS (
        SELECT DISTINCT
            s.id,
            s.tiempo_rojo_seg,
            s.tiempo_amarillo_seg
        FROM puntos p
        JOIN semaforos s
          ON ST_DWithin(
                public.fn_point_to_geom(s.ubicacion)::geography,
                ST_SetSRID(ST_MakePoint(p.lon::double precision, p.lat::double precision), 4326)::geography,
                100
             )
    )
    SELECT
        COALESCE(COUNT(*), 0),
        COALESCE(SUM(((tiempo_rojo_seg + tiempo_amarillo_seg) / 2)), 0)
    INTO v_semaforos, v_tiempo_semaforos
    FROM semaforos_detectados;

    WITH puntos AS (
        SELECT
            (coord->>0)::numeric AS lat,
            (coord->>1)::numeric AS lon
        FROM jsonb_array_elements(COALESCE(p_ruta_coords, '[]'::jsonb)) AS coord
    ),
    zonas_detectadas AS (
        SELECT DISTINCT
            z.id,
            z.factor_multiplicador_tiempo,
            z.horarios_pico
        FROM puntos p
        JOIN zonas_congestion z
          ON ST_Contains(
                ST_SetSRID(z.geometria::geometry, 4326),
                ST_SetSRID(ST_MakePoint(p.lon::double precision, p.lat::double precision), 4326)
             )
    )
    SELECT
        COALESCE(COUNT(*), 0),
        COALESCE(MAX(
            CASE
                WHEN public.fn_horarios_pico_activos(horarios_pico) THEN factor_multiplicador_tiempo
                ELSE factor_multiplicador_tiempo * 0.3
            END
        ), 1.0)
    INTO v_zonas, v_factor
    FROM zonas_detectadas;

    RETURN QUERY SELECT v_semaforos, v_tiempo_semaforos, v_factor, v_zonas;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_horarios_pico_activos(p_horarios jsonb)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM jsonb_array_elements(COALESCE(p_horarios, '[]'::jsonb)) AS horario
        WHERE (
            (horario->>'inicio')::time <= (horario->>'fin')::time
            AND CURRENT_TIME BETWEEN (horario->>'inicio')::time AND (horario->>'fin')::time
        ) OR (
            -- caso de cruce de día: p.ej. inicio 22:00, fin 06:00
            (horario->>'inicio')::time > (horario->>'fin')::time
            AND (CURRENT_TIME >= (horario->>'inicio')::time OR CURRENT_TIME <= (horario->>'fin')::time)
        )
    );
$$;

-- ============================================================================
-- REGISTRAR RETORNO DE AMBULANCIA
-- ============================================================================
CREATE OR REPLACE FUNCTION public.registrar_retorno_ambulancia(
    p_ambulancia_id uuid,
    p_incidente_id uuid DEFAULT NULL
)
RETURNS TABLE(ok boolean, mensaje text)
LANGUAGE plpgsql
AS $$
DECLARE
    v_ambulancias ambulancias%ROWTYPE;
BEGIN
    SELECT * INTO v_ambulancias
    FROM ambulancias
    WHERE id = p_ambulancia_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Ambulancia no encontrada'::text;
        RETURN;
    END IF;

    -- Marcar que la ambulancia ha regresado al puesto (puede ajustarse a 'disponible' si se desea)
    UPDATE ambulancias
    SET estado = 'en_posta',
        ultima_actualizacion = NOW()
    WHERE id = p_ambulancia_id;

    -- Si se pasó incidente, cerrarlo (opcional según workflow)
    IF p_incidente_id IS NOT NULL THEN
        UPDATE incidentes
        SET estado = 'cerrado'
        WHERE id = p_incidente_id;
    END IF;

    RETURN QUERY SELECT true, 'Retorno registrado correctamente'::text;
END;
$$;

COMMIT;
