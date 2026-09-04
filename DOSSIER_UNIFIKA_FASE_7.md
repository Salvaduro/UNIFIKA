# DOSSIER FASE 7: Ausentismos y Storage Médico
**ESTADO: CERRADA Y EN PRODUCCIÓN 🏆**

*   **Hidratación Maestra (Reactividad):** Se eliminaron los "Stale Closures". El UI ahora reacciona automáticamente a la base de datos al cambiar de periodo.
*   **Matemática de Licencias (SLN):** El motor descuenta matemáticamente los días no remunerados del sueldo básico pagado, reportándolos a cero pesos pero visibles en el PDF.
*   **Storage Zero-Trash:** Transaccionalidad perfecta entre PostgreSQL y Supabase Storage. Archivos huérfanos se eliminan físicamente al borrar el registro.
*   **Muro de Privacidad:** Implementación de URLs firmadas (Signed URLs) al vuelo (60 seg) para la visualización de soportes médicos, con políticas RLS omnipotentes para el backend.