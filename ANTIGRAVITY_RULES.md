# Reglas Inmutables para Antigravity e IA (Actualizado Fase 8)

1. **Transacciones Envenenadas:** Todo a BD debe estar en `try-except` con `db.rollback()`[cite: 4].
2. **Arquitectura Stateless y PDFs Híbridos:** Cero archivos físicos. El cálculo histórico debe SOBREESCRIBIR deducciones/totales con la BD para inmutabilidad[cite: 4].
3. **Matemática Financiera:** Las validaciones de topes legales DEBEN excluir estrictamente los bonos no constitutivos de salario (`vlr_bono`)[cite: 4]. 
4. **Enrutamiento de Correos:** Enviar siempre al correo oficial del cliente, ignorando el `current_user`, con copia oculta a auditoría[cite: 4].
5. **Reglas de UI:** Prohibido el uso de alertas nativas. Usar exclusivamente Toasts y Modales[cite: 4].
6. **Fragmentación PILA (Inmutabilidad de IBC):** Cualquier novedad de ausentismo (IGE, VAC, SLN) DEBE fragmentar matemáticamente el IBC en líneas independientes dentro del archivo TXT[cite: 4]. Prohibido mezclar IBC de días laborados con IBC de ausentismos.
7. **Transaccionalidad Storage:** Para archivos físicos (Supabase), primero se interactúa con el bucket (Upload/Delete). Solo si el bucket responde con éxito, se ejecuta el commit en PostgreSQL.