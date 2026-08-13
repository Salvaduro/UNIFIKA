# Reglas Inmutables para Antigravity (IA)

1.  **Transacciones Envenenadas:** 
    *   Toda transacción a BD debe estar en un bloque `try-except` con `db.rollback()`. 
    *   NUNCA retornes `HTTP 200 OK` si hubo un rollback. Debes lanzar `raise HTTPException`.
2.  **Arquitectura Stateless (Cero Disco):**
    *   Prohibido usar `os.path` para guardar imágenes, PDFs o logs en el servidor.
    *   Los PDFs se generan en un buffer de memoria (`io.BytesIO`) y se adjuntan directamente a Resend o se envían al cliente.
3.  **Fuente de la Verdad (Master Data):**
    *   Al clonar nóminas (pre-liquidación), PROHIBIDO copiar valores financieros ciegamente del periodo anterior.
    *   El `salario_base`, `auxilio_transporte` y reglas de `salario_especie` (solo para "empleado interno") deben extraerse SIEMPRE de `m_empleados` en tiempo real.
4.  **Cálculos Financieros Obligatorios (DRY):**
    *   Antes de ejecutar un `db.add()` en `t_novedades`, el registro debe pasar obligatoriamente por la calculadora interna centralizada para poblar deducciones y totales (`ibc_pila`, `salud_4`, `pension_4`, etc.).
5.  **Control de Versiones (Ramas):**
    *   Los desarrollos nuevos se hacen en ramas aisladas (`git checkout -b feature-name`). Prohibido hacer push directo a `main` durante la etapa de experimentación.