import { useState, useEffect } from 'react';
import './App.css';
import logoUrl from './assets/Logo.png';

const generarPeriodos = () => {
  const periodos = [];
  const fechaActual = new Date();
  const añoActual = fechaActual.getFullYear();
  const mesActual = fechaActual.getMonth(); // Enero es 0, Diciembre es 11
  const opcionesMes = { month: 'long' };
  
  // Iterar desde el mes 0 (Enero) hasta el mes actual + 1
  for (let i = 0; i <= mesActual + 1; i++) {
    // Si estamos en diciembre (11), i=12 pasará automáticamente a Enero del próximo año
    const fecha = new Date(añoActual, i, 1);
    const mes = new Intl.DateTimeFormat('es-ES', opcionesMes).format(fecha).toUpperCase();
    const año = fecha.getFullYear();
    periodos.push(`${mes} ${año}`);
  }
  
  return periodos.reverse(); // Muestra el mes más reciente de primero
};

function App() {
  // ==========================================
  // BLOQUE 1: MANEJO DE ESTADOS (FORMULARIO Y UI)
  // ==========================================
  const [formData, setFormData] = useState({
    ID_CONTRATO: 'EMP-001',
    SALARIO_BASE: 1750905,
    DIAS_LABORADOS: 15,
    ES_SMLV: 'SI',
    CON_BONO: 'NO',
    TIENE_AUX: 'SI',
    TIPO_CONTRATO: 'TIEMPO COMPLETO',
    ESTADO_EMPLEADO: 'ACTIVO',
    PERIODO_PAGO: 'QUINCENAL',
    SALARIO_ESPECIE: '',
    VLR_BONO: '',
    CON_PRESTAMO: 'NO',
    PRESTAMOS: '',
    DIAS_VACACIONES: 0,
    DIAS_INCAPACIDAD: 0,
    REPORTAR_EXTRAS: 'NO',
    HED: 0,
    HEN: 0,
    HEDF: 0,
    HENF: 0,
    RN: 0,
    RDN: 0,
    RNF: 0,
    EPS: '',
    FONDO_PENSIONES: '',
  });

  const [isLoading, setIsLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);

  // Estados del Periodo
  const [periodoLiq, setPeriodoLiq] = useState('JUNIO 2026');
  const [quincenaPago, setQuincenaPago] = useState('1');
  const [observaciones, setObservaciones] = useState("");
  const [mostrarNota, setMostrarNota] = useState(false);

  // Estados CRM
  const [empleadorId, setEmpleadorId] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [empleadosEncontrados, setEmpleadosEncontrados] = useState([]);
  const [selectedEmpleadoId, setSelectedEmpleadoId] = useState('');
  const [isContractOpen, setIsContractOpen] = useState(false);

  // Efecto para auto-calcular el periodo actual
  useEffect(() => {
    const date = new Date();
    const months = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"];
    const currentMonth = months[date.getMonth()];
    const currentYear = date.getFullYear();
    setPeriodoLiq(`${currentMonth} ${currentYear}`);

    if (date.getDate() <= 15) {
      setQuincenaPago('1');
    } else {
      setQuincenaPago('2');
    }
  }, []);

  // Efecto para sincronizar la Quincena con el Periodo de Pago del contrato
  useEffect(() => {
    const isMensual = formData.PERIODO_PAGO?.toUpperCase() === 'MENSUAL' || formData.PERIODO_PAGO?.toUpperCase() === 'MENSUALIDAD';
    if (isMensual) {
      setQuincenaPago('M');
    } else {
      if (quincenaPago === 'M') {
        const date = new Date();
        setQuincenaPago(date.getDate() <= 15 ? '1' : '2');
      }
    }
  }, [formData.PERIODO_PAGO]);

  const SMLV_ACTUAL = 1750905;

  // ==========================================
  // BLOQUE 2: CONSULTA CRM Y AUTOCOMPLETADO
  // ==========================================
  const autocompletarFormulario = (empleado) => {
    setFormData((prev) => {
      const diasPorDefecto = empleado.PERIODO_PAGO?.toLowerCase() === 'quincenal' ? 15 : 30;
      return {
        ...prev,
        ID_CONTRATO: empleado.ID_CONTRATO || prev.ID_CONTRATO,
        SALARIO_BASE: empleado.SALARIO_BASE || prev.SALARIO_BASE,
        SALARIO_ESPECIE: empleado.SALARIO_ESPECIE || '',
        ES_SMLV: empleado.ES_SMLV || prev.ES_SMLV,
        CON_BONO: empleado.CON_BONO || prev.CON_BONO,
        TIENE_AUX: empleado.TIENE_AUX || prev.TIENE_AUX,
        TIPO_CONTRATO: empleado.TIPO_CONTRATO || prev.TIPO_CONTRATO,
        CARGO_DESEMPENEADO: empleado.CARGO_DESEMPENEADO || '',
        PERIODO_PAGO: empleado.PERIODO_PAGO || prev.PERIODO_PAGO,
        DIAS_LABORADOS: diasPorDefecto,
        VLR_BONO: empleado.VLR_BONO || '',
        EPS: empleado.EPS || '',
        FONDO_PENSIONES: empleado['FONDO DE PENSIONES'] || '',
      };
    });
  };

  const handleSearchEmpleador = async () => {
    if (!empleadorId.trim()) return;

    setIsSearching(true);
    setError(null);
    setSearchError(null);
    setEmpleadosEncontrados([]);
    setSelectedEmpleadoId('');

    // Limpiar el formulario actual
    setFormData({
      ID_CONTRATO: '',
      SALARIO_BASE: SMLV_ACTUAL,
      DIAS_LABORADOS: 15,
      ES_SMLV: 'SI',
      CON_BONO: 'NO',
      TIENE_AUX: 'SI',
      TIPO_CONTRATO: 'TIEMPO COMPLETO',
      CARGO_DESEMPENEADO: '',
      ESTADO_EMPLEADO: 'ACTIVO',
      PERIODO_PAGO: 'QUINCENAL',
      SALARIO_ESPECIE: '',
      VLR_BONO: '',
      CON_PRESTAMO: 'NO',
      PRESTAMOS: '',
      DIAS_VACACIONES: 0,
      DIAS_INCAPACIDAD: 0,
      REPORTAR_EXTRAS: 'NO',
      HED: 0,
      HEN: 0,
      HEDF: 0,
      HENF: 0,
      RN: 0,
      RDN: 0,
      RNF: 0,
      EPS: '',
      FONDO_PENSIONES: '',
    });

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/empleador/${empleadorId}/empleados`);

      if (!response.ok) {
        let isDynamicError = false;

        if (response.status !== 404) {
          try {
            const errorData = await response.json();
            if (errorData && errorData.detail) {
              setSearchError(<>{errorData.detail}</>);
              isDynamicError = true;
            }
          } catch (e) {
            // Ignorar error al leer JSON
          }
        }

        if (!isDynamicError) {
          setSearchError(<>No se encuentra registro en nuestro sistema. <br />Por favor, comunícate al Tel. 333 6025560 para brindarte atención.</>);
        }

        setSelectedEmpleadoId('');
        setResultado(null);
        return;
      }

      const data = await response.json();

      if (data.status === 'success' && data.data && data.data.length > 0) {
        if (data.data.length === 1) {
          // Un solo empleado, autocompletar
          const emp = data.data[0];
          setSelectedEmpleadoId(emp.ID_CONTRATO);
          autocompletarFormulario(emp);
        }
        setEmpleadosEncontrados(data.data);
      } else {
        setError('No se encontraron empleados para este ID.');
      }
    } catch (err) {
      console.error('Error al buscar empleador:', err);
      setSearchError(<>No se encuentra registro en nuestro sistema. <br />Por favor, comunícate al Tel. 333 6025560 para brindarte atención.</>);
      setSelectedEmpleadoId('');
      setResultado(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectEmpleado = (e) => {
    const selectedId = e.target.value;
    setSelectedEmpleadoId(selectedId);

    if (selectedId) {
      const empleado = empleadosEncontrados.find(emp => emp.ID_CONTRATO === selectedId);
      if (empleado) {
        autocompletarFormulario(empleado);
      }
    }
  };

  // ==========================================
  // BLOQUE 3: REGLAS DE NEGOCIO (EVENTOS INPUT)
  // ==========================================
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      let newValue = value;

      if (name === 'DIAS_LABORADOS') {
        const maxDias = prev.PERIODO_PAGO?.toLowerCase() === 'quincenal' ? 15 : 30;
        const parsedValue = parseFloat(value);
        if (!isNaN(parsedValue) && parsedValue > maxDias) {
          newValue = maxDias;
        }
      }

      const newData = { ...prev, [name]: newValue };

      // Regla: Tiempo Parcial fuerza SMLV a NO
      if (name === 'TIPO_CONTRATO' && value === 'TIEMPO PARCIAL') {
        newData.ES_SMLV = 'NO';
        newData.SALARIO_BASE = ''; // Limpiar el salario mínimo por defecto
      }

      // Regla: Limpiar SALARIO_ESPECIE si no es Empleado Interno
      if (name === 'TIPO_CONTRATO' && value?.toLowerCase().trim() !== 'empleado interno') {
        newData.SALARIO_ESPECIE = '';
      }

      // Autocompletar y bloquear si se selecciona SMLV
      if (name === 'ES_SMLV') {
        if (value === 'SI') {
          newData.SALARIO_BASE = SMLV_ACTUAL;
          newData.CON_BONO = 'NO'; // Exclusión: el bono no aplica
          newData.VLR_BONO = '';
        } else {
          newData.SALARIO_BASE = '';
        }
      }

      // Regla: Limpiar VLR_BONO si el bono es NO
      if (name === 'CON_BONO' && value === 'NO') {
        newData.VLR_BONO = '';
      }

      // Regla: Limpiar PRESTAMOS si no hay préstamo
      if (name === 'CON_PRESTAMO' && value === 'NO') {
        newData.PRESTAMOS = '';
      }

      // Regla: Limpiar EXTRAS si no reporta
      if (name === 'REPORTAR_EXTRAS' && value === 'NO') {
        newData.HED = 0;
        newData.HEN = 0;
        newData.HEDF = 0;
        newData.HENF = 0;
        newData.RN = 0;
        newData.RDN = 0;
        newData.RNF = 0;
      }

      return newData;
    });
  };

  // ==========================================
  // BLOQUE 4: LIQUIDACIÓN DE NÓMINA (SUBMIT)
  // ==========================================
  const handleLiquidarNomina = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResultado(null);
    try {
      const payload = [{
        ...formData,
        SALARIO_BASE: formData.SALARIO_BASE.toString(),
        DIAS_LABORADOS: Number(formData.DIAS_LABORADOS),
        SALARIO_ESPECIE: formData.SALARIO_ESPECIE ? Number(formData.SALARIO_ESPECIE) : 0,
        VLR_BONO: formData.VLR_BONO ? Number(formData.VLR_BONO) : 0,
        PRESTAMOS: formData.PRESTAMOS ? Number(formData.PRESTAMOS) : 0,
        DIAS_VACACIONES: formData.DIAS_VACACIONES ? Number(formData.DIAS_VACACIONES) : 0,
        DIAS_INCAPACIDAD: formData.DIAS_INCAPACIDAD ? Number(formData.DIAS_INCAPACIDAD) : 0,
        HED: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.HED) : 0,
        HEN: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.HEN) : 0,
        HEDF: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.HEDF) : 0,
        HENF: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.HENF) : 0,
        RN: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.RN) : 0,
        RDN: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.RDN) : 0,
        RNF: formData.REPORTAR_EXTRAS === 'SI' ? Number(formData.RNF) : 0,
        EPS: formData.EPS,
        FONDO_PENSIONES: formData.FONDO_PENSIONES
      }];

      const response = await fetch('http://127.0.0.1:8000/api/v1/liquidar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data && data.length > 0) {
        setResultado(data[0]);
      } else {
        setError('No se recibieron datos de liquidación.');
      }

    } catch (error) {
      console.error('Error al liquidar nómina:', error);
      setError('Hubo un error al conectar con el servidor backend. Revisa que el servidor esté encendido.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGuardarHistorico = async () => {
    if (!resultado) return;
    setIsSaving(true);
    setSaveMessage(null);
    try {
      const empleadoOriginal = empleadosEncontrados.find(emp => emp.ID_CONTRATO === resultado.ID_CONTRATO) || {};
      const payloadCompleto = { ...empleadoOriginal, ...resultado };
      
      const payload = [payloadCompleto].map(empleado => ({
        ...empleado,
        PERIODO_LIQ: periodoLiq,
        QUINCENA_PAGO: quincenaPago,
        OBSERVACIONES: observaciones
      }));

      const response = await fetch('http://127.0.0.1:8000/api/v1/historico/guardar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
      }

      const data = await response.json();
      setSaveMessage({ type: 'success', text: data.message || 'Nómina guardada exitosamente.' });
    } catch (error) {
      console.error('Error al guardar histórico:', error);
      setSaveMessage({ type: 'error', text: 'Error al guardar la nómina en la base de datos.' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDescargarPDF = async () => {
    if (!resultado) return;
    setIsDownloading(true);
    try {
      const empleadoOriginal = empleadosEncontrados.find(emp => emp.ID_CONTRATO === resultado.ID_CONTRATO) || {};
      const payloadCompleto = { 
        ...empleadoOriginal, 
        ...resultado,
        PERIODO_LIQ: periodoLiq,
        QUINCENA_PAGO: quincenaPago,
        OBSERVACIONES: observaciones
      };

      const response = await fetch('http://127.0.0.1:8000/api/v1/comprobante/generar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payloadCompleto),
      });

      if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = url;
      
      const periodoFormateado = periodoLiq ? periodoLiq.replace(/\s+/g, '_').toUpperCase() : 'SIN_PERIODO';
      const quincenaFormateada = quincenaPago ? quincenaPago.replace(/\s+/g, '_').toUpperCase() : '';
      
      let sufijoQuincena = quincenaFormateada;
      if (quincenaFormateada === "1") {
          sufijoQuincena = "Q1";
      } else if (quincenaFormateada === "2") {
          sufijoQuincena = "Q2";
      }
      
      const idContrato = resultado.ID_EMPLEADO || resultado.ID_CONTRATO || 'SIN_CONTRATO';
      const nombreArchivo = sufijoQuincena 
        ? `Desprendible_${idContrato}_${periodoFormateado}_${sufijoQuincena}.pdf`
        : `Desprendible_${idContrato}_${periodoFormateado}.pdf`;

      a.download = nombreArchivo;
      document.body.appendChild(a);
      a.click();

      a.remove();
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Error al descargar PDF:', error);
      alert('Hubo un error al generar el PDF. Por favor, intenta de nuevo.');
    } finally {
      setIsDownloading(false);
    }
  };

  // ==========================================
  // BLOQUE 5: RENDERIZADO UI (COMPONENTES)
  // ==========================================
  return (
    <div className="min-h-screen bg-slate-50 font-sans flex flex-col">
      <nav className="bg-unifika-primary shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-24 py-2 items-center">
            <div className="flex items-center space-x-3">
              <img src={logoUrl} alt="Unifika Logo" className="h-20 w-auto drop-shadow-md" />
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-slate-300 text-sm hidden md:block font-medium">
                Portal de Administración
              </div>
              <div className="h-9 w-9 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-white font-semibold cursor-pointer hover:bg-slate-600 transition-colors">
                AD
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {/* Header Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-unifika-primary tracking-tight">
            Liquidación de Nómina
          </h1>
          <p className="mt-2 text-base text-slate-500">
            Ingresa la identificación del Empleador para consultar los contratos activos y liquidar la nómina del periodo actual.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start w-full mb-12">
          {/* Formulario Section */}
          <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden">
            <div className="px-8 py-6 border-b border-slate-100 bg-white">
              <h3 className="text-lg font-bold text-slate-800 flex items-center">
                <svg className="w-5 h-5 mr-2 text-unifika-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                Detalles de la Relación Laboral / Contrato
              </h3>
            </div>

            <div className="px-8 pt-6">
              {/* Bloque: Parámetros del Periodo */}
              <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 mb-6">
                <h4 className="text-sm font-bold text-slate-700 mb-3 uppercase tracking-wide">Parámetros del Periodo</h4>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Mes / Año</label>
                    <select
                      value={periodoLiq}
                      onChange={(e) => setPeriodoLiq(e.target.value)}
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                    >
                      {generarPeriodos().map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Ciclo de Pago</label>
                    <select
                      value={quincenaPago}
                      onChange={(e) => setQuincenaPago(e.target.value)}
                      disabled={formData.PERIODO_PAGO?.toUpperCase() === 'MENSUAL' || formData.PERIODO_PAGO?.toUpperCase() === 'MENSUALIDAD'}
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none disabled:bg-slate-100 disabled:text-slate-500"
                    >
                      {(formData.PERIODO_PAGO?.toUpperCase() !== 'MENSUAL' && formData.PERIODO_PAGO?.toUpperCase() !== 'MENSUALIDAD') && (
                        <>
                          <option value="1">Primera Quincena (Q1)</option>
                          <option value="2">Segunda Quincena (Q2)</option>
                        </>
                      )}
                      {(formData.PERIODO_PAGO?.toUpperCase() === 'MENSUAL' || formData.PERIODO_PAGO?.toUpperCase() === 'MENSUALIDAD') && (
                        <option value="M">Mensualidad Completa (M)</option>
                      )}
                    </select>
                  </div>
                </div>
                
                {/* Progressive Disclosure para Observaciones */}
                <div className="mt-4 pt-4 border-t border-slate-200">
                  <button
                    type="button"
                    onClick={() => setMostrarNota(!mostrarNota)}
                    className="text-xs font-semibold text-slate-500 hover:text-unifika-primary flex items-center transition-colors outline-none"
                  >
                    <svg className={`w-4 h-4 mr-1 transform transition-transform ${mostrarNota ? 'rotate-45 text-slate-400' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
                    {mostrarNota ? 'Ocultar observación' : 'Añadir observación (Opcional)'}
                  </button>
                  
                  {mostrarNota && (
                    <div className="mt-3 animate-fade-in">
                      <textarea
                        value={observaciones}
                        onChange={(e) => setObservaciones(e.target.value)}
                        placeholder="Escribe aquí cualquier anotación para el periodo (ej. Descuento autorizado por gerencia)..."
                        className="w-full px-4 py-3 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-700 text-sm outline-none resize-none h-20 shadow-inner"
                      ></textarea>
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 mb-6">
                <h4 className="text-sm font-bold text-slate-700 mb-3 uppercase tracking-wide">Búsqueda ID Empleador</h4>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <input
                      type="text"
                      value={empleadorId}
                      onChange={(e) => {
                        setEmpleadorId(e.target.value);
                        setSearchError(null);
                      }}
                      placeholder="ID Empleador"
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSearchEmpleador}
                    disabled={isSearching || !empleadorId.trim()}
                    className={`px-6 py-2.5 font-bold rounded-xl transition-all flex items-center justify-center min-w-[160px] ${isSearching || !empleadorId.trim()
                      ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                      : 'bg-unifika-primary text-white hover:bg-slate-800 shadow-sm'
                      }`}
                  >
                    {isSearching ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Buscando...
                      </>
                    ) : 'Consultar'}
                  </button>
                </div>

                {searchError && (
                  <div className="bg-red-50 border-l-4 border-red-500 p-4 text-red-700 mt-4 rounded">
                    {searchError}
                  </div>
                )}

                {empleadosEncontrados.length > 1 && (
                  <div className="mt-4 animate-fade-in border-t border-slate-200 pt-4">
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Seleccionar Empleado a Liquidar:</label>
                    <select
                      value={selectedEmpleadoId}
                      onChange={handleSelectEmpleado}
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                    >
                      <option value="">-- Seleccione un empleado --</option>
                      {empleadosEncontrados.map((empleado) => (
                        <option key={empleado.ID_CONTRATO} value={empleado.ID_CONTRATO}>
                          {empleado.NOMBRE_EMPLEADO} ({empleado.TIPO_CONTRATO}) - {empleado.ID_EMPLEADO}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {empleadosEncontrados.length === 1 && (
                  <div className="mt-4 animate-fade-in border-t border-slate-200 pt-4">
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Empleado a Liquidar:</label>
                    <input
                      type="text"
                      readOnly
                      value={`${empleadosEncontrados[0].NOMBRE_EMPLEADO} (${empleadosEncontrados[0].TIPO_CONTRATO}) - ${empleadosEncontrados[0].ID_EMPLEADO}`}
                      className="w-full px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-slate-700 font-medium outline-none cursor-not-allowed"
                    />
                  </div>
                )}
              </div>
            </div>

            {selectedEmpleadoId && (
              <form onSubmit={handleLiquidarNomina} className="px-8 pb-8 pt-2 animate-fade-in-up">

                {/* SECCIÓN 1: REPORTE DE NOVEDADES */}
                <div className="mb-8 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
                    <h3 className="text-lg font-bold text-slate-800">Reporte de Novedades</h3>
                    <p className="text-sm text-slate-500 mt-1">Campos editables para el periodo actual</p>
                  </div>

                  <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                      {/* Días Laborados */}
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Días Laborados</label>
                        <input type="number" name="DIAS_LABORADOS" value={formData.DIAS_LABORADOS} onChange={handleInputChange} min="0" max={formData.PERIODO_PAGO?.toLowerCase() === 'quincenal' ? 15 : 30} step="any" className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none" required />
                      </div>

                      {/* Días Vacaciones */}
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Días Vacaciones</label>
                        <input type="number" name="DIAS_VACACIONES" value={formData.DIAS_VACACIONES} onChange={handleInputChange} min="0" max="30" step="any" className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none" required />
                      </div>

                      {/* Días Incapacidad */}
                      <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-2">Días Incapacidad</label>
                        <input type="number" name="DIAS_INCAPACIDAD" value={formData.DIAS_INCAPACIDAD} onChange={handleInputChange} min="0" max="30" step="any" className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none" required />
                      </div>
                    </div>

                    {/* NOVEDADES: EXTRAS Y PRÉSTAMOS */}
                    <div className="mt-6 pt-6 border-t border-slate-100">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                        {/* HORAS EXTRAS */}
                        <div className="bg-slate-50 rounded-xl border border-slate-200 p-5">
                          <h4 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wide">Horas Extras y Recargos</h4>
                          <div className="mb-4">
                            <label className="block text-sm font-semibold text-slate-700 mb-2">¿Reportar Extras y Recargos?</label>
                            <select name="REPORTAR_EXTRAS" value={formData.REPORTAR_EXTRAS} onChange={handleInputChange} className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none">
                              <option value="NO">No</option>
                              <option value="SI">Sí</option>
                            </select>
                          </div>

                          {formData.REPORTAR_EXTRAS === 'SI' && (
                            <div className="grid grid-cols-2 gap-4 animate-fade-in pt-2">
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">H. Extras Diurnas</label>
                                <input type="number" name="HED" value={formData.HED} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">H. Extras Nocturnas</label>
                                <input type="number" name="HEN" value={formData.HEN} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">H. Extras Diurnas Festivas</label>
                                <input type="number" name="HEDF" value={formData.HEDF} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">H. Extras Nocturnas Festivas</label>
                                <input type="number" name="HENF" value={formData.HENF} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Recargos Nocturnos</label>
                                <input type="number" name="RN" value={formData.RN} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Recargos Diurnos Festivos</label>
                                <input type="number" name="RDN" value={formData.RDN} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                              <div>
                                <label className="block text-xs font-semibold text-slate-700 mb-1">Recargos Nocturnos Festivos</label>
                                <input type="number" name="RNF" value={formData.RNF} onChange={handleInputChange} min="0" step="any" className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none" />
                              </div>
                            </div>
                          )}
                        </div>

                        {/* PRÉSTAMOS */}
                        <div className="bg-slate-50 rounded-xl border border-slate-200 p-5">
                          <h4 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wide">Deducciones y Préstamos</h4>
                          <div className="flex flex-col gap-4">
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">¿Descontar cuota de préstamo?</label>
                              <select name="CON_PRESTAMO" value={formData.CON_PRESTAMO} onChange={handleInputChange} className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none">
                                <option value="NO">No</option>
                                <option value="SI">Sí</option>
                              </select>
                            </div>
                            {formData.CON_PRESTAMO === 'SI' && (
                              <div className="animate-fade-in pt-2">
                                <label className="block text-sm font-semibold text-slate-700 mb-2">Valor del Préstamo ($)</label>
                                <input
                                  type="number"
                                  name="PRESTAMOS"
                                  value={formData.PRESTAMOS}
                                  onChange={handleInputChange}
                                  className="w-full px-4 py-2.5 bg-rose-50 border border-rose-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-rose-400 focus:border-rose-400 transition-all text-slate-900 outline-none shadow-sm"
                                  required
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* SECCIÓN 2: TÉRMINOS ACTUALES DEL CONTRATO (Colapsable) */}
                <div className="mb-8 border border-slate-200 rounded-xl overflow-hidden shadow-sm bg-white">
                  <button
                    type="button"
                    onClick={() => setIsContractOpen(!isContractOpen)}
                    className="w-full px-6 py-4 bg-slate-100 hover:bg-slate-200 transition-colors flex justify-between items-center outline-none"
                  >
                    <div className="flex items-center text-left">
                      <svg className="w-5 h-5 mr-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                      <div>
                        <h3 className="text-base font-bold text-slate-700">Términos Actuales del Contrato</h3>
                      </div>
                    </div>
                    <svg className={`w-5 h-5 text-slate-500 transform transition-transform duration-300 ${isContractOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                  </button>

                  {isContractOpen && (
                    <div className="p-6 border-t border-slate-200 animate-fade-in">
                      <div className="mb-6 p-3 bg-amber-50/50 border border-amber-100 rounded-lg">
                        <p className="text-xs text-amber-700 italic flex items-start">
                          <svg className="w-4 h-4 mr-2 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                          Nota: Las condiciones contractuales provienen directamente del sistema maestro. Cualquier modificación requiere la elaboración de un "Otro Sí" al contrato y debe gestionarse a través de nuestros canales de atención.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* BLOQUE FIJO INICIAL (Siempre visible - Fila 1) */}
                        <div>
                          <label className="block text-sm font-semibold text-slate-700 mb-2">Cargo Desempeñado</label>
                          <input type="text" value={formData.CARGO_DESEMPENEADO} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                        </div>
                        <div>
                          <label className="block text-sm font-semibold text-slate-700 mb-2">Periodo de Pago</label>
                          <input type="text" value={formData.PERIODO_PAGO} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                        </div>

                        {/* RENDERIZADO CONDICIONAL BASADO EN SMLV */}
                        {formData.ES_SMLV?.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "") === 'si' ? (
                          <>
                            {/* CASO A: SMLV es SÍ (Estructura compacta de 2 filas) */}
                            {/* Fila 2 */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">¿Salario Mínimo?</label>
                              <input type="text" value={formData.ES_SMLV} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">Tiene Aux. Transporte</label>
                              <input type="text" value={formData.TIENE_AUX} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>
                          </>
                        ) : (
                          <>
                            {/* CASO B: SMLV es NO (Estructura completa de 4 filas) */}
                            {/* Fila 2 */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">¿Salario Mínimo?</label>
                              <input type="text" value={formData.ES_SMLV} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">Salario Base ($)</label>
                              <input type="text" value={formData.SALARIO_BASE} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>

                            {/* Fila 3 */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">¿Bono Salarial?</label>
                              <input type="text" value={formData.CON_BONO} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>
                            {formData.CON_BONO?.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "") === 'si' && (
                              <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-2">Valor del Bono ($)</label>
                                <input type="text" value={formData.VLR_BONO} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                              </div>
                            )}

                            {/* Fila 4 */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">Tiene Aux. Transporte</label>
                              <input type="text" value={formData.TIENE_AUX} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                            </div>
                            {formData.TIPO_CONTRATO?.toLowerCase().trim() === 'empleado interno' && (
                              <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-2">Salario en Especie ($)</label>
                                <input type="text" value={formData.SALARIO_ESPECIE} readOnly className="w-full px-4 py-2.5 bg-gray-50 text-gray-500 border border-slate-200 rounded-xl cursor-not-allowed outline-none" />
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="mt-8 p-4 bg-red-50/80 border-l-4 border-red-500 text-red-700 rounded-r-lg text-sm flex items-start animate-fade-in">
                    <svg className="w-5 h-5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
                    {error}
                  </div>
                )}

                <div className="mt-10 flex justify-end">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className={`inline-flex items-center justify-center px-8 py-3.5 font-bold text-slate-900 transition-all duration-300 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-unifika-accent ${isLoading ? 'bg-slate-200 text-slate-500 cursor-not-allowed' : 'bg-unifika-accent hover:bg-unifika-accent-hover hover:shadow-lg hover:-translate-y-0.5'}`}
                  >
                    {isLoading ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-slate-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Procesando...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Liquidar Nómina
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Sección de Resultados */}
          {selectedEmpleadoId && (
            <div className="lg:col-span-1 bg-white rounded-2xl shadow-md border border-slate-100 sticky top-28 h-auto overflow-hidden animate-fade-in-up">
              {resultado ? (
                <div className="transform transition-all animate-fade-in-up flex flex-col">
                  {/* Header Resultado */}
                  <div className="bg-gradient-to-r from-unifika-primary to-slate-800 px-6 py-5 text-white relative flex-shrink-0">
                    <div className="absolute top-0 right-0 -mt-6 -mr-6 w-32 h-32 bg-white opacity-5 rounded-full blur-2xl"></div>
                    <h3 className="text-lg font-bold mb-1 relative z-10 text-unifika-accent">Resumen de Liquidación</h3>
                    <p className="text-slate-100 text-sm font-semibold relative z-10 flex items-center mt-2 bg-black/20 p-2 rounded-lg">
                      <svg className="w-4 h-4 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                      Empleado: {empleadosEncontrados.find(e => e.ID_CONTRATO === resultado.ID_CONTRATO)?.NOMBRE_EMPLEADO || resultado.NOMBRE_EMPLEADO || resultado.ID_CONTRATO}
                    </p>
                  </div>

                  {/* Dos Columnas: Devengados y Deducciones */}
                  <div className="p-5 grid grid-cols-1 xl:grid-cols-2 gap-6">

                    {/* Columna Izquierda: Devengados */}
                    <div>
                      <h4 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3 border-b-2 border-slate-100 pb-2 flex items-center">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2"></span> Ingresos
                      </h4>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs sm:text-sm">
                          <span className="text-slate-600">Sueldo Básico</span>
                          <span className="font-medium text-slate-900">${(resultado.SUELDO_EFECTIVO_PAGADO || 0).toLocaleString('es-CO')}</span>
                        </div>
                        {resultado.SALARIO_ESPECIE_MES > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">En Especie</span>
                            <span className="font-medium text-slate-900">${resultado.SALARIO_ESPECIE_MES.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        <div className="flex justify-between text-xs sm:text-sm">
                          <span className="text-slate-600">Aux. Transp.</span>
                          <span className="font-medium text-slate-900">${(resultado.VAL_AUX_TTE || 0).toLocaleString('es-CO')}</span>
                        </div>
                        {resultado.VALOR_VACACIONES > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">Vacaciones</span>
                            <span className="font-medium text-slate-900">${resultado.VALOR_VACACIONES.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VALOR_INCAPACIDAD > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">Incapacidad</span>
                            <span className="font-medium text-slate-900">${resultado.VALOR_INCAPACIDAD.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VALOR_BONO > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">Bono</span>
                            <span className="font-medium text-slate-900">${resultado.VALOR_BONO.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_HED > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">H.E.D</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_HED.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_HEN > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">H.E.N</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_HEN.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_HEDF > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">H.E.D.F</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_HEDF.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_HENF > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">H.E.N.F</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_HENF.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_RN > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">R.N</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_RN.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_RDN > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">R.D.F</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_RDN.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.VLR_RNF > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">R.N.F</span>
                            <span className="font-medium text-slate-900">${resultado.VLR_RNF.toLocaleString('es-CO')}</span>
                          </div>
                        )}

                        <div className="flex flex-col mt-3 pt-3 border-t-2 border-slate-100 bg-emerald-50/50 p-2 rounded-lg">
                          <span className="text-slate-800 text-xs font-bold mb-1">T. Devengado</span>
                          <span className="text-emerald-700 text-sm font-black">${(resultado.TOTAL_DEVENGADO || 0).toLocaleString('es-CO')}</span>
                        </div>
                      </div>
                    </div>

                    {/* Columna Derecha: Deducciones */}
                    <div>
                      <h4 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3 border-b-2 border-slate-100 pb-2 flex items-center">
                        <span className="w-2 h-2 rounded-full bg-rose-500 mr-2"></span> Descuentos
                      </h4>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs sm:text-sm">
                          <span className="text-slate-600">Salud (4%)</span>
                          <span className="font-medium text-slate-900">-${(resultado.SALUD_4 || 0).toLocaleString('es-CO')}</span>
                        </div>
                        <div className="flex justify-between text-xs sm:text-sm">
                          <span className="text-slate-600">Pensión (4%)</span>
                          <span className="font-medium text-slate-900">-${(resultado.PENSION_4 || 0).toLocaleString('es-CO')}</span>
                        </div>
                        {resultado.PRESTAMOS > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">Préstamos</span>
                            <span className="font-medium text-slate-900">-${resultado.PRESTAMOS.toLocaleString('es-CO')}</span>
                          </div>
                        )}
                        {resultado.SALARIO_ESPECIE_MES > 0 && (
                          <div className="flex justify-between text-xs sm:text-sm">
                            <span className="text-slate-600">Desc. Especie</span>
                            <span className="font-medium text-slate-900">-${resultado.SALARIO_ESPECIE_MES.toLocaleString('es-CO')}</span>
                          </div>
                        )}

                        <div className="flex flex-col mt-3 pt-3 border-t-2 border-slate-100 bg-rose-50/50 p-2 rounded-lg">
                          <span className="text-slate-800 text-xs font-bold mb-1">T. Deducciones</span>
                          <span className="text-rose-600 text-sm font-black">-${((resultado.TOTAL_DEDUCIDO || 0) + (resultado.SALARIO_ESPECIE_MES || 0)).toLocaleString('es-CO')}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Footer Full Width: Neto a Pagar */}
                  <div className="bg-unifika-primary px-6 py-6 mt-2">
                    <div className="flex flex-col items-start text-white">
                      <p className="text-xs text-unifika-accent uppercase tracking-widest font-bold mb-2">Valor a transferir</p>
                      <p className="text-3xl sm:text-4xl font-black tracking-tight text-white drop-shadow-md">
                        ${(resultado.NETO_PAGAR || 0).toLocaleString('es-CO')}
                      </p>
                    </div>
                  </div>

                  {/* Nuevos botones: Guardar y Descargar PDF */}
                  <div className="p-5 bg-slate-50 border-t border-slate-200 flex flex-col gap-3">
                    {saveMessage && (
                      <div className={`p-3 rounded text-sm ${saveMessage.type === 'success' ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-red-100 text-red-800 border border-red-200'}`}>
                        {saveMessage.text}
                      </div>
                    )}
                    <div className="flex flex-col sm:flex-row gap-3">
                      <button
                        onClick={handleGuardarHistorico}
                        disabled={isSaving}
                        className={`flex-1 flex items-center justify-center px-4 py-2.5 text-sm font-bold rounded-xl transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 ${isSaving ? 'bg-slate-200 text-slate-500 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-700 text-white'}`}
                      >
                        {isSaving ? 'Guardando...' : 'Guardar Histórico'}
                      </button>

                      <button
                        onClick={handleDescargarPDF}
                        disabled={isDownloading}
                        className={`flex-1 flex items-center justify-center px-4 py-2.5 text-sm font-bold rounded-xl transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-400 ${isDownloading ? 'bg-slate-200 text-slate-500 cursor-not-allowed' : 'bg-slate-800 hover:bg-slate-900 text-white'}`}
                      >
                        {isDownloading ? (
                          <>
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-slate-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Generando PDF...
                          </>
                        ) : 'Descargar Desprendible'}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-10 flex flex-col items-center justify-center text-center h-full min-h-[350px]">
                  <div className="w-20 h-20 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mb-5 text-slate-300">
                    <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-bold text-slate-700 mb-2">Sin Resultados</h3>
                  <p className="text-sm text-slate-500 max-w-[200px] leading-relaxed">
                    Completa el formulario y presiona <strong>Liquidar</strong>.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
