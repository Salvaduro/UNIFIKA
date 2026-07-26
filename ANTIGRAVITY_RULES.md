# 🛑 CONSTITUCIÓN Y REGLAS INMUTABLES DE ANTIGRAVITY (UNIFIKA NÓMINA CLOUD)
**LEER ANTES DE ESCRIBIR CUALQUIER LÍNEA DE CÓDIGO**

## 1. REGLAS DE NEGOCIO (BUSINESS LOGIC)
- **Cálculo UGPP (Tiempo Parcial):** Las horas extras NO suman al IBC. Excepción única: si pagan salud, el IBC se fuerza obligatoriamente a 1 SMLV.
- **Inmutabilidad de Nómina:** Una nómina con estado "CERRADA" en `t_cierres_nomina` es sagrada. NO se puede modificar, actualizar ni sobreescribir. El backend DEBE rechazar la petición con HTTP 403.
- **Cierre Granular:** El candado de cierre de nómina se aplica por EMPLEADO (`id_contrato`), NUNCA por empresa (`id_aportante`).
- **Manejo de Rotación (Wolkvox):** NUNCA aplicar Hard-Delete a un empleado que ya no viene en Wolkvox (estado "lost"). Aplicar **Soft-Delete** cambiando `estado_empleado = 'RETIRADO'`.
- **Muro de Contención (Mora):** Empleadores con estado `"En Mora SS"`, `"RETIRADO"` o `"UnicaAfiliacion"` en Wolkvox no pueden operar. El backend debe lanzar HTTP 403 con mensaje para llamar a soporte.

## 2. REGLAS DE BASE DE DATOS Y ESTADO (POSTGRESQL / SUPABASE)
- **Tipado Estricto:** PostgreSQL rechaza comparaciones String vs Integer. Siempre usar `str(id_aportante)` antes de cualquier consulta SQL/SQLAlchemy.
- **Escudo Anti-Nulls (Side-Effects):** Al hacer un `UPDATE` o `UPSERT` en tablas maestras (`m_aportantes`, `m_empleados`), el modelo Pydantic DEBE incluir `exclude_unset=True, exclude_none=True`. Nunca sobreescribir datos valiosos con NULL por recibir payloads incompletos.
- **Transacciones Envenenadas:** Toda lectura de BD que preceda a un `UPSERT` debe estar envuelta en `try-except` con un `db.rollback()` obligatorio en caso de fallo.
- **Llaves Compuestas:** La llave primaria de un empleado en la nómina es `id_contrato` (`NIT_CEDULA`). Cuando se busca en Wolkvox, se debe extraer la cédula real (Unpacking).

## 3. REGLAS DE FRONTEND (REACT / VITE)
- **UI de Nómina:** Un solo botón de "Guardar y Descargar Desprendible" (Promise Chaining). Si la nómina está cerrada, el botón desaparece y se muestra un mensaje estático.
- **Seguridad de Sesión (Idle Timer):** Cierre de sesión automático tras 15 minutos de inactividad (borrado de tokens local).
- **Prohibido Guardar al Morir (Unmount):** La acción de Logout NUNCA debe lanzar peticiones HTTP `POST/PUT` al backend. Solo destruye sesión localmente.
- **Manejo de Errores Visuales:** Las alertas (Toasts) nunca deben mostrar `[object Object]`. Siempre extraer `error.response?.data?.detail`.

## 4. REGLAS DE INTEGRACIÓN Y RED (WOLKVOX / FIXIE)
- **Proxy Obligatorio:** Las peticiones a Wolkvox deben salir por la variable `FIXIE_URL` usando `proxy=fixie_url`.
- **Fallo Silencioso (Case-Sensitive):** Wolkvox es sensible a mayúsculas.
- **Sincronización en Cascada (JiT):** Siempre que se sincronice un aportante, el código debe continuar inmediatamente a sincronizar sus empleados, trayendo `Carpeta Cliente` (usando `.get()`).

## 5. REGLAS DE INFRAESTRUCTURA (RENDER & VERCEL)
- **Discos Efímeros en Render:** El backend está en Render. NO guardar archivos físicos en disco. Todo PDF de ReportLab debe generarse en memoria (`BytesIO`) y devolverse vía `StreamingResponse`.
- **Puertos Dinámicos:** Escuchar en `0.0.0.0` y usar la variable de entorno `PORT` de Render.
- **CORS Estricto:** Permitir la URL de Vercel y localhost.
