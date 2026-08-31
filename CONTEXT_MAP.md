# Mapa de Contexto Arquitectónico - UNIFIKA Nómina Cloud

## 1. Topología de Infraestructura (Stateless)
*   **Frontend:** React + Vite (Desplegado en Vercel).
*   **Backend:** Python + FastAPI (Desplegado en Render). Usa discos efímeros (PROHIBIDO guardar archivos físicos).
*   **Base de Datos:** PostgreSQL (Alojado en Supabase).
*   **Proxy de Salida (IP Fija):** Fixie (Enruta peticiones de Render hacia el firewall de Wolkvox CRM).
*   **Comunicaciones (Email):** Resend (Envío de correos transaccionales con adjuntos PDF generados en memoria RAM. Puerto SMTP: 2525/465/587).
*   **Automatización:** cron-job.org lanza un POST diario a las 6:00 AM al endpoint `/api/v1/cron/procesar-ciclo`. **El backend orquesta esto vía BackgroundTasks para evitar Timeouts.**

## 2. Entidades Core y Flujo de Datos
*   **`m_empleados` (Fuente de la Verdad):** Contiene la data maestra. Al generar o clonar nóminas, los datos fijos SIEMPRE se extraen de aquí. Excluye estados: 'RETIRADO', 'En Mora SS', 'UnicaAfiliacion'.
*   **`t_novedades` (Transaccional):** Almacena las variables del periodo. La regeneración histórica de PDFs usa un **Patrón Híbrido**: calcula el desglose al vuelo, pero sobreescribe deducciones y totales con la BD para garantizar inmutabilidad.
*   **`t_cierres_nomina` (Candado):** Registro de inmutabilidad. Se activa automáticamente 3 días hábiles después del corte.
*   **`t_auditoria_logs` (Telemetría):** Caja negra del sistema. Registra acciones del STAFF, EMPLEADOR y SISTEMA_CRON.

## 3. Seguridad y RBAC
*   **Roles:** SUPERADMIN, ADMINISTRADOR (STAFF) y EMPLEADOR (Cliente).
*   **Override:** Solo el STAFF puede reabrir nóminas cerradas.
*   **Cron Security:** Protegido por el header `X-Cron-Secret`.
*   **Ejecución Dirigida:** El Cron soporta el parámetro `?target_aportante=ID` para aislar pruebas en producción.

## 4. Próxima Arquitectura (Fase 7 - Prestaciones y PILA)
*   *En diseño:* Transición a tablas de control de fechas (inicio/fin) para ausentismos (licencias e incapacidades).
*   *En diseño:* Acumuladores de IBC y días laborados para liquidación automática de primas, cesantías e intereses.
*   *En diseño:* Motor de cálculo de Parafiscales (SENA, ICBF, CCF) utilizando el IBC_PILA actual.