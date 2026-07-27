# 🛑 DOSSIER DE ARQUITECTURA Y REGLAS (UNIFIKA NÓMINA CLOUD - FASE 5)
**LEER ANTES DE PROPONER CUALQUIER CAMBIO DE CÓDIGO**

## 1. STACK TECNOLÓGICO Y ARQUITECTURA
- **Frontend:** React + Vite + Tailwind CSS. (Despliegue objetivo: Vercel).
- **Backend:** Python + FastAPI. (Despliegue objetivo: Render).
- **Base de Datos:** PostgreSQL en Supabase.
- **CRM / Integración:** Wolkvox (Salida mediante proxy Fixie).

## 2. ARQUITECTURA MULTI-TENANT Y ROLES (RBAC)
- **Tabla `m_perfiles`:** Contiene `id_aportante` (FK) y `rol`.
- **Roles Normalizados (Siempre en MAYÚSCULAS):**
  - `EMPLEADOR`: Cliente estándar. Solo tiene acceso a la información donde `id_aportante` coincida.
  - `ADMINISTRADOR` / `SUPERADMIN`: Staff interno de UNIFIKA. Su `id_aportante` es nulo. Pueden saltar el filtro de tenant para ver a todas las empresas.
- **Frontend (Patrón Impersonation):** No hay Dashboards separados. Es una sola interfaz unificada. Si el rol es `EMPLEADOR`, se carga su nómina automáticamente. Si el rol es `SUPERADMIN`/`ADMINISTRADOR`, la UI muestra un input de búsqueda por ID y un botón de "Sincronizar a CRM" para suplantar a cualquier empresa.

## 3. REGLAS CRÍTICAS DE NEGOCIO (INMUTABLES)
- **Tiempo Parcial (UGPP):** Las horas extras NO suman al IBC. Excepción: si pagan salud, el IBC se fuerza a 1 SMLV.
- **Cierre de Nómina (El Candado):** Si existe un registro en `t_cierres_nomina` para un `id_contrato`, la nómina es intocable (HTTP 403). El cierre es por empleado, no por empresa.
- **Sincronización JiT:** Las peticiones a Wolkvox buscan Aportantes, luego en cascada a sus Empleados, aplicando Soft-Delete (`estado_empleado = 'RETIRADO'`) a los que ya no existan en el CRM.
- **Seguridad en Supabase:** El agente de IDE (Antigravity) solo tiene credenciales de acceso READ-ONLY a la base de datos para inspeccionar esquemas. Todo cambio estructural en DB lo hace el Director.

## 4. BRANDING Y ESTILOS (TAILWIND CSS)
- **Paleta Estricta:** - Pestañas/Fondos neutros: `#83a9b2`
  - Cabeceras principales: `#5b97a9`
  - CTAs (Botones primarios) y Alertas: `#babf15`
  - Elementos de solo lectura: `bg-slate-100`