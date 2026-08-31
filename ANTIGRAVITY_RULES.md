# Reglas Inmutables para Antigravity (IA)

1.  **Transacciones Envenenadas:** 
    *   Toda transacción a BD debe estar en un bloque `try-except` con `db.rollback()`. 
    *   NUNCA retornes `HTTP 200 OK` si hubo un rollback. Debes lanzar `raise HTTPException`.
2.  **Arquitectura Stateless y PDFs Híbridos:**
    *   Prohibido usar `os.path` para guardar archivos en el servidor. Los PDFs se generan en `io.BytesIO`.
    *   **Regla de Históricos:** Al regenerar PDFs históricos, usa el "Patrón Híbrido". Calcula el desglose, pero SOBREESCRIBE obligatoriamente deducciones y totales finales usando los datos de la base de datos para proteger la inmutabilidad.
3.  **Regla de Tareas en Segundo Plano (BackgroundTasks):**
    *   ¡CRÍTICO! Cuando uses `BackgroundTasks` de FastAPI, la función en segundo plano NO debe usar la sesión de base de datos (`db: Session`) inyectada por el endpoint. Debe instanciar su propia sesión (`SessionLocal()`) y cerrarla en un bloque `finally`.
4.  **Fuente de la Verdad (Master Data):**
    *   El `salario_base` y reglas fijas deben extraerse SIEMPRE de `m_empleados` en tiempo real, no copiarse ciegamente del periodo anterior.
5.  **Cálculos Financieros Obligatorios (DRY):**
    *   Antes de ejecutar un `db.add()` en `t_novedades`, el registro debe pasar obligatoriamente por la calculadora interna para poblar `ibc_pila`, `salud_4`, `pension_4`, etc.