# 🗺️ MAPA DE ARQUITECTURA Y COMPONENTES (UNIFIKA CLOUD)

## 1. STACK DE INFRAESTRUCTURA Y HOSTING
- **Frontend:** React + Vite + Tailwind CSS. Alojado en **Vercel**.
- **Backend:** Python + FastAPI. Alojado en Web Services de **Render**.
- **Base de Datos:** PostgreSQL alojado en **Supabase**.
- **Proxy Salida:** Fixie.

## 2. FLUJO DE AUTENTICACIÓN Y EXTRACCIÓN (JiT SYNC)
**Rutas Centrales:** `/api/v1/auth/init-session` y `/api/v1/empleador/{id}/sync`.
- **Paso 1:** Autenticación en Supabase. El sistema exige confirmación por correo electrónico. No se permite el ingreso hasta que el usuario confirme su email (estado bloqueado en Supabase Auth).
- **Paso 2:** Verifica si el `id_aportante` existe en Supabase local. Si no existe o es Sync Manual, llama a Wolkvox Contactos. Guarda `razon_social`, `estado_contacto`, y `carpeta_cliente` en `m_aportantes`.
- **Paso 3:** Llamada en Cascada a Wolkvox Oportunidades. Descarga empleados, aplica Soft-Delete a los "lost" y hace `UPSERT` en `m_empleados`.

## 3. FLUJO DE LIQUIDACIÓN DE NÓMINA Y PDFs
**Ruta Backend (`POST /api/v1/novedades` o `/api/v1/liquidar`):**
- **Capa 1:** Server-Side Lock (`SELECT` a `t_cierres_nomina` por `id_contrato`). Si existe, lanza HTTP 403. (Nota: Sujeto a anulación por STAFF en Fase 6).
- **Capa 2:** Inserta/Actualiza en `t_novedades`. NO toca `m_aportantes` ni `m_empleados`.
- **Capa 3 (FPDF):** Genera PDF mapeando propiedades como `empleado.cargo` y devengados.

## 4. MAPA DE BASE DE DATOS Y MULTI-TENANT (SUPABASE)
- **`m_aportantes`:** `id_aportante`, `estado_contacto`, `carpeta_cliente`.
- **`m_empleados`:** `id_contrato` (PK compuesta), `id_empleado` (Cédula), `id_aportante` (FK), `link_drive`, `estado_empleado`.
- **`t_novedades`:** Histórico de nómina quincenal por `id_contrato`.
- **`t_cierres_nomina`:** El Candado por `id_contrato`.
- **`t_auditoria_logs` (NUEVO FASE 6):** Tabla de telemetría y trazabilidad con campo `JSONB` para registrar cierres, reaperturas (Override) y guardados históricos de todos los roles.
- **`m_perfiles`:** Contiene `id_aportante` (FK) y `rol`. Arquitectura RBAC Multi-Tenant: 
  - `EMPLEADOR`: Solo ve su propia empresa (Filtrado estricto por id_aportante).
  - `ADMINISTRADOR` / `SUPERADMIN`: Staff interno. Saltan el filtro de tenant para ver a todos los clientes.
- **Frontend (Patrón Impersonation):** No hay Dashboards separados. Un único Dashboard dinámico en React. `EMPLEADOR` ve su nómina automáticamente. `SUPERADMIN`/`ADMINISTRADOR` controlan la vista y suplantan clientes mediante una barra de búsqueda por `ID Empleador`.

## 5. ESTILOS UI (TAILWIND CSS BRANDING)
- Pestañas: `#83a9b2`
- Cabeceras: `#5b97a9` (Texto blanco, negrita)
- CTAs (Botones principales): `#babf15` (Hover: `#a2a812`)