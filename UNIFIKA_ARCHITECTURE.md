# UNIFIKA CORE ARCHITECTURE (Fase 8 Setup)

*   **Single Source of Truth:** La UI se hidrata lanzando peticiones concurrentes a `t_novedades` y `t_ausentismos` basándose en el periodo actual.
*   **Cálculo al Vuelo (Frontend):** React suma días de incidencias (IGE, VAC, SLN) deduciendo fechas y auto-completa el formulario antes del envío.
*   **Motor Salarial (Backend):** Python recibe los días, aplica reglas laborales (topes de auxilio, exclusiones de bonos) y devuelve el json final.
*   **Inmutabilidad PDF:** Si una nómina está en `t_cierres_nomina`, el PDF se regenera priorizando los valores monetarios históricos fijos de la base de datos.