import uuid
import datetime
from sqlalchemy import Column, String, Boolean, Numeric, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from enum import StrEnum
from database import Base


class RolUsuario(StrEnum):
    EMPLEADOR = "EMPLEADOR"
    ADMINISTRADOR = "ADMINISTRADOR"
    SUPERADMIN = "SUPERADMIN"


class Aportante(Base):
    """
    Modelo ORM para m_aportantes (Empresas / Empleadores en UNIFIKA).
    Constituye el nivel superior de tenencia (Tenant Principal).
    """
    __tablename__ = "m_aportantes"

    id_aportante = Column(String(50), primary_key=True)
    razon_social = Column(String(255), nullable=False)
    tipo_documento = Column(String(50), nullable=True)
    tipo_empleador = Column(String(50), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    estado_contacto = Column(String(100), nullable=True)
    carpeta_cliente = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)

    # Relación (relationship) con m_perfiles (Multi-Tenant)
    perfiles = relationship("Perfil", back_populates="aportante", cascade="all, delete-orphan")

    # Relación con m_empleados
    empleados = relationship("Empleado", back_populates="aportante", cascade="all, delete-orphan")


class Perfil(Base):
    """
    Modelo ORM para m_perfiles (Perfiles y Usuarios autenticados por Supabase Auth).
    Incluye id_aportante y relación con m_aportantes para arquitectura Multi-Tenant.
    """
    __tablename__ = "m_perfiles"

    id = Column(String(36), primary_key=True)
    rol = Column(String(50), nullable=False, default=RolUsuario.EMPLEADOR.value)
    id_aportante = Column(
        String(50),
        ForeignKey("m_aportantes.id_aportante", ondelete="SET NULL"),
        nullable=True
    )
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)

    # Relación (relationship) con m_aportantes (Multi-Tenant)
    aportante = relationship("Aportante", back_populates="perfiles")


class Empleado(Base):
    """
    Modelo ORM para m_empleados (Trabajadores y sus Contratos).
    """
    __tablename__ = "m_empleados"

    id_contrato = Column(String(50), primary_key=True)
    id_aportante = Column(
        String(50),
        ForeignKey("m_aportantes.id_aportante", ondelete="CASCADE"),
        nullable=False
    )
    id_empleado = Column(String(50), nullable=False)
    t_id_empleado = Column(String(20), nullable=True)
    nombre_empleado = Column(String(255), nullable=False)
    cargo = Column(String(150), nullable=True)
    tipo_contrato = Column(String(50), default="TIEMPO COMPLETO")
    estado_empleado = Column(String(50), default="ACTIVO")
    periodo_pago = Column(String(50), default="QUINCENAL")
    salario_base = Column(Numeric(12, 2), default=0)
    vlr_bono = Column(Numeric(12, 2), default=0)
    sal_especie = Column(Numeric(12, 2), default=0)
    eps = Column(String(100), default="N/A")
    afp = Column(String(100), default="N/A")
    es_smlv = Column(Boolean, default=False)
    con_bono = Column(Boolean, default=False)
    tiene_aux = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)
    nombre_1 = Column(String(100), nullable=True)
    nombre_2 = Column(String(100), nullable=True)
    apellido_1 = Column(String(100), nullable=True)
    apellido_2 = Column(String(100), nullable=True)
    departamento = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    riesgo_arl = Column(String(50), nullable=True)
    ccf = Column(String(100), nullable=True)
    arl = Column(String(100), nullable=True)
    link_drive = Column(Text, nullable=True)

    # Relación con m_aportantes
    aportante = relationship("Aportante", back_populates="empleados")
    # Relación con t_novedades
    novedades = relationship("Novedad", back_populates="empleado", cascade="all, delete-orphan")


class Novedad(Base):
    """
    Modelo ORM para t_novedades (Registro quincenal transaccional).
    """
    __tablename__ = "t_novedades"

    id_novedad = Column(String(36), primary_key=True)
    id_contrato = Column(
        String(50),
        ForeignKey("m_empleados.id_contrato", ondelete="CASCADE"),
        nullable=False
    )
    periodo_liq = Column(String(50), nullable=False)
    quincena_pago = Column(String(50), nullable=True)
    generar_nomina = Column(Boolean, default=True)
    dias_laborados = Column(Numeric(5, 2), default=0)
    horas_laboradas = Column(Numeric(5, 2), default=0)
    dias_vacaciones = Column(Numeric(5, 2), default=0)
    dias_incapacidad = Column(Numeric(5, 2), default=0)
    prestamos = Column(Numeric(12, 2), default=0)
    prima_calc = Column(Numeric(12, 2), default=0)
    hed = Column(Numeric(5, 2), default=0)
    hen = Column(Numeric(5, 2), default=0)
    hedf = Column(Numeric(5, 2), default=0)
    henf = Column(Numeric(5, 2), default=0)
    rn = Column(Numeric(5, 2), default=0)
    rdn = Column(Numeric(5, 2), default=0)
    rnf = Column(Numeric(5, 2), default=0)
    observaciones = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)
    ibc_pila = Column(Numeric(12, 2), nullable=True)
    salud_4 = Column(Numeric(12, 2), nullable=True)
    pension_4 = Column(Numeric(12, 2), nullable=True)
    total_devengado = Column(Numeric(12, 2), nullable=True)
    total_deducido = Column(Numeric(12, 2), nullable=True)
    neto_pagar = Column(Numeric(12, 2), nullable=True)
    salario_base = Column(Numeric(12, 2), nullable=True)
    vlr_bono = Column(Numeric(12, 2), nullable=True)
    sal_especie = Column(Numeric(12, 2), nullable=True)

    # Relación con m_empleados
    empleado = relationship("Empleado", back_populates="novedades")


class CierreNomina(Base):
    """
    Modelo ORM para t_cierres_nomina (Candado de inmutabilidad por empleado).
    """
    __tablename__ = "t_cierres_nomina"

    id_cierre = Column(String(36), primary_key=True)
    id_contrato = Column(String(50), nullable=False)
    periodo_liq = Column(String(50), nullable=False)
    quincena_pago = Column(String(50), nullable=False)
    fecha_cierre = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)
    cerrado_por = Column(String(100), nullable=True)
