-- Migración 1: Schema limpio y compatible con la app SEM
-- Este schema debe correr sobre una base vacía o después de un reset.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS postas_medicas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL UNIQUE,
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN ('posta_basica', 'posta_avanzada', 'hospital')),
    latitud DECIMAL(10, 8) NOT NULL,
    longitud DECIMAL(11, 8) NOT NULL,
    ubicacion POINT GENERATED ALWAYS AS (POINT(longitud, latitud)) STORED,
    capacidad_ambulancias INT NOT NULL DEFAULT 1,
    especialidades TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    telefonos TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    horario_atencion JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ambulancias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(20) UNIQUE NOT NULL,
    posta_base_id UUID NOT NULL REFERENCES postas_medicas(id) ON DELETE RESTRICT,
    estado VARCHAR(50) NOT NULL DEFAULT 'disponible' CHECK (estado IN ('disponible', 'en_ruta', 'ocupada', 'mantenimiento')),
    equipamiento TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    conductor VARCHAR(255),
    ubicacion_actual POINT,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidentes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp_reporte TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ubicacion POINT NOT NULL,
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN ('menor', 'mayor')),
    descripcion TEXT,
    paciente_nombre VARCHAR(255),
    paciente_edad INT,
    sintomas TEXT[] DEFAULT ARRAY[]::TEXT[],
    contacto_emergencia VARCHAR(255),
    ambulancia_asignada_id UUID REFERENCES ambulancias(id) ON DELETE SET NULL,
    posta_destino_id UUID REFERENCES postas_medicas(id) ON DELETE SET NULL,
    estado VARCHAR(50) NOT NULL DEFAULT 'reportado' CHECK (estado IN ('reportado', 'en_transporte', 'en_posta', 'cerrado')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rutas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incidente_id UUID NOT NULL REFERENCES incidentes(id) ON DELETE CASCADE,
    ambulancia_id UUID NOT NULL REFERENCES ambulancias(id) ON DELETE RESTRICT,
    ruta_geojson JSONB,
    distancia_km DECIMAL(8, 2),
    tiempo_estimado_seg INT,
    tiempo_real_seg INT,
    semaforos_encontrados INT,
    congestiones INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semaforos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL,
    ubicacion POINT NOT NULL,
    interseccion VARCHAR(255),
    tiempo_rojo_seg INT DEFAULT 20,
    tiempo_verde_seg INT DEFAULT 20,
    tiempo_amarillo_seg INT DEFAULT 3,
    estado VARCHAR(50) DEFAULT 'verde' CHECK (estado IN ('rojo', 'verde', 'amarillo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zonas_congestion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL,
    geometria POLYGON,
    factor_multiplicador_tiempo DECIMAL(3, 2) DEFAULT 1.60,
    horarios_pico JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_postas_ubicacion ON postas_medicas USING GIST(ubicacion);
CREATE INDEX IF NOT EXISTS idx_incidentes_ubicacion ON incidentes USING GIST(ubicacion);
CREATE INDEX IF NOT EXISTS idx_incidentes_estado ON incidentes(estado);
CREATE INDEX IF NOT EXISTS idx_incidentes_ambulancia ON incidentes(ambulancia_asignada_id);
CREATE INDEX IF NOT EXISTS idx_ambulancias_posta ON ambulancias(posta_base_id);
CREATE INDEX IF NOT EXISTS idx_ambulancias_estado ON ambulancias(estado);
CREATE INDEX IF NOT EXISTS idx_rutas_incidente ON rutas(incidente_id);
CREATE INDEX IF NOT EXISTS idx_rutas_ambulancia ON rutas(ambulancia_id);
CREATE INDEX IF NOT EXISTS idx_semaforos_ubicacion ON semaforos USING GIST(ubicacion);

