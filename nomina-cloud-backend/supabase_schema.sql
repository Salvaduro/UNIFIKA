-- ==========================================
-- SCRIPT DE MIGRACIÓN PARA SUPABASE (POSTGRESQL)
-- ==========================================
-- Este script crea la estructura de datos basada en el liquidador de Pandas.

-- 1. Tabla M_APORTANTES (Empresas / Clientes / Empleadores)
CREATE TABLE m_aportantes (
    id_aportante VARCHAR(50) PRIMARY KEY,
    razon_social VARCHAR(255) NOT NULL,
    tipo_documento VARCHAR(50),
    carpeta_cliente VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla M_EMPLEADOS (Trabajadores y sus Contratos)
-- Se usa id_contrato como Primary Key porque un empleado puede tener varios contratos 
-- a lo largo del tiempo o con diferentes aportantes.
CREATE TABLE m_empleados (
    id_contrato VARCHAR(50) PRIMARY KEY,
    id_aportante VARCHAR(50) NOT NULL REFERENCES m_aportantes(id_aportante) ON DELETE CASCADE,
    id_empleado VARCHAR(50) NOT NULL,
    t_id_empleado VARCHAR(20),
    nombre_empleado VARCHAR(255) NOT NULL,
    cargo VARCHAR(150),
    
    -- Variables contractuales
    tipo_contrato VARCHAR(50) DEFAULT 'TIEMPO COMPLETO', -- TIEMPO COMPLETO, TIEMPO PARCIAL, EMPLEADO INTERNO
    estado_empleado VARCHAR(50) DEFAULT 'ACTIVO',        -- ACTIVO, RETIRADO
    periodo_pago VARCHAR(50) DEFAULT 'QUINCENAL',
    
    -- Valores monetarios bases
    salario_base NUMERIC(12, 2) DEFAULT 0,
    vlr_bono NUMERIC(12, 2) DEFAULT 0,
    sal_especie NUMERIC(12, 2) DEFAULT 0,
    
    -- Seguridad Social
    eps VARCHAR(100) DEFAULT 'N/A',
    afp VARCHAR(100) DEFAULT 'N/A',
    
    -- Variables booleanas de liquidación
    es_smlv BOOLEAN DEFAULT FALSE,
    con_bono BOOLEAN DEFAULT FALSE,
    tiene_aux BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla T_NOVEDADES (Registro transaccional de novedades por periodo)
CREATE TABLE t_novedades (
    id_novedad UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_contrato VARCHAR(50) NOT NULL REFERENCES m_empleados(id_contrato) ON DELETE CASCADE,
    
    -- Identificadores del periodo
    periodo_liq VARCHAR(50) NOT NULL, -- Ej: 'MAYO 2026'
    quincena_pago VARCHAR(50),        -- Ej: '1' o '2'
    
    -- Flag de procesamiento
    generar_nomina BOOLEAN DEFAULT TRUE,
    
    -- Días y Horas
    dias_laborados NUMERIC(5, 2) DEFAULT 0,
    horas_laboradas NUMERIC(5, 2) DEFAULT 0,
    dias_vacaciones NUMERIC(5, 2) DEFAULT 0,
    dias_incapacidad NUMERIC(5, 2) DEFAULT 0,
    
    -- Valores monetarios puntuales
    prestamos NUMERIC(12, 2) DEFAULT 0,
    prima_calc NUMERIC(12, 2) DEFAULT 0,
    
    -- Factores de recargos y horas extras
    hed NUMERIC(5, 2) DEFAULT 0,  -- Hora Extra Diurna
    hen NUMERIC(5, 2) DEFAULT 0,  -- Hora Extra Nocturna
    hedf NUMERIC(5, 2) DEFAULT 0, -- Hora Extra Dominical/Festiva Diurna
    henf NUMERIC(5, 2) DEFAULT 0, -- Hora Extra Dominical/Festiva Nocturna
    rn NUMERIC(5, 2) DEFAULT 0,   -- Recargo Nocturno
    rdn NUMERIC(5, 2) DEFAULT 0,  -- Recargo Dominical/Festivo Diurno
    rnf NUMERIC(5, 2) DEFAULT 0,  -- Recargo Festivo Nocturno
    
    observaciones TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Restricción para evitar duplicar nóminas del mismo contrato en la misma quincena y periodo
    UNIQUE (id_contrato, periodo_liq, quincena_pago)
);

-- Índices recomendados para optimización de consultas
CREATE INDEX idx_empleados_aportante ON m_empleados(id_aportante);
CREATE INDEX idx_novedades_contrato ON t_novedades(id_contrato);
CREATE INDEX idx_novedades_periodo ON t_novedades(periodo_liq, quincena_pago);
