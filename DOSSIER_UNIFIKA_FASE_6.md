# 🚀 DOSSIER DE ARQUITECTURA Y REGLAS (UNIFIKA NÓMINA CLOUD - FASE 6)
**ESTADO: PRODUCCIÓN ESTABLE | ETAPA: OPERACIÓN CONTINUA Y QUICK WINS**

## 1. CONTEXTO ACTUAL
El MVP está desplegado de forma estable (Vercel para Frontend, Render para Backend, Supabase para DB). La arquitectura Multi-Tenant y el Control de Accesos (RBAC) basados en el `id_aportante` y el `rol` (EMPLEADOR, ADMINISTRADOR, SUPERADMIN) funcionan correctamente mediante un Dashboard unificado (Patrón Impersonation).

## 2. OBJETIVOS DE LA FASE 6
A partir de la retroalimentación de clientes y staff, esta fase se enfoca en automatización, control de auditoría y cálculo de prestaciones:
1. **Ciclos de Cierre Automáticos:** Bloqueo de periodos (Q1, Q2/Mensual) 3 días hábiles posteriores a su vencimiento.
2. **Reversión de Cierres (Override) [✓ LOGRADO]:** Facultad exclusiva del STAFF (ADMINISTRADOR/SUPERADMIN) para desbloquear nóminas.
3. **Auditoría y Telemetría [✓ LOGRADO]:** Trazabilidad de uso (guardados, cierres, reaperturas) tanto del STAFF como de los EMPLEADORES mediante la tabla `t_auditoria_logs`.
4. **Pre-liquidación Automática:** Clonación de la nómina anterior con envío de notificaciones (Email/WhatsApp) para aprobación por omisión.
5. **Motor de Prestaciones:** Prototipado del cálculo de Primas y Cesantías.

## 3. NUEVAS REGLAS DE NEGOCIO (MODIFICACIONES SOBRE FASE 5)
- **Flexibilidad del Candado (`t_cierres_nomina`):** La regla de inmutabilidad absoluta se relaja. El candado sigue siendo INMUTABLE para el `EMPLEADOR`. Sin embargo, los roles `ADMINISTRADOR` y `SUPERADMIN` adquieren el superpoder de ELIMINAR el registro de cierre para permitir correcciones excepcionales.
- **Cálculo de Días Hábiles:** Cualquier lógica de cierre por tiempo DEBE contemplar el calendario de días festivos oficiales de Colombia.
- **Registro Centralizado de Auditoría:** Toda acción de impacto (creación, edición de nóminas, cierres y reaperturas) exige un registro obligatorio en la tabla `t_auditoria_logs`.

## 4. DIRECTRICES PARA EL DESARROLLADOR IA (ANTIGRAVITY)
- Toda nueva librería en Python debe documentarse en `requirements.txt`.
- Para UI de roles, seguir basándose en el estado global normalizado en mayúsculas extraído de `m_perfiles`.
- Prohibido construir sistemas complejos desde cero sin la autorización del Tech Lead. Aplicar el principio de "Quick Wins" (Victorias Rápidas) iterativas.