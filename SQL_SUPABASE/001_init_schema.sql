-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.ambulancias (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  codigo character varying NOT NULL UNIQUE,
  posta_base_id uuid NOT NULL,
  estado character varying NOT NULL DEFAULT 'disponible'::character varying CHECK (estado::text = ANY (ARRAY['disponible'::character varying, 'en_ruta'::character varying, 'ocupada'::character varying, 'mantenimiento'::character varying]::text[])),
  ubicacion_actual point,
  ultima_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ambulancias_pkey PRIMARY KEY (id),
  CONSTRAINT ambulancias_posta_base_id_fkey FOREIGN KEY (posta_base_id) REFERENCES public.postas_medicas(id)
);
CREATE TABLE public.incidentes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  timestamp_reporte timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  ubicacion point NOT NULL,
  tipo character varying NOT NULL CHECK (tipo::text = ANY (ARRAY['menor'::character varying, 'mayor'::character varying]::text[])),
  paciente_nombre character varying,
  ambulancia_asignada_id uuid,
  posta_destino_id uuid,
  estado character varying NOT NULL DEFAULT 'reportado'::character varying CHECK (estado::text = ANY (ARRAY['reportado'::character varying, 'sin_recursos'::character varying, 'en_transporte'::character varying, 'en_posta'::character varying, 'cerrado'::character varying]::text[])),
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT incidentes_pkey PRIMARY KEY (id),
  CONSTRAINT incidentes_ambulancia_asignada_id_fkey FOREIGN KEY (ambulancia_asignada_id) REFERENCES public.ambulancias(id),
  CONSTRAINT incidentes_posta_destino_id_fkey FOREIGN KEY (posta_destino_id) REFERENCES public.postas_medicas(id)
);
CREATE TABLE public.postas_medicas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre character varying NOT NULL UNIQUE,
  tipo character varying NOT NULL CHECK (tipo::text = ANY (ARRAY['posta_basica'::character varying, 'posta_avanzada'::character varying, 'hospital'::character varying]::text[])),
  latitud numeric NOT NULL,
  longitud numeric NOT NULL,
  ubicacion point DEFAULT point((longitud)::double precision, (latitud)::double precision),
  capacidad_ambulancias integer NOT NULL DEFAULT 1,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT postas_medicas_pkey PRIMARY KEY (id)
);
CREATE TABLE public.rutas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  incidente_id uuid NOT NULL,
  ambulancia_id uuid NOT NULL,
  ruta_geojson jsonb,
  distancia_km numeric,
  tiempo_estimado_seg integer,
  tiempo_real_seg integer,
  semaforos_encontrados integer,
  congestiones integer DEFAULT 0,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  traffic_details jsonb,
  CONSTRAINT rutas_pkey PRIMARY KEY (id),
  CONSTRAINT rutas_incidente_id_fkey FOREIGN KEY (incidente_id) REFERENCES public.incidentes(id),
  CONSTRAINT rutas_ambulancia_id_fkey FOREIGN KEY (ambulancia_id) REFERENCES public.ambulancias(id)
);
CREATE TABLE public.semaforos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre character varying NOT NULL,
  ubicacion point NOT NULL,
  interseccion character varying,
  tiempo_rojo_seg integer DEFAULT 20,
  tiempo_verde_seg integer DEFAULT 20,
  tiempo_amarillo_seg integer DEFAULT 3,
  estado character varying DEFAULT 'verde'::character varying CHECK (estado::text = ANY (ARRAY['rojo'::character varying, 'verde'::character varying, 'amarillo'::character varying]::text[])),
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT semaforos_pkey PRIMARY KEY (id)
);
CREATE TABLE public.spatial_ref_sys (
  srid integer NOT NULL CHECK (srid > 0 AND srid <= 998999),
  auth_name character varying,
  auth_srid integer,
  srtext character varying,
  proj4text character varying,
  CONSTRAINT spatial_ref_sys_pkey PRIMARY KEY (srid)
);
CREATE TABLE public.zonas_congestion (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre character varying NOT NULL,
  geometria polygon,
  factor_multiplicador_tiempo numeric DEFAULT 1.60,
  horarios_pico jsonb,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT zonas_congestion_pkey PRIMARY KEY (id)
);