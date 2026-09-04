# Mapa de Contexto Arquitectónico - UNIFIKA Nómina Cloud

*   **Infraestructura:** Frontend en React+Vite (Vercel). Backend en Python+FastAPI (Render)[cite: 5]. Enrutamiento Resend con BCC[cite: 5].
*   **Entidades Core:** `m_empleados` (Maestra), `t_novedades` (Transaccional Híbrida)[cite: 5], `t_ausentismos` (Rutas Storage), `t_cierres_nomina` (Candados de inmutabilidad).
*   **Fases 1 a 6:** COMPLETADAS (Autenticación, Motor Salarial, Dashboards, Históricos).
*   **Fase 7:** COMPLETADA (Motor de Ausentismos, Storage Médico RLS, Deducción SLN).
*   **Fase 8 (ACTUAL): Motor PILA y Seguridad Social**
    *   Algoritmo de fragmentación de IBC y generación stateless del Archivo Plano (TXT).
    *   Homologación estricta de catálogos MinSalud (EPS, AFP, ARL, CCF).
    *   Gateway Operador: Integración para carga masiva y validación.