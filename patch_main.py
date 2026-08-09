import sys

with open('nomina-cloud-backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject imports
import_insert = '''
import calendar
import holidays
import uuid
'''
content = content.replace('import datetime\n', 'import datetime\n' + import_insert)

content = content.replace('from typing import List, Dict, Any, Union', 'from typing import List, Dict, Any, Union, Optional, Tuple')
content = content.replace('from fastapi import FastAPI, Depends, Body, HTTPException', 'from fastapi import FastAPI, Depends, Body, HTTPException, Request')

# 2. Inject helpers
helpers_insert = '''
co_holidays = holidays.CO()

def is_business_day(d: datetime.date) -> bool:
    return d.weekday() < 5 and d not in co_holidays

def add_business_days(start_date: datetime.date, days: int) -> datetime.date:
    current = start_date
    step = 1 if days > 0 else -1
    remaining = abs(days)
    
    while remaining > 0:
        current += datetime.timedelta(days=step)
        if is_business_day(current):
            remaining -= 1
    return current

def obtener_ultimo_dia_mes(year: int, month: int) -> datetime.date:
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, last_day)

def obtener_nombre_mes(mes_num: int) -> str:
    meses = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    return meses[mes_num]

def calcular_fechas_ciclo(fecha_base: datetime.date) -> Optional[Tuple[str, str, str]]:
    year = fecha_base.year
    month = fecha_base.month
    
    corte_15_actual = datetime.date(year, month, 15)
    corte_fin_actual = obtener_ultimo_dia_mes(year, month)
    
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
        
    corte_15_anterior = datetime.date(prev_year, prev_month, 15)
    corte_fin_anterior = obtener_ultimo_dia_mes(prev_year, prev_month)
    
    if fecha_base == add_business_days(corte_15_actual, -2):
        return ('PRELIQUIDAR', f"{obtener_nombre_mes(month)} {year}", '1')
        
    if fecha_base == add_business_days(corte_fin_actual, -2):
        return ('PRELIQUIDAR', f"{obtener_nombre_mes(month)} {year}", '2')
        
    if fecha_base == add_business_days(corte_15_actual, 3):
        return ('CERRAR', f"{obtener_nombre_mes(month)} {year}", '1')
        
    if fecha_base == add_business_days(corte_fin_anterior, 3):
        return ('CERRAR', f"{obtener_nombre_mes(prev_month)} {prev_year}", '2')
        
    return None
'''
content = content.replace('\ndef formatear_periodo(valor):', helpers_insert + '\ndef formatear_periodo(valor):')

# 3. Inject Endpoint
endpoint_insert = '''
@app.post("/api/v1/cron/procesar-ciclo")
def procesar_ciclo(request: Request, dry_run: bool = False, db: Session = Depends(get_db)):
    cron_secret_header = request.headers.get("X-Cron-Secret")
    cron_secret_env = os.environ.get("CRON_SECRET")
    
    if not cron_secret_env or cron_secret_header != cron_secret_env:
        raise HTTPException(status_code=403, detail="Forbidden. Invalid CRON_SECRET.")

    target_date_str = request.query_params.get("date")
    if target_date_str:
        fecha_base = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        fecha_base = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date()
        
    resultado = calcular_fechas_ciclo(fecha_base)
    if not resultado:
        return {"status": "success", "message": f"No hay acciones de ciclo programadas para hoy ({fecha_base})."}
        
    accion, periodo_liq, quincena_pago = resultado
    acciones_simuladas = []
    
    try:
        if accion == 'PRELIQUIDAR':
            activos = db.query(models.Empleado).filter(
                models.Empleado.estado_empleado == 'ACTIVO'
            ).all()
            
            if not activos:
                return {"status": "success", "message": "No hay empleados activos para pre-liquidar."}
                
            nuevas_novedades = []
            empleadores_afectados = set()
            
            for emp in activos:
                ultima_nov = db.query(models.Novedad).filter(
                    models.Novedad.id_contrato == emp.id_contrato
                ).order_by(models.Novedad.created_at.desc()).first()
                
                if ultima_nov:
                    nueva_nov = models.Novedad(
                        id_novedad=str(uuid.uuid4()),
                        id_contrato=emp.id_contrato,
                        periodo_liq=periodo_liq,
                        quincena_pago=quincena_pago,
                        generar_nomina=True,
                        hed=0, hen=0, hedf=0, henf=0, rn=0, rdn=0, rnf=0,
                        dias_vacaciones=0, dias_incapacidad=0, prestamos=0,
                        dias_laborados=ultima_nov.dias_laborados,
                        horas_laboradas=ultima_nov.horas_laboradas,
                        prima_calc=ultima_nov.prima_calc,
                        observaciones="Pre-liquidación automática"
                    )
                else:
                    nueva_nov = models.Novedad(
                        id_novedad=str(uuid.uuid4()),
                        id_contrato=emp.id_contrato,
                        periodo_liq=periodo_liq,
                        quincena_pago=quincena_pago,
                        generar_nomina=True,
                        observaciones="Pre-liquidación automática inicial"
                    )
                
                nuevas_novedades.append(nueva_nov)
                if dry_run:
                    acciones_simuladas.append({
                        "accion": "CREAR_NOVEDAD",
                        "id_contrato": emp.id_contrato,
                        "periodo": periodo_liq,
                        "quincena": quincena_pago
                    })
                
                if emp.aportante and emp.aportante.email:
                    empleadores_afectados.add(emp.aportante.email)
                
            if not dry_run:
                db.bulk_save_objects(nuevas_novedades)
                auditoria = models.AuditoriaLog(
                    usuario_email="SISTEMA_CRON",
                    rol_usuario="SISTEMA",
                    tipo_accion="PRELIQUIDACION_MASIVA",
                    detalles={"periodo": periodo_liq, "quincena": quincena_pago, "empleados_afectados": len(nuevas_novedades)}
                )
                db.add(auditoria)
                db.commit()
            
            mail_from = os.environ.get("MAIL_FROM", "nomina@unifika.co")
            if resend.api_key and not dry_run:
                for email_aportante in empleadores_afectados:
                    if email_aportante:
                        try:
                            resend.Emails.send({
                                "from": mail_from,
                                "to": str(email_aportante),
                                "subject": f"Pre-liquidación de Nómina Lista - {periodo_liq}",
                                "html": f"<p>La pre-liquidación para la quincena {quincena_pago} del periodo {periodo_liq} ya se encuentra generada y lista para su revisión en UNIFIKA Nómina Cloud.</p>"
                            })
                        except Exception as e:
                            logger.error(f"Error enviando correo de pre-liquidación a {email_aportante}: {e}")
            elif dry_run:
                for email_aportante in empleadores_afectados:
                    if email_aportante:
                        acciones_simuladas.append({
                            "accion": "ENVIAR_CORREO",
                            "destinatario": email_aportante
                        })
            
            if dry_run:
                return {"status": "success", "message": f"SIMULACIÓN: Pre-liquidación generada para {len(nuevas_novedades)} contratos.", "acciones_simuladas": acciones_simuladas}
            return {"status": "success", "message": f"Pre-liquidación generada para {len(nuevas_novedades)} contratos."}
            
        elif accion == 'CERRAR':
            query_pendientes = text("""
                SELECT n.id_contrato 
                FROM t_novedades n
                LEFT JOIN t_cierres_nomina c ON n.id_contrato = c.id_contrato 
                                            AND n.periodo_liq = c.periodo_liq 
                                            AND n.quincena_pago = c.quincena_pago
                WHERE n.periodo_liq = :periodo
                  AND n.quincena_pago = :quincena
                  AND c.id_cierre IS NULL
            """)
            pendientes = db.execute(query_pendientes, {"periodo": periodo_liq, "quincena": quincena_pago}).fetchall()
            
            cierres = []
            for row in pendientes:
                cierres.append(models.CierreNomina(
                    id_cierre=str(uuid.uuid4()),
                    id_contrato=row[0],
                    periodo_liq=periodo_liq,
                    quincena_pago=quincena_pago,
                    cerrado_por="SISTEMA_CRON"
                ))
                if dry_run:
                    acciones_simuladas.append({
                        "accion": "CERRAR_NOMINA",
                        "id_contrato": row[0],
                        "periodo": periodo_liq,
                        "quincena": quincena_pago
                    })
                
            if cierres:
                if not dry_run:
                    db.bulk_save_objects(cierres)
                    auditoria = models.AuditoriaLog(
                        usuario_email="SISTEMA_CRON",
                        rol_usuario="SISTEMA",
                        tipo_accion="CIERRE_AUTOMATICO",
                        detalles={"periodo": periodo_liq, "quincena": quincena_pago, "cierres_realizados": len(cierres)}
                    )
                    db.add(auditoria)
                    db.commit()
            
            if dry_run:
                return {"status": "success", "message": f"SIMULACIÓN: Cierre automático aplicado a {len(cierres)} contratos.", "acciones_simuladas": acciones_simuladas}
            return {"status": "success", "message": f"Cierre automático aplicado a {len(cierres)} contratos."}
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error en procesar-ciclo ({accion}): {e}")
        raise HTTPException(status_code=500, detail="Error en procesamiento masivo de ciclo.")
'''
content = content + '\n' + endpoint_insert

with open('nomina-cloud-backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched successfully!')
