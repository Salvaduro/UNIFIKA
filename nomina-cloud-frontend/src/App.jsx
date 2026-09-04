import { useState, useEffect, useMemo } from "react";
import "./App.css";
import logoUrl from "./assets/Logo.png";
import Auth from "./components/Auth";
import ResetPassword from "./components/ResetPassword";
import ResumenNomina from "./components/ResumenNomina";
import DashboardHistorico from "./components/DashboardHistorico";
import DashboardAuditoria from "./components/DashboardAuditoria";
import IdleTimer from "./components/IdleTimer";
import { supabase } from "./lib/supabaseClient";
import { apiClient } from "./lib/apiClient";
import toast, { Toaster } from "react-hot-toast";

const generarPeriodos = () => {
  const periodos = [];
  const fechaActual = new Date();
  const añoActual = fechaActual.getFullYear();
  const mesActual = fechaActual.getMonth(); // Enero es 0, Diciembre es 11
  const opcionesMes = { month: "long" };

  // Iterar desde el mes 0 (Enero) hasta el mes actual + 1
  for (let i = 0; i <= mesActual + 1; i++) {
    // Si estamos en diciembre (11), i=12 pasará automáticamente a Enero del próximo año
    const fecha = new Date(añoActual, i, 1);
    const mes = new Intl.DateTimeFormat("es-ES", opcionesMes)
      .format(fecha)
      .toUpperCase();
    const año = fecha.getFullYear();
    periodos.push(`${mes} ${año}`);
  }

  return periodos.reverse(); // Muestra el mes más reciente de primero
};

function App() {
  const [session, setSession] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: newSession } }) => {
      setSession((prev) =>
        prev?.access_token === newSession?.access_token &&
          prev?.user?.id === newSession?.user?.id
          ? prev
          : newSession,
      );
      setIsLoadingAuth(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, newSession) => {
      // 1. Manejo de caducidad crítica
      if (event === "SIGNED_OUT" || event === "TOKEN_REFRESH_FAILED") {
        setSession(null);
        localStorage.clear();
        return;
      }

      // Leemos la bandera de cuarentena
      const enCuarentena =
        localStorage.getItem("bloqueo_recuperacion") === "true";
      const esRutaRecuperacion =
        window.location.pathname === "/actualizar-password";

      // Si estamos en cuarentena y esta es la pestaña vieja (Login), CONGELAMOS EL ESTADO
      if (enCuarentena && !esRutaRecuperacion) {
        setSession(null);
        return; // Interrumpe el flujo, evitando que pase al Dashboard
      }

      // Lógica normal para el resto de casos
      if (newSession) {
        setSession((prev) =>
          prev?.access_token === newSession?.access_token &&
            prev?.user?.id === newSession?.user?.id
            ? prev
            : newSession,
        );
      } else {
        setSession(null);
      }
      setIsLoadingAuth(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  // ==========================================
  // BLOQUE 1: MANEJO DE ESTADOS (FORMULARIO Y UI)
  // ==========================================
  const [formData, setFormData] = useState({
    ID_CONTRATO: "EMP-001",
    SALARIO_BASE: 1750905,
    DIAS_LABORADOS: 15,
    ES_SMLV: "SI",
    CON_BONO: "NO",
    TIENE_AUX: "SI",
    TIPO_CONTRATO: "TIEMPO COMPLETO",
    ESTADO_EMPLEADO: "ACTIVO",
    PERIODO_PAGO: "QUINCENAL",
    SALARIO_ESPECIE: "",
    VLR_BONO: "",
    CON_PRESTAMO: "NO",
    PRESTAMOS: "",
    DIAS_VACACIONES: 0,
    DIAS_INCAPACIDAD: 0,
    REPORTAR_EXTRAS: "NO",
    HED: 0,
    HEN: 0,
    HEDF: 0,
    HENF: 0,
    RN: 0,
    RDN: 0,
    RNF: 0,
    EPS: "",
    FONDO_PENSIONES: "",
  });

  const [isLoading, setIsLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [reporteData, setReporteData] = useState([]);
  const [reporteFiltro, setReporteFiltro] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(15);
  const [sortConfig, setSortConfig] = useState({ key: "razon_social", direction: "ascending" });
  const [isFetchingReporte, setIsFetchingReporte] = useState(false);
  const [isCerrado, setIsCerrado] = useState(false);
  const [carpetaCliente, setCarpetaCliente] = useState(null);

  // Fase 7: Estados de Ausentismo
  const [isAusentismoModalOpen, setIsAusentismoModalOpen] = useState(false);
  const [ausentismosLocales, setAusentismosLocales] = useState([]);
  const [nuevoAusentismo, setNuevoAusentismo] = useState({
    tipo_novedad: "Incapacidad",
    fecha_inicio: "",
    fecha_fin: ""
  });
  const [tramitarReembolso, setTramitarReembolso] = useState(false);
  const [soporteMedico, setSoporteMedico] = useState(null);

  const calcularPeriodoPorDefecto = () => {
    const hoy = new Date();
    const meses = [
      "ENERO",
      "FEBRERO",
      "MARZO",
      "ABRIL",
      "MAYO",
      "JUNIO",
      "JULIO",
      "AGOSTO",
      "SEPTIEMBRE",
      "OCTUBRE",
      "NOVIEMBRE",
      "DICIEMBRE",
    ];

    const mesActual = meses[hoy.getMonth()];
    const anioActual = hoy.getFullYear();
    const diaActual = hoy.getDate();

    const periodo = `${mesActual} ${anioActual}`;
    const quincena = diaActual <= 15 ? "1" : "2";

    return { periodo, quincena };
  };

  const periodoInicial = calcularPeriodoPorDefecto();

  // Estados del Periodo
  const [periodoLiq, setPeriodoLiq] = useState(periodoInicial.periodo);
  const [quincenaPago, setQuincenaPago] = useState(periodoInicial.quincena);
  const [reportePeriodo, setReportePeriodo] = useState(periodoInicial.periodo);
  const [reporteQuincena, setReporteQuincena] = useState("1");
  const [observaciones, setObservaciones] = useState("");
  const [mostrarNota, setMostrarNota] = useState(false);

  // Estados CRM
  const [perfilAportante, setPerfilAportante] = useState(null);
  const [empleadorId, setEmpleadorId] = useState("");
  const [isLoadingPerfil, setIsLoadingPerfil] = useState(false);
  const [perfilError, setPerfilError] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSyncingMasivo, setIsSyncingMasivo] = useState(false);
  const [empleadosEncontrados, setEmpleadosEncontrados] = useState([]);
  const [selectedEmpleadoId, setSelectedEmpleadoId] = useState("");
  const [isContractOpen, setIsContractOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("liquidacion");
  const [refreshResumenKey, setRefreshResumenKey] = useState(0);

  // Derivaciones del DataGrid (Movidas aquí para evitar violar Rules of Hooks por Early Returns)
  const sortedData = useMemo(() => {
    let sortableItems = [...(reporteData || [])];
    if (sortConfig !== null) {
      sortableItems.sort((a, b) => {
        let valA = a?.[sortConfig.key];
        let valB = b?.[sortConfig.key];

        if (valA === null || valA === undefined) valA = typeof valB === "number" ? 0 : "";
        if (valB === null || valB === undefined) valB = typeof valA === "number" ? 0 : "";

        if (typeof valA === "number" && typeof valB === "number") {
          return sortConfig.direction === "ascending" ? valA - valB : valB - valA;
        }
        const strA = String(valA || "").toLowerCase();
        const strB = String(valB || "").toLowerCase();
        if (strA < strB) {
          return sortConfig.direction === "ascending" ? -1 : 1;
        }
        if (strA > strB) {
          return sortConfig.direction === "ascending" ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [reporteData, sortConfig]);

  const datosFiltrados = (sortedData || []).filter((item) => {
    if (!reporteFiltro) return true;
    const term = reporteFiltro.toLowerCase();
    return (
      item?.razon_social?.toLowerCase().includes(term) ||
      item?.nombre_empleado?.toLowerCase().includes(term) ||
      String(item?.id_contrato || "").toLowerCase().includes(term) ||
      item?.tipo_contrato?.toLowerCase().includes(term)
    );
  });

  const totalPages = Math.max(1, Math.ceil((datosFiltrados?.length || 0) / itemsPerPage));
  const paginatedData = (datosFiltrados || []).slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalDevengadoFiltrado = (datosFiltrados || []).reduce((sum, item) => sum + (Number(item?.total_devengado) || 0), 0);
  const totalIbcFiltrado = (datosFiltrados || []).reduce((sum, item) => sum + (Number(item?.ibc_pila) || 0), 0);

  // Efecto para cargar el perfil al iniciar sesión
  useEffect(() => {
    const fetchPerfil = async () => {
      if (window.location.pathname === "/actualizar-password") return;
      if (!session) return;
      if (perfilAportante && perfilAportante.rol) return; // Evita el refetch si ya hay datos

      setIsLoadingPerfil(true);
      setPerfilError(null);
      try {
        // 1. Consulta directa a m_perfiles filtrando por user.id para obtener el rol real y el id_aportante
        let rolBD = null;
        let idAportanteBD = null;
        try {
          const { data: perfilData, error: perfilErr } = await supabase
            .from("m_perfiles")
            .select("rol, id_aportante")
            .eq("id", session.user.id)
            .single();

          if (!perfilErr && perfilData) {
            if (perfilData.rol) {
              rolBD = String(perfilData.rol).toUpperCase().trim();
            }
            if (perfilData.id_aportante) {
              idAportanteBD = perfilData.id_aportante;
            }
          }
        } catch (err) {
          console.warn("Fallo en consulta directa a m_perfiles:", err);
        }

        // 2. Sincronización en cascada (Sync Guard)
        const res = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/auth/init-session`, {
          method: 'POST'
        });
        if (res.ok) {
          const { data } = await res.json();
          // Normalización (Defensa de Tipos): forzar rol a mayúsculas
          const rawRol = data?.rol || rolBD || "EMPLEADOR";
          const normalizedRol = String(rawRol).toUpperCase().trim();
          const normalizedIdAportante = data?.id_aportante || idAportanteBD || null;

          setPerfilAportante({
            ...data,
            rol: normalizedRol,
            id_aportante: normalizedIdAportante,
          });
        } else {
          const errorData = await res.json().catch(() => ({}));
          const errorMsg =
            errorData.detail ||
            "Error de autenticación o usuario no autorizado.";

          if (res.status === 403) {
            await supabase.auth.signOut();
            localStorage.clear();
            toast.error(errorMsg);
            setTimeout(() => {
              window.location.reload();
            }, 2000);
            return;
          }
          setPerfilError(errorMsg);
        }
      } catch (error) {
        console.error("Error al obtener perfil", error);
        setPerfilError("Fallo en la comunicación con el servidor.");
      } finally {
        setIsLoadingPerfil(false);
      }
    };
    fetchPerfil();
  }, [session, perfilAportante]);

  // Efecto para cargar empleados SOLO después de tener el perfil (Previene Condición de Carrera)
  useEffect(() => {
    if (window.location.pathname === "/actualizar-password") return;
    // Solo buscar empleados si ya tenemos certeza del usuario logueado
    if (session && session.user && perfilAportante?.id_aportante) {
      if (perfilAportante.rol === "EMPLEADOR") {
        handleSearchEmpleador(perfilAportante.id_aportante);
      }
    }
  }, [session, perfilAportante]);

  const hidratarLiquidacion = async (idContrato, pLiq, qPago) => {
    if (!idContrato || !pLiq || !qPago) return;
    
    try {
        const resNov = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/novedades/${encodeURIComponent(idContrato)}?periodo_liq=${encodeURIComponent(pLiq)}&quincena_pago=${encodeURIComponent(qPago)}`);
        
        if (resNov.ok) {
            const dataNov = await resNov.json();
            if (dataNov.status === "success" && dataNov.data) {
                setFormData(prev => ({ ...prev, ...dataNov.data }));
            }
        }

        const resAus = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/empleado/${encodeURIComponent(idContrato)}/ausentismos?periodo_liq=${encodeURIComponent(pLiq)}&quincena_pago=${encodeURIComponent(qPago)}`);
        
        if (resAus.ok) {
            const dataAus = await resAus.json();
            if (dataAus && dataAus.data) {
                setAusentismosLocales(dataAus.data);
            } else if (Array.isArray(dataAus)) {
                setAusentismosLocales(dataAus);
            } else {
                setAusentismosLocales([]);
            }
        } else {
            setAusentismosLocales([]);
        }
    } catch (error) {
        console.error("Error en hidratación maestra:", error);
    }
  };

  useEffect(() => {
    hidratarLiquidacion(selectedEmpleadoId, periodoLiq, quincenaPago);
  }, [selectedEmpleadoId, periodoLiq, quincenaPago]);

  useEffect(() => {
    const lista = ausentismosLocales || [];
    
    let tIncapacidad = 0, tVacaciones = 0, tLicencia = 0;

    lista.forEach((a) => {
        const safeObj = a?.data || a || {};
        
        const rawTipo = safeObj.tipo_novedad || safeObj.tipoNovedad || safeObj.tipo || "";
        const tipo = String(rawTipo).toUpperCase();
        
        // 1. Intentar buscar la propiedad directa
        let dias = parseFloat(safeObj.dias_totales || safeObj.diasTotales || safeObj.dias) || 0;
        
        // 2. Si no existe, calcularla matemáticamente con las fechas
        if (dias === 0 && safeObj.fecha_inicio && safeObj.fecha_fin) {
            const inicio = new Date(safeObj.fecha_inicio);
            const fin = new Date(safeObj.fecha_fin);
            // Diferencia en milisegundos a días (+1 para que sea inclusivo)
            dias = Math.round((fin - inicio) / (1000 * 60 * 60 * 24)) + 1;
        }

        if (tipo.includes("INCAPACIDAD") || tipo.includes("IGE")) tIncapacidad += dias;
        else if (tipo.includes("VACACION") || tipo.includes("VAC")) tVacaciones += dias;
        else if (tipo.includes("LICENCIA") || tipo.includes("SLN") || tipo.includes("PERMISO") || tipo.includes("NO REMUNERADA")) tLicencia += dias;
    });
    
    setFormData(prev => ({
        ...prev,
        DIAS_INCAPACIDAD: tIncapacidad,
        DIAS_VACACIONES: tVacaciones,
        DIAS_LICENCIA: tLicencia
    }));
  }, [ausentismosLocales]);

  // Efecto para auto-calcular el periodo actual
  useEffect(() => {
    const date = new Date();
    const months = [
      "ENERO",
      "FEBRERO",
      "MARZO",
      "ABRIL",
      "MAYO",
      "JUNIO",
      "JULIO",
      "AGOSTO",
      "SEPTIEMBRE",
      "OCTUBRE",
      "NOVIEMBRE",
      "DICIEMBRE",
    ];
    const currentMonth = months[date.getMonth()];
    const currentYear = date.getFullYear();
    setPeriodoLiq(`${currentMonth} ${currentYear}`);

    if (date.getDate() <= 15) {
      setQuincenaPago("1");
    } else {
      setQuincenaPago("2");
    }
  }, []);

  // Efecto para sincronizar la Quincena con el Periodo de Pago del contrato
  useEffect(() => {
    const isMensual =
      formData.PERIODO_PAGO?.toUpperCase() === "MENSUAL" ||
      formData.PERIODO_PAGO?.toUpperCase() === "MENSUALIDAD";
    if (isMensual) {
      setQuincenaPago("M");
    } else {
      if (quincenaPago === "M") {
        const date = new Date();
        setQuincenaPago(date.getDate() <= 15 ? "1" : "2");
      }
    }
  }, [formData.PERIODO_PAGO]);

  if (window.location.pathname === "/actualizar-password") {
    return <ResetPassword />;
  }

  if (isLoadingAuth) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 border-4 border-unifika-primary border-t-transparent rounded-full animate-spin mb-4"></div>
        <h2 className="text-xl font-bold text-slate-800">
          Validando credenciales...
        </h2>
      </div>
    );
  }

  if (!session) {
    return <Auth />;
  }

  const SMLV_ACTUAL = 1750905;

  // ==========================================
  // BLOQUE 2: CONSULTA CRM Y AUTOCOMPLETADO
  // ==========================================
  function autocompletarFormulario(empleado) {
    const esQuincenal = empleado.PERIODO_PAGO?.toUpperCase() === "QUINCENAL";
    const esTiempoParcial =
      empleado.TIPO_CONTRATO?.toUpperCase() === "TIEMPO PARCIAL";

    setFormData((prev) => {
      const diasPorDefecto = esTiempoParcial ? 0 : esQuincenal ? 15 : 30;

      return {
        ...prev,
        ID_CONTRATO: empleado.ID_CONTRATO || prev.ID_CONTRATO,
        SALARIO_BASE: empleado.SALARIO_BASE || prev.SALARIO_BASE,
        SALARIO_ESPECIE: empleado.SALARIO_ESPECIE || "",
        ES_SMLV: empleado.ES_SMLV || prev.ES_SMLV,
        CON_BONO: empleado.CON_BONO || prev.CON_BONO,
        TIENE_AUX: empleado.TIENE_AUX || prev.TIENE_AUX,
        TIPO_CONTRATO: empleado.TIPO_CONTRATO || prev.TIPO_CONTRATO,
        CARGO_DESEMPENEADO: empleado.CARGO_DESEMPENEADO || "",
        PERIODO_PAGO: empleado.PERIODO_PAGO || prev.PERIODO_PAGO,
        DIAS_LABORADOS: diasPorDefecto,
        HORAS_LABORADAS: 0,
        DIAS_VACACIONES: prev.DIAS_VACACIONES || 0,
        DIAS_INCAPACIDAD: prev.DIAS_INCAPACIDAD || 0,
        DIAS_LICENCIA: prev.DIAS_LICENCIA || 0,
        PRESTAMOS: 0,
        PRIMA_CALC: 0,
        HED: 0,
        HEN: 0,
        HEDF: 0,
        HENF: 0,
        RN: 0,
        RDN: 0,
        RNF: 0,
        OBSERVACIONES: "",
        VLR_BONO: empleado.VLR_BONO || "",
        EPS: empleado.EPS || "",
        FONDO_PENSIONES: empleado["FONDO DE PENSIONES"] || "",
        LINK_DRIVE: empleado.LINK_DRIVE || "",
      };
    });

    if (esTiempoParcial) {
      apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/historico/ultimo-dias/${encodeURIComponent(empleado.ID_CONTRATO)}`,
      )
        .then((res) => res.json())
        .then((data) => {
          if (data.status === "success") {
            setFormData((prev) => ({
              ...prev,
              DIAS_LABORADOS: data.dias_laborados,
            }));
          }
        })
        .catch((err) => console.error("Fallo silencioso al traer días:", err));
    }
  }

  async function handleSearchEmpleador(aportanteId = "me", force = false) {
    // Si no pasan ID y es ADMIN o SUPERADMIN, usa el estado empleadorId
    const isStaff =
      perfilAportante?.rol === "ADMINISTRADOR" ||
      perfilAportante?.rol === "SUPERADMIN";
    const targetId = aportanteId === "me" ? empleadorId || "me" : aportanteId;
    if (
      targetId === "me" &&
      isStaff &&
      !empleadorId.trim()
    )
      return;

    if (!force && empleadosEncontrados && empleadosEncontrados.length > 0)
      return; // Evita el refetch si ya hay datos

    setIsSearching(true);
    setError(null);
    setSearchError(null);
    setEmpleadosEncontrados([]);
    setSelectedEmpleadoId("");

    // Limpiar el formulario actual
    setFormData({
      ID_CONTRATO: "",
      SALARIO_BASE: SMLV_ACTUAL,
      DIAS_LABORADOS: 15,
      ES_SMLV: "SI",
      CON_BONO: "NO",
      TIENE_AUX: "SI",
      TIPO_CONTRATO: "TIEMPO COMPLETO",
      CARGO_DESEMPENEADO: "",
      ESTADO_EMPLEADO: "ACTIVO",
      PERIODO_PAGO: "QUINCENAL",
      SALARIO_ESPECIE: "",
      VLR_BONO: "",
      CON_PRESTAMO: "NO",
      PRESTAMOS: "",
      DIAS_VACACIONES: 0,
      DIAS_INCAPACIDAD: 0,
      REPORTAR_EXTRAS: "NO",
      HED: 0,
      HEN: 0,
      HEDF: 0,
      HENF: 0,
      RN: 0,
      RDN: 0,
      RNF: 0,
      EPS: "",
      FONDO_PENSIONES: "",
    });

    try {
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/empleados`,
      );

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
          setSearchError(
            <>
              No se encuentra registro en nuestro sistema. <br />
              Por favor, comunícate al Tel. 333 6025560 para brindarte atención.
            </>,
          );
        }

        setSelectedEmpleadoId("");
        setResultado(null);
        return;
      }

      const data = await response.json();

      if (data.status === "success" && data.data && data.data.length > 0) {
        setCarpetaCliente(data.carpeta_cliente || null);
        if (data.data.length === 1) {
          // Un solo empleado, autocompletar
          const emp = data.data[0];
          setSelectedEmpleadoId(emp.ID_CONTRATO);
          autocompletarFormulario(emp);
        }
        setEmpleadosEncontrados(data.data);
      } else {
        setError("No se encontraron empleados para este ID.");
      }
    } catch (err) {
      console.error("Error al buscar empleador:", err);
      setSearchError(
        <>
          No se encuentra registro en nuestro sistema. <br />
          Por favor, comunícate al Tel. 333 6025560 para brindarte atención.
        </>,
      );
      setSelectedEmpleadoId("");
      setResultado(null);
    } finally {
      setIsSearching(false);
    }
  }

  const handleSelectEmpleado = async (e) => {
    const selectedId = e.target.value;
    setSelectedEmpleadoId(selectedId);

    if (selectedId) {
      try {
        const targetId = empleadorId || "me";
        const response = await apiClient(
          `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/empleado/${encodeURIComponent(selectedId)}`
        );
        if (!response.ok) {
          throw new Error(`Error HTTP: ${response.status}`);
        }
        const data = await response.json();
        if (data.status === "success" && data.data) {
          autocompletarFormulario(data.data);
        } else {
          throw new Error("Respuesta del servidor sin status success o sin data");
        }
      } catch (error) {
        console.error("Error al cargar detalle del empleado (carpeta):", error);
        // Fallback local en caso de error
        const empleado = empleadosEncontrados.find(
          (emp) => emp.ID_CONTRATO === selectedId,
        );
        if (empleado) {
          autocompletarFormulario(empleado);
        }
      }
    }
  };

  const handleRowClick = async (empResumen) => {
    setActiveTab("liquidacion");
    setSelectedEmpleadoId(empResumen.id_contrato);

    try {
      const targetId = empleadorId || "me";
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/empleado/${encodeURIComponent(empResumen.id_contrato)}`
      );
      if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
      const data = await response.json();
      if (data.status === "success" && data.data) {
        autocompletarFormulario(data.data);
      } else {
        throw new Error("Respuesta del servidor sin status success o sin data");
      }
    } catch (error) {
      console.error("Error al cargar detalle del empleado en row click:", error);
      const empleadoCompleto = empleadosEncontrados.find(
        (e) => e.ID_CONTRATO === empResumen.id_contrato,
      );
      if (empleadoCompleto) {
        autocompletarFormulario(empleadoCompleto);
      }
    }
  };

  const handleEditarDesdeReporte = async (item) => {
    const nit = item.nit_empresa;
    const contratoId = item.id_contrato;
    
    setEmpleadorId(nit);
    setPeriodoLiq(item.periodo_liq);
    setQuincenaPago(item.quincena_pago);
    setSelectedEmpleadoId(contratoId);
    
    setActiveTab("liquidacion");

    try {
      const targetId = nit || "me";
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/empleado/${encodeURIComponent(contratoId)}`
      );
      if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
      }
      const data = await response.json();
      if (data.status === "success" && data.data) {
        autocompletarFormulario(data.data);
        // La hidratación maestra se encargará de sobreescribir el formData y ausentismosLocales 
        // a través del useEffect reactivo al cambiar los estados.
      } else {
        throw new Error("Respuesta del servidor sin status success o sin data");
      }
    } catch (error) {
      console.error("Error al cargar detalle del empleado desde reporte:", error);
      toast.error(`Error al cargar datos del empleado: ${error.message || "Error desconocido"}`);
    }
  };

  const handleSyncEmpleado = async (e, idContrato) => {
    e.preventDefault();
    e.stopPropagation();

    setIsSyncing(true);
    try {
      const targetId = empleadorId || "me";
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/empleado/${encodeURIComponent(idContrato)}/sync`,
        { method: "POST" }
      );
      if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
      const data = await response.json();
      if (data.status === "success" && data.data) {
        autocompletarFormulario(data.data);
        setEmpleadosEncontrados(prev => prev.map(emp => emp.ID_CONTRATO === idContrato ? data.data : emp));
        toast.success("Empleado sincronizado y cálculos actualizados");
        setRefreshResumenKey(prev => prev + 1);
      } else {
        throw new Error("Respuesta del servidor sin status success o sin data");
      }
    } catch (error) {
      console.error("Error al sincronizar empleado:", error);
      toast.error("Hubo un error sincronizando el empleado con el CRM.");
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSyncMasivo = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    setIsSyncingMasivo(true);
    setError(null);
    setSearchError(null);

    try {
      const targetId = empleadorId || "me";
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/empleador/${targetId}/sync-masivo`,
        { method: "POST" }
      );

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Error HTTP: ${response.status}`);
      }

      const data = await response.json();
      if (data.status === "success" && data.data) {
        setEmpleadosEncontrados(data.data);
        setSelectedEmpleadoId("");
        setFormData({
          ID_CONTRATO: "",
          SALARIO_BASE: SMLV_ACTUAL,
          DIAS_LABORADOS: 15,
          ES_SMLV: "SI",
          CON_BONO: "NO",
          TIENE_AUX: "SI",
          TIPO_CONTRATO: "TIEMPO COMPLETO",
          CARGO_DESEMPENEADO: "",
          ESTADO_EMPLEADO: "ACTIVO",
          PERIODO_PAGO: "QUINCENAL",
          SALARIO_ESPECIE: "",
          VLR_BONO: "",
          CON_PRESTAMO: "NO",
          PRESTAMOS: "",
          DIAS_VACACIONES: 0,
          DIAS_INCAPACIDAD: 0,
          REPORTAR_EXTRAS: "NO",
          HED: 0,
          HEN: 0,
          HEDF: 0,
          HENF: 0,
          RN: 0,
          RDN: 0,
          RNF: 0,
          EPS: "",
          FONDO_PENSIONES: "",
        });
        toast.success("Sincronización masiva con el CRM completada exitosamente.");
      } else {
        throw new Error("Respuesta inválida del servidor en sincronización masiva");
      }
    } catch (error) {
      console.error("Error al forzar sincronización masiva con el CRM:", error);
      toast.error(`Hubo un error en la sincronización masiva: ${error.message || "Error desconocido"}`);
    } finally {
      setIsSyncingMasivo(false);
    }
  };

  // ==========================================
  // BLOQUE 3: REGLAS DE NEGOCIO (EVENTOS INPUT)
  // ==========================================
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      let newValue = value;

      if (name === "DIAS_LABORADOS") {
        const maxDias =
          prev.PERIODO_PAGO?.toLowerCase() === "quincenal" ? 15 : 30;
        const parsedValue = parseFloat(value);
        if (!isNaN(parsedValue) && parsedValue > maxDias) {
          newValue = maxDias;
        }
      }

      const newData = { ...prev, [name]: newValue };

      // Regla: Tiempo Parcial fuerza SMLV a NO
      if (name === "TIPO_CONTRATO" && value === "TIEMPO PARCIAL") {
        newData.ES_SMLV = "NO";
        newData.SALARIO_BASE = ""; // Limpiar el salario mínimo por defecto
      }

      // Regla: Limpiar SALARIO_ESPECIE si no es Empleado Interno
      if (
        name === "TIPO_CONTRATO" &&
        value?.toLowerCase().trim() !== "empleado interno"
      ) {
        newData.SALARIO_ESPECIE = "";
      }

      // Autocompletar y bloquear si se selecciona SMLV
      if (name === "ES_SMLV") {
        if (value === "SI") {
          newData.SALARIO_BASE = SMLV_ACTUAL;
          newData.CON_BONO = "NO"; // Exclusión: el bono no aplica
          newData.VLR_BONO = "";
        } else {
          newData.SALARIO_BASE = "";
        }
      }

      // Regla: Limpiar VLR_BONO si el bono es NO
      if (name === "CON_BONO" && value === "NO") {
        newData.VLR_BONO = "";
      }

      // Regla: Limpiar PRESTAMOS si no hay préstamo
      if (name === "CON_PRESTAMO" && value === "NO") {
        newData.PRESTAMOS = "";
      }

      // Regla: Limpiar EXTRAS si no reporta
      if (name === "REPORTAR_EXTRAS" && value === "NO") {
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
  // BLOQUE 4: REPORTE DE FACTURACION (STAFF)
  // ==========================================
  const handleConsultarReporte = async () => {
    setIsFetchingReporte(true);
    try {
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/reportes/facturacion?periodo=${encodeURIComponent(reportePeriodo)}&quincena=${encodeURIComponent(reporteQuincena)}`,
        { method: "GET" }
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      if (data.status === "success") {
        setReporteData(data.data || []);
      } else {
        setReporteData([]);
      }
    } catch (error) {
      console.error("Error al consultar reporte:", error);
      toast.error("Error al cargar datos del reporte");
      setReporteData([]);
    } finally {
      setIsFetchingReporte(false);
    }
  };

  const handleFiltroChange = (e) => {
    setReporteFiltro(e.target.value);
    setCurrentPage(1);
  };

  const handleItemsPerPageChange = (e) => {
    setItemsPerPage(Number(e.target.value));
    setCurrentPage(1);
  };

  const handleSort = (key) => {
    let direction = "ascending";
    if (sortConfig.key === key && sortConfig.direction === "ascending") {
      direction = "descending";
    }
    setSortConfig({ key, direction });
  };



  const handleExportarCSVLocal = () => {
    if (!datosFiltrados || datosFiltrados.length === 0) return;
    
    const cabeceras = ["ID Contrato", "Empresa", "Empleado", "Tipo Contrato", "Periodo", "Quincena", "Días Lab", "Días Incap", "Días Vac", "IBC", "Devengado", "Deducido", "Neto", "Estado"];
    
    const lineas = datosFiltrados.map(d => {
      return `"${d.id_contrato}","${d.razon_social}","${d.nombre_empleado}","${d.tipo_contrato}","${d.periodo_liq}","${d.quincena_pago}","${d.dias_laborados}","${d.dias_incapacidad}","${d.dias_vacaciones}","${d.ibc_pila}","${d.total_devengado}","${d.total_deducido}","${d.neto_pagar}","${d.estado_cierre}"`;
    });
    
    const csvContent = cabeceras.join(",") + "\n" + lineas.join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement("a");
    link.href = url;
    link.download = `Reporte_Granular_${reportePeriodo.replace(" ", "_")}_${new Date().getTime()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("CSV exportado correctamente");
  };

  const handleLiquidarNomina = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResultado(null);
    try {
      const payload = [
        {
          ...formData,
          SALARIO_BASE: formData.SALARIO_BASE.toString(),
          DIAS_LABORADOS: Number(formData.DIAS_LABORADOS),
          SALARIO_ESPECIE: formData.SALARIO_ESPECIE
            ? Number(formData.SALARIO_ESPECIE)
            : 0,
          VLR_BONO: formData.VLR_BONO ? Number(formData.VLR_BONO) : 0,
          PRESTAMOS: formData.PRESTAMOS ? Number(formData.PRESTAMOS) : 0,
          DIAS_VACACIONES: formData.DIAS_VACACIONES
            ? Number(formData.DIAS_VACACIONES)
            : 0,
          DIAS_INCAPACIDAD: formData.DIAS_INCAPACIDAD
            ? Number(formData.DIAS_INCAPACIDAD)
            : 0,
          DIAS_LICENCIA: formData.DIAS_LICENCIA
            ? Number(formData.DIAS_LICENCIA)
            : 0,
          HED: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.HED) : 0,
          HEN: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.HEN) : 0,
          HEDF: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.HEDF) : 0,
          HENF: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.HENF) : 0,
          RN: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.RN) : 0,
          RDN: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.RDN) : 0,
          RNF: formData.REPORTAR_EXTRAS === "SI" ? Number(formData.RNF) : 0,
          EPS: formData.EPS,
          FONDO_PENSIONES: formData.FONDO_PENSIONES,
          ausentismos: ausentismosLocales,
        },
      ];

      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/liquidar`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data && data.length > 0) {
        setResultado(data[0]);

        try {
          const idQuery = formData.ID_CONTRATO ? `?id_contrato=${encodeURIComponent(formData.ID_CONTRATO)}` : "";
          const closureRes = await apiClient(
            `${import.meta.env.VITE_API_URL}/api/v1/nomina/estado-cierre/${encodeURIComponent(periodoLiq)}/${encodeURIComponent(quincenaPago)}${idQuery}`
          );
          if (closureRes.ok) {
            const closureData = await closureRes.json();
            setIsCerrado(closureData.cerrado);
          } else {
            setIsCerrado(false);
          }
        } catch (e) {
          setIsCerrado(false);
        }
      } else {
        setError("No se recibieron datos de liquidación.");
      }
    } catch (error) {
      console.error("Error al liquidar nómina:", error);
      setError(
        "Hubo un error al conectar con el servidor backend. Revisa que el servidor esté encendido.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * UI de Nómina - Regla de Promise Chaining:
   * Un solo botón de "Guardar y Descargar Desprendible" que ejecuta en cadena:
   * 1) Guardado del histórico de nómina en el backend.
   * 2) Generación y descarga del PDF solo tras completar el guardado con éxito.
   * Si la nómina está en estado CERRADA, el botón desaparece y se muestra un mensaje estático.
   */
  const handleGuardarYDescargar = async () => {
    if (!resultado) return;
    setIsSaving(true);
    setSaveMessage(null);
    try {
      const empleadoOriginal =
        empleadosEncontrados.find(
          (emp) => emp.ID_CONTRATO === resultado.ID_CONTRATO,
        ) || {};
      const payloadCompleto = { ...empleadoOriginal, ...resultado };

      const payload = [payloadCompleto].map((empleado) => ({
        ...empleado,
        PERIODO_LIQ: periodoLiq,
        QUINCENA_PAGO: quincenaPago,
        OBSERVACIONES: observaciones,
      }));

      // Paso A: Guardar Histórico
      const saveResponse = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/historico/guardar`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!saveResponse.ok) {
        let errData = {};
        try { errData = await saveResponse.json(); } catch (e) { }
        const errorObj = new Error(errData.detail || "Error HTTP: " + saveResponse.status);
        errorObj.response = { data: errData };
        throw errorObj;
      }

      // Paso B: Descargar Desprendible
      setIsDownloading(true);
      const pdfPayload = {
        ...empleadoOriginal,
        ...resultado,
        PERIODO_LIQ: periodoLiq,
        QUINCENA_PAGO: quincenaPago,
        OBSERVACIONES: observaciones,
      };

      const pdfResponse = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/comprobante/generar`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(pdfPayload),
        },
      );

      if (!pdfResponse.ok) {
        let errData = {};
        try { errData = await pdfResponse.json(); } catch (e) { }
        const errorObj = new Error(errData.detail || "Error HTTP: " + pdfResponse.status);
        errorObj.response = { data: errData };
        throw errorObj;
      }

      const blob = await pdfResponse.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;

      const periodoFormateado = periodoLiq
        ? periodoLiq.replace(/\s+/g, "_").toUpperCase()
        : "SIN_PERIODO";
      const quincenaFormateada = quincenaPago
        ? quincenaPago.replace(/\s+/g, "_").toUpperCase()
        : "";

      let sufijoQuincena = quincenaFormateada;
      if (quincenaFormateada === "1") {
        sufijoQuincena = "Q1";
      } else if (quincenaFormateada === "2") {
        sufijoQuincena = "Q2";
      }

      const idContrato =
        resultado.ID_EMPLEADO || resultado.ID_CONTRATO || "SIN_CONTRATO";
      const nombreArchivo = sufijoQuincena
        ? `Desprendible_${idContrato}_${periodoFormateado}_${sufijoQuincena}.pdf`
        : `Desprendible_${idContrato}_${periodoFormateado}.pdf`;

      a.download = nombreArchivo;
      document.body.appendChild(a);
      a.click();

      a.remove();
      window.URL.revokeObjectURL(url);

      // Paso C: Toast de Éxito
      setSaveMessage({
        type: "success",
        text: "Nómina guardada y desprendible generado con éxito.",
      });
      setTimeout(() => {
        setSaveMessage(null);
      }, 5000);
    } catch (error) {
      console.error("Error en Guardar y Descargar:", error);
      const detail = error.response?.data?.detail || error.message || "Error desconocido al procesar la nómina";
      const errorMessage = typeof detail === "string" ? detail : JSON.stringify(detail);
      setSaveMessage({ type: "error", text: errorMessage });
      setTimeout(() => {
        setSaveMessage(null);
      }, 5000);
    } finally {
      setIsSaving(false);
      setIsDownloading(false);
    }
  };

  /**
   * Seguridad de Sesión - Regla de Logout:
   * La acción de Logout NUNCA debe lanzar peticiones HTTP POST/PUT al backend
   * (prohibido guardar al morir / unmount). Solo destruye la sesión localmente
   * con supabase.auth.signOut() y limpiando tokens locales.
   */
  const handleLogout = async () => {
    await supabase.auth.signOut();
    window.location.href = '/login';
  };

  if (isLoadingPerfil) {
    return (
      <div className="fixed inset-0 z-[9999] bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-2xl flex flex-col items-center max-w-sm w-full mx-auto animate-fade-in text-center">
          <svg
            className="animate-spin h-14 w-14 text-unifika-primary mb-6"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          <h2 className="text-xl font-bold text-slate-800 mb-2 leading-tight">
            Sincronizando su perfil con el CRM corporativo...
          </h2>
          <p className="text-slate-500 text-sm font-medium">
            Este proceso puede tardar unos segundos. Por favor no cierre ni actualice esta ventana.
          </p>
        </div>
      </div>
    );
  }

  if (perfilError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full text-center">
          <div className="text-red-500 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              ></path>
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">
            Acceso Denegado
          </h2>
          <p className="text-slate-600 mb-6">{perfilError}</p>
          <button
            onClick={handleLogout}
            className="w-full bg-unifika-primary hover:bg-slate-800 text-white font-bold py-3 px-4 rounded-xl transition-colors"
          >
            Cerrar Sesión
          </button>
        </div>
      </div>
    );
  }

  // ==========================================
  // BLOQUE 5: RENDERIZADO UI (COMPONENTES)
  // ==========================================

  return (
    <IdleTimer>
      <Toaster position="top-right" />
      <div className="min-h-screen bg-slate-50 font-sans flex flex-col">
        <nav className="bg-unifika-primary shadow-lg sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-24 py-2 items-center">
              <div className="flex items-center space-x-3">
                <img
                  src={logoUrl}
                  alt="Unifika Logo"
                  className="h-20 w-auto drop-shadow-md"
                />
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-slate-300 text-sm hidden md:block font-medium">
                  Portal de Administración{" "}
                  {perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR"
                    ? `(${perfilAportante.rol})`
                    : ""}
                </div>
                <button
                  onClick={handleLogout}
                  className="text-white hover:text-red-300 text-sm font-semibold flex items-center gap-2 transition-colors border border-slate-600 hover:border-red-400 px-3 py-1.5 rounded-lg"
                >
                  Cerrar Sesión
                </button>
                <div className="h-9 w-9 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-white font-semibold hover:bg-slate-600 transition-colors">
                  {perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR"
                    ? "AD"
                    : "EM"}
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">
          {/* Header Section */}
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-[#5b97a9] tracking-tight transition-colors duration-300">
                {activeTab === "liquidacion" && "Cálculo de Nómina"}
                {activeTab === "resumen" && "Revisión Final y Aprobación"}
                {activeTab === "historico" && "Archivo de Pagos Anteriores"}
                {activeTab === "auditoria" && "Registro de Auditoría y Telemetría"}
              </h1>
              <p className="mt-2 text-sm text-gray-600 max-w-2xl transition-colors duration-300">
                {activeTab === "liquidacion" &&
                  "Ingresa los días trabajados y novedades para calcular el pago de este periodo."}
                {activeTab === "resumen" &&
                  "Revisa el resumen de pagos y aprueba la nómina para generar los desprendibles."}
                {activeTab === "historico" &&
                  "Consulta las nóminas pasadas y descarga los comprobantes de pago de tus empleados."}
                {activeTab === "reportes" &&
                  "Consolida y exporta la facturación de nóminas (Acceso exclusivo Staff)."}
                {activeTab === "auditoria" &&
                  "Supervisa y analiza la trazabilidad completa y eventos del sistema (Acceso exclusivo SUPERADMIN)."}
              </p>
            </div>

            {/* Tabs Nav */}
            <div className="flex bg-slate-200/50 p-1 rounded-xl w-full md:w-auto self-start flex-wrap">
              <button
                onClick={() => setActiveTab("liquidacion")}
                className={`flex-1 md:flex-none px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "liquidacion" ? "bg-[#83a9b2] text-white shadow-md" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
              >
                1. Calcular Pagos
              </button>
              <button
                onClick={() => setActiveTab("resumen")}
                className={`flex-1 md:flex-none px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "resumen" ? "bg-[#83a9b2] text-white shadow-md" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
              >
                2. Revisar y Aprobar
              </button>
              <button
                onClick={() => setActiveTab("historico")}
                className={`flex-1 md:flex-none px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "historico" ? "bg-[#83a9b2] text-white shadow-md" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
              >
                3. Historial de Nóminas
              </button>
              {(perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR") && (
                <button
                  onClick={() => setActiveTab("reportes")}
                  className={`flex-1 md:flex-none px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "reportes" ? "bg-[#83a9b2] text-white shadow-md" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
                >
                  4. Reportes (Staff)
                </button>
              )}
              {perfilAportante?.rol === "SUPERADMIN" && (
                <button
                  onClick={() => setActiveTab("auditoria")}
                  className={`flex-1 md:flex-none px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "auditoria" ? "bg-[#83a9b2] text-white shadow-md" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
                >
                  5. Auditoría (Staff)
                </button>
              )}
            </div>
          </div>

          {activeTab === "liquidacion" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start w-full mb-12">
              {/* Formulario Section */}
              <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200/60 overflow-hidden">
                <div className="px-8 py-5 bg-[#5b97a9] text-white flex justify-between items-center flex-wrap gap-4">
                  <h3 className="text-lg font-bold flex items-center">
                    <svg
                      className="w-5 h-5 mr-2 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      ></path>
                    </svg>
                    Datos del Empleado
                  </h3>
                </div>

                <div className="bg-[#eef5f7] rounded-b-lg p-6 md:p-8 space-y-6 border-l border-r border-b border-[#5b97a9]/20">
                  {(() => {
                    const linkDriveValue = carpetaCliente ? String(carpetaCliente) : (perfilAportante?.carpeta_cliente ? String(perfilAportante.carpeta_cliente) : "");
                    const isValidLink = linkDriveValue &&
                      linkDriveValue.trim() !== "" &&
                      linkDriveValue !== "null" &&
                      linkDriveValue !== "None" &&
                      linkDriveValue.toLowerCase() !== "n/a";

                    return (
                      <div className="flex justify-end -mt-2 mb-2 gap-2">
                        {(perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR") && (
                          <button
                            type="button"
                            onClick={(e) => handleSyncEmpleado(e, selectedEmpleadoId)}
                            disabled={isSyncing || !selectedEmpleadoId}
                            className="border border-[#5b97a9] text-[#5b97a9] hover:bg-[#5b97a9] hover:text-white px-4 py-2 rounded-md font-bold flex items-center gap-2 transition-colors disabled:opacity-50"
                          >
                            {isSyncing ? "Sincronizando..." : "🔄 Sincronizar Empleado"}
                          </button>
                        )}
                        {isValidLink && (
                          <a
                            href={linkDriveValue}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="border border-[#5b97a9] text-[#5b97a9] hover:bg-[#5b97a9] hover:text-white px-4 py-2 rounded-md font-bold flex items-center gap-2 transition-colors"
                          >
                            📂 Ver Información Asociada
                          </a>
                        )}
                      </div>
                    );
                  })()}
                  <div className="space-y-6">
                    {/* Bloque: Parámetros del Periodo */}
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                      <h4 className="text-sm font-bold text-slate-700 mb-3 uppercase tracking-wide">
                        Periodo a Pagar
                      </h4>
                      <div className="flex flex-col md:flex-row gap-4">
                        <div className="flex-1">
                          <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Mes a pagar:
                          </label>
                          <select
                            value={periodoLiq}
                            onChange={(e) => setPeriodoLiq(e.target.value)}
                            className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                          >
                            {generarPeriodos().map((p) => (
                              <option key={p} value={p}>
                                {p}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="flex-1">
                          <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Quincena / Mensualidad a pagar:
                          </label>
                          <select
                            value={quincenaPago}
                            onChange={(e) => setQuincenaPago(e.target.value)}
                            disabled={
                              formData.PERIODO_PAGO?.toUpperCase() ===
                              "MENSUAL" ||
                              formData.PERIODO_PAGO?.toUpperCase() ===
                              "MENSUALIDAD"
                            }
                            className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none disabled:bg-slate-100 disabled:text-slate-500"
                          >
                            {formData.PERIODO_PAGO?.toUpperCase() !== "MENSUAL" &&
                              formData.PERIODO_PAGO?.toUpperCase() !==
                              "MENSUALIDAD" && (
                                <>
                                  <option value="1">Primera Quincena (Q1)</option>
                                  <option value="2">Segunda Quincena (Q2)</option>
                                </>
                              )}
                            {(formData.PERIODO_PAGO?.toUpperCase() ===
                              "MENSUAL" ||
                              formData.PERIODO_PAGO?.toUpperCase() ===
                              "MENSUALIDAD") && (
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
                          <svg
                            className={`w-4 h-4 mr-1 transform transition-transform ${mostrarNota ? "rotate-45 text-slate-400" : ""}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M12 4v16m8-8H4"
                            ></path>
                          </svg>
                          {mostrarNota
                            ? "Ocultar observación"
                            : "Añadir observación (Opcional)"}
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

                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3 gap-2">
                        <h4 className="text-sm font-bold text-slate-700 uppercase tracking-wide mb-0">
                          Datos del Empleador:{" "}
                          {perfilAportante?.razon_social || "Cargando..."}
                        </h4>
                        {(perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR") && (
                          <button
                            type="button"
                            onClick={handleSyncMasivo}
                            disabled={isSyncingMasivo || isSearching}
                            className="border border-[#5b97a9] text-[#5b97a9] hover:bg-[#5b97a9] hover:text-white px-3 py-1.5 rounded-md font-bold text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
                          >
                            {isSyncingMasivo ? "Sincronizando..." : "🔄 Sincronizar Empresa"}
                          </button>
                        )}
                      </div>

                      {(perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR") && (
                        <div className="flex flex-col md:flex-row gap-4 mt-4 border-t border-slate-200 pt-4">
                          <div className="flex-1">
                            <input
                              type="text"
                              value={empleadorId}
                              onChange={(e) => {
                                setEmpleadorId(e.target.value);
                                setSearchError(null);
                              }}
                              placeholder="NIT / Cédula del Empleador (Búsqueda Administrativa / Soporte)"
                              className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => handleSearchEmpleador("me", true)}
                            disabled={isSearching || !empleadorId.trim()}
                            className={`px-6 py-2.5 font-bold rounded-xl transition-all flex items-center justify-center min-w-[160px] ${isSearching || !empleadorId.trim()
                              ? "bg-slate-200 text-slate-500 cursor-not-allowed"
                              : "bg-unifika-primary text-white hover:bg-slate-800 shadow-sm"
                              }`}
                          >
                            {isSearching ? (
                              <>
                                <svg
                                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                                  xmlns="http://www.w3.org/2000/svg"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                >
                                  <circle
                                    className="opacity-25"
                                    cx="12"
                                    cy="12"
                                    r="10"
                                    stroke="currentColor"
                                    strokeWidth="4"
                                  ></circle>
                                  <path
                                    className="opacity-75"
                                    fill="currentColor"
                                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                  ></path>
                                </svg>
                                Buscando...
                              </>
                            ) : (
                              "Consultar"
                            )}
                          </button>
                        </div>
                      )}

                      {isSearching &&
                        perfilAportante?.rol !== "SUPERADMIN" &&
                        perfilAportante?.rol !== "ADMINISTRADOR" && (
                          <div className="flex items-center text-unifika-primary mt-2">
                            <svg
                              className="animate-spin -ml-1 mr-2 h-4 w-4"
                              xmlns="http://www.w3.org/2000/svg"
                              fill="none"
                              viewBox="0 0 24 24"
                            >
                              <circle
                                className="opacity-25"
                                cx="12"
                                cy="12"
                                r="10"
                                stroke="currentColor"
                                strokeWidth="4"
                              ></circle>
                              <path
                                className="opacity-75"
                                fill="currentColor"
                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                              ></path>
                            </svg>
                            <span className="text-sm font-medium">
                              Sincronizando empleados...
                            </span>
                          </div>
                        )}

                      {searchError && (
                        <div className="bg-red-50 border-l-4 border-red-500 p-4 text-red-700 mt-4 rounded">
                          {searchError}
                        </div>
                      )}

                      {empleadosEncontrados.length > 1 && (
                        <div className="mt-4 animate-fade-in border-t border-slate-200 pt-4">
                          <label className="block text-sm font-semibold text-slate-700 mb-2">
                            Seleccionar Empleado a Liquidar:
                          </label>
                          <select
                            value={selectedEmpleadoId}
                            onChange={handleSelectEmpleado}
                            className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                          >
                            <option value="">-- Seleccione un empleado --</option>
                            {empleadosEncontrados.map((empleado) => (
                              <option
                                key={empleado.ID_CONTRATO}
                                value={empleado.ID_CONTRATO}
                              >
                                {empleado.NOMBRE_EMPLEADO} (
                                {empleado.TIPO_CONTRATO}) - {empleado.ID_EMPLEADO}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {empleadosEncontrados.length === 1 && (
                        <div className="mt-4 animate-fade-in border-t border-slate-200 pt-4">
                          <label className="block text-sm font-semibold text-slate-700 mb-2">
                            Empleado a Liquidar:
                          </label>
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
                    <form
                      onSubmit={handleLiquidarNomina}
                      className="animate-fade-in-up space-y-6"
                    >
                      {/* SECCIÓN 1: REPORTE DE NOVEDADES */}
                      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                        <div className="px-6 py-4 bg-white border-b border-slate-100">
                          <h3 className="text-lg font-bold text-slate-800">
                            Novedades del Periodo (Permisos, Faltas, Extras)
                          </h3>
                          <p className="text-sm text-slate-500 mt-1">
                            Campos editables para el periodo actual
                          </p>
                        </div>

                        <div className="p-6">
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                            {/* Días Laborados */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">
                                Días Laborados
                              </label>
                              <input
                                type="number"
                                name="DIAS_LABORADOS"
                                value={formData.DIAS_LABORADOS}
                                onChange={handleInputChange}
                                min="0"
                                max={
                                  formData.PERIODO_PAGO?.toLowerCase() ===
                                    "quincenal"
                                    ? 15
                                    : 30
                                }
                                step="any"
                                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                                required
                              />
                            </div>

                            {/* Días Vacaciones */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">
                                Días Vacaciones
                              </label>
                              <input
                                type="number"
                                name="DIAS_VACACIONES"
                                value={formData.DIAS_VACACIONES || 0}
                                readOnly
                                className="w-full px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-slate-500 cursor-not-allowed outline-none"
                                required
                              />
                            </div>

                            {/* Días Incapacidad */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">
                                Días Incapacidad
                              </label>
                              <input
                                type="number"
                                name="DIAS_INCAPACIDAD"
                                value={formData.DIAS_INCAPACIDAD || 0}
                                readOnly
                                className="w-full px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-slate-500 cursor-not-allowed outline-none"
                                required
                              />
                            </div>
                            
                            {/* Días Licencia */}
                            <div>
                              <label className="block text-sm font-semibold text-slate-700 mb-2">Días Licencia</label>
                              <input 
                                type="number" 
                                name="DIAS_LICENCIA"
                                value={formData.DIAS_LICENCIA || 0} 
                                readOnly 
                                className="w-full px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-slate-500 cursor-not-allowed outline-none" 
                              />
                            </div>
                          </div>

                          <div className="mt-4 flex justify-end">
                            <button
                              type="button"
                              onClick={() => setIsAusentismoModalOpen(true)}
                              className="px-5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold rounded-xl transition-colors border border-indigo-200 flex items-center gap-2 text-sm"
                            >
                              📅 Gestionar Ausentismos
                            </button>
                          </div>

                          {/* NOVEDADES: EXTRAS Y PRÉSTAMOS */}
                          <div className="mt-6 pt-6 border-t border-slate-100">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                              {/* HORAS EXTRAS */}
                              <div className="bg-white shadow-sm rounded-xl border border-slate-200 p-5">
                                <h4 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wide">
                                  Horas Extras y Recargos
                                </h4>
                                <div className="mb-4">
                                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                                    ¿Reportar Extras y Recargos?
                                  </label>
                                  <select
                                    name="REPORTAR_EXTRAS"
                                    value={formData.REPORTAR_EXTRAS}
                                    onChange={handleInputChange}
                                    className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                                  >
                                    <option value="NO">No</option>
                                    <option value="SI">Sí</option>
                                  </select>
                                </div>

                                {formData.REPORTAR_EXTRAS === "SI" && (
                                  <div className="grid grid-cols-2 gap-4 animate-fade-in pt-2">
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        H. Extras Diurnas
                                      </label>
                                      <input
                                        type="number"
                                        name="HED"
                                        value={formData.HED}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        H. Extras Nocturnas
                                      </label>
                                      <input
                                        type="number"
                                        name="HEN"
                                        value={formData.HEN}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        H. Extras Diurnas Festivas
                                      </label>
                                      <input
                                        type="number"
                                        name="HEDF"
                                        value={formData.HEDF}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        H. Extras Nocturnas Festivas
                                      </label>
                                      <input
                                        type="number"
                                        name="HENF"
                                        value={formData.HENF}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        Recargos Nocturnos
                                      </label>
                                      <input
                                        type="number"
                                        name="RN"
                                        value={formData.RN}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        Recargos Diurnos Festivos
                                      </label>
                                      <input
                                        type="number"
                                        name="RDN"
                                        value={formData.RDN}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                    <div>
                                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                                        Recargos Nocturnos Festivos
                                      </label>
                                      <input
                                        type="number"
                                        name="RNF"
                                        value={formData.RNF}
                                        onChange={handleInputChange}
                                        min="0"
                                        step="any"
                                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-unifika-primary outline-none"
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>

                              {/* PRÉSTAMOS */}
                              <div className="bg-white shadow-sm rounded-xl border border-slate-200 p-5">
                                <h4 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wide">
                                  Otros Descuentos (Anticipos, Préstamos, Alimentación, etc.)
                                </h4>
                                <div className="flex flex-col gap-4">
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      ¿Aplicar algún descuento en este periodo?
                                    </label>
                                    <select
                                      name="CON_PRESTAMO"
                                      value={formData.CON_PRESTAMO}
                                      onChange={handleInputChange}
                                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-xl focus:bg-white focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary transition-all text-slate-900 outline-none"
                                    >
                                      <option value="NO">No</option>
                                      <option value="SI">Sí</option>
                                    </select>
                                  </div>
                                  {formData.CON_PRESTAMO === "SI" && (
                                    <div className="animate-fade-in pt-2">
                                      <label className="block text-sm font-semibold text-slate-700 mb-2">
                                        Valor Total a Descontar ($)
                                      </label>
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
                      <div className="shadow-sm rounded-lg">
                        <button
                          type="button"
                          onClick={() => setIsContractOpen(!isContractOpen)}
                          className={`w-full px-6 py-4 bg-[#5b97a9] hover:bg-[#4b8293] transition-colors duration-200 flex justify-between items-center outline-none cursor-pointer ${isContractOpen ? "rounded-t-lg" : "rounded-lg"}`}
                        >
                          <div className="flex items-center text-left">
                            <svg
                              className="w-5 h-5 mr-3 text-white"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                              ></path>
                            </svg>
                            <div>
                              <h3 className="text-base font-bold text-white">
                                Condiciones de Contratación
                              </h3>
                            </div>
                          </div>
                          <svg
                            className={`w-5 h-5 text-white transform transition-transform duration-300 ${isContractOpen ? "rotate-180" : "rotate-0"}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M19 9l-7 7-7-7"
                            ></path>
                          </svg>
                        </button>

                        {isContractOpen && (
                          <div className="p-5 bg-slate-100 shadow-inner border-x border-b border-[#5b97a9]/20 rounded-b-lg animate-fade-in">
                            <div className="mb-6 flex items-start gap-2 p-3 text-sm text-amber-800 bg-amber-100 border border-amber-200 rounded-md">
                              <svg
                                className="w-5 h-5 flex-shrink-0 mt-0.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                                ></path>
                              </svg>
                              <p className="italic">
                                Nota: Las condiciones contractuales provienen
                                directamente del sistema maestro. Cualquier
                                modificación requiere la elaboración de un "Otro
                                Sí" al contrato y debe gestionarse a través de
                                nuestros canales de atención.
                              </p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {/* BLOQUE FIJO INICIAL (Siempre visible - Fila 1) */}
                              <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-2">
                                  Cargo Desempeñado
                                </label>
                                <input
                                  type="text"
                                  value={formData.CARGO_DESEMPENEADO}
                                  readOnly
                                  className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                />
                              </div>
                              <div>
                                <label className="block text-sm font-semibold text-slate-700 mb-2">
                                  Periodo de Pago
                                </label>
                                <input
                                  type="text"
                                  value={formData.PERIODO_PAGO}
                                  readOnly
                                  className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                />
                              </div>

                              {/* RENDERIZADO CONDICIONAL BASADO EN SMLV */}
                              {formData.ES_SMLV?.toLowerCase()
                                .normalize("NFD")
                                .replace(/[\u0300-\u036f]/g, "") === "si" ? (
                                <>
                                  {/* CASO A: SMLV es SÍ (Estructura compacta de 2 filas) */}
                                  {/* Fila 2 */}
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      ¿Salario Mínimo?
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.ES_SMLV}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      Tiene Aux. Transporte
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.TIENE_AUX}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>
                                </>
                              ) : (
                                <>
                                  {/* CASO B: SMLV es NO (Estructura completa de 4 filas) */}
                                  {/* Fila 2 */}
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      ¿Salario Mínimo?
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.ES_SMLV}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      Salario Base ($)
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.SALARIO_BASE}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>

                                  {/* Fila 3 */}
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      ¿Bono Salarial?
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.CON_BONO}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>
                                  {formData.CON_BONO?.toLowerCase()
                                    .normalize("NFD")
                                    .replace(/[\u0300-\u036f]/g, "") === "si" && (
                                      <div>
                                        <label className="block text-sm font-semibold text-slate-700 mb-2">
                                          Valor del Bono ($)
                                        </label>
                                        <input
                                          type="text"
                                          value={formData.VLR_BONO}
                                          readOnly
                                          className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                        />
                                      </div>
                                    )}

                                  {/* Fila 4 */}
                                  <div>
                                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                                      Tiene Aux. Transporte
                                    </label>
                                    <input
                                      type="text"
                                      value={formData.TIENE_AUX}
                                      readOnly
                                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                    />
                                  </div>
                                  {formData.TIPO_CONTRATO?.toLowerCase().trim() ===
                                    "empleado interno" && (
                                      <div>
                                        <label className="block text-sm font-semibold text-slate-700 mb-2">
                                          Salario en Especie ($)
                                        </label>
                                        <input
                                          type="text"
                                          value={formData.SALARIO_ESPECIE}
                                          readOnly
                                          className="w-full px-4 py-2.5 bg-gray-200 text-gray-500 border border-gray-300 rounded-xl cursor-not-allowed outline-none"
                                        />
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
                          <svg
                            className="w-5 h-5 mr-3 flex-shrink-0"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                              clipRule="evenodd"
                            />
                          </svg>
                          {error}
                        </div>
                      )}

                      <div className="mt-10 flex justify-end">
                        <button
                          type="submit"
                          disabled={isLoading}
                          className={`inline-flex items-center justify-center px-12 py-4 font-bold text-white transition-colors duration-200 rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#babf15] ${isLoading ? "bg-slate-400 cursor-not-allowed" : "bg-[#babf15] hover:bg-[#a2a812]"}`}
                        >
                          {isLoading ? (
                            <>
                              <svg
                                className="animate-spin -ml-1 mr-3 h-5 w-5 text-slate-500"
                                xmlns="http://www.w3.org/2000/svg"
                                fill="none"
                                viewBox="0 0 24 24"
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                ></circle>
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                ></path>
                              </svg>
                              Procesando...
                            </>
                          ) : (
                            <>
                              <svg
                                className="w-5 h-5 mr-2"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                                />
                              </svg>
                              Liquidar Nómina
                            </>
                          )}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>

              {/* Sección de Resultados */}
              {selectedEmpleadoId && (
                <div className="lg:col-span-1 bg-white rounded-2xl shadow-md border border-slate-100 sticky top-28 h-auto overflow-hidden animate-fade-in-up">
                  {resultado ? (
                    <div className="transform transition-all animate-fade-in-up flex flex-col">
                      {/* Header Resultado */}
                      <div className="bg-gradient-to-r from-unifika-primary to-slate-800 px-6 py-5 text-white relative flex-shrink-0">
                        <div className="absolute top-0 right-0 -mt-6 -mr-6 w-32 h-32 bg-white opacity-5 rounded-full blur-2xl"></div>
                        <h3 className="text-lg font-bold mb-1 relative z-10 text-unifika-accent">
                          Resumen de Liquidación
                        </h3>
                        <p className="text-slate-100 text-sm font-semibold relative z-10 flex items-center mt-2 bg-black/20 p-2 rounded-lg">
                          <svg
                            className="w-4 h-4 mr-2 text-emerald-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                            ></path>
                          </svg>
                          Empleado:{" "}
                          {empleadosEncontrados.find(
                            (e) => e.ID_CONTRATO === resultado.ID_CONTRATO,
                          )?.NOMBRE_EMPLEADO ||
                            resultado.NOMBRE_EMPLEADO ||
                            resultado.ID_CONTRATO}
                        </p>
                      </div>

                      {/* Dos Columnas: Devengados y Deducciones */}
                      <div className="p-5 grid grid-cols-1 xl:grid-cols-2 gap-6">
                        {/* Columna Izquierda: Devengados */}
                        <div>
                          <h4 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3 border-b-2 border-slate-100 pb-2 flex items-center">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2"></span>{" "}
                            Ingresos
                          </h4>
                          <div className="space-y-2">
                            <div className="flex justify-between text-xs sm:text-sm">
                              <span className="text-slate-600">
                                Sueldo Básico
                              </span>
                              <span className="font-medium text-slate-900">
                                $
                                {(
                                  resultado.SUELDO_EFECTIVO_PAGADO || 0
                                ).toLocaleString("es-CO")}
                              </span>
                            </div>
                            {resultado.SALARIO_ESPECIE_MES > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">En Especie</span>
                                <span className="font-medium text-slate-900">
                                  $
                                  {resultado.SALARIO_ESPECIE_MES.toLocaleString(
                                    "es-CO",
                                  )}
                                </span>
                              </div>
                            )}
                            <div className="flex justify-between text-xs sm:text-sm">
                              <span className="text-slate-600">Aux. Transp.</span>
                              <span className="font-medium text-slate-900">
                                $
                                {(resultado.VAL_AUX_TTE || 0).toLocaleString(
                                  "es-CO",
                                )}
                              </span>
                            </div>
                            {resultado.VALOR_VACACIONES > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">Vacaciones</span>
                                <span className="font-medium text-slate-900">
                                  $
                                  {resultado.VALOR_VACACIONES.toLocaleString(
                                    "es-CO",
                                  )}
                                </span>
                              </div>
                            )}
                            {resultado.VALOR_INCAPACIDAD > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">
                                  Incapacidad
                                </span>
                                <span className="font-medium text-slate-900">
                                  $
                                  {resultado.VALOR_INCAPACIDAD.toLocaleString(
                                    "es-CO",
                                  )}
                                </span>
                              </div>
                            )}
                            {resultado.VALOR_BONO > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">Bono</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VALOR_BONO.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_HED > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">H.E.D</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_HED.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_HEN > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">H.E.N</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_HEN.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_HEDF > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">H.E.D.F</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_HEDF.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_HENF > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">H.E.N.F</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_HENF.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_RN > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">R.N</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_RN.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_RDN > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">R.D.F</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_RDN.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.VLR_RNF > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">R.N.F</span>
                                <span className="font-medium text-slate-900">
                                  ${resultado.VLR_RNF.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}

                            <div className="flex flex-col mt-3 pt-3 border-t-2 border-slate-100 bg-emerald-50/50 p-2 rounded-lg">
                              <span className="text-slate-800 text-xs font-bold mb-1">
                                T. Devengado
                              </span>
                              <span className="text-emerald-700 text-sm font-black">
                                $
                                {(resultado.TOTAL_DEVENGADO || 0).toLocaleString(
                                  "es-CO",
                                )}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Columna Derecha: Deducciones */}
                        <div>
                          <h4 className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3 border-b-2 border-slate-100 pb-2 flex items-center">
                            <span className="w-2 h-2 rounded-full bg-rose-500 mr-2"></span>{" "}
                            Descuentos
                          </h4>
                          <div className="space-y-2">
                            <div className="flex justify-between text-xs sm:text-sm">
                              <span className="text-slate-600">Salud (4%)</span>
                              <span className="font-medium text-slate-900">
                                -$
                                {(resultado.SALUD_4 || 0).toLocaleString("es-CO")}
                              </span>
                            </div>
                            <div className="flex justify-between text-xs sm:text-sm">
                              <span className="text-slate-600">Pensión (4%)</span>
                              <span className="font-medium text-slate-900">
                                -$
                                {(resultado.PENSION_4 || 0).toLocaleString(
                                  "es-CO",
                                )}
                              </span>
                            </div>
                            {resultado.PRESTAMOS > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">Préstamos</span>
                                <span className="font-medium text-slate-900">
                                  -${resultado.PRESTAMOS.toLocaleString("es-CO")}
                                </span>
                              </div>
                            )}
                            {resultado.SALARIO_ESPECIE_MES > 0 && (
                              <div className="flex justify-between text-xs sm:text-sm">
                                <span className="text-slate-600">
                                  Desc. Especie
                                </span>
                                <span className="font-medium text-slate-900">
                                  -$
                                  {resultado.SALARIO_ESPECIE_MES.toLocaleString(
                                    "es-CO",
                                  )}
                                </span>
                              </div>
                            )}

                            <div className="flex flex-col mt-3 pt-3 border-t-2 border-slate-100 bg-rose-50/50 p-2 rounded-lg">
                              <span className="text-slate-800 text-xs font-bold mb-1">
                                T. Deducciones
                              </span>
                              <span className="text-rose-600 text-sm font-black">
                                -$
                                {(
                                  (resultado.TOTAL_DEDUCIDO || 0) +
                                  (resultado.SALARIO_ESPECIE_MES || 0)
                                ).toLocaleString("es-CO")}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Footer Full Width: Neto a Pagar */}
                      <div className="bg-unifika-primary px-6 py-6 mt-2">
                        <div className="flex flex-col items-start text-white">
                          <p className="text-xs text-unifika-accent uppercase tracking-widest font-bold mb-2">
                            Valor a transferir
                          </p>
                          <p className="text-3xl sm:text-4xl font-black tracking-tight text-white drop-shadow-md">
                            ${(resultado.NETO_PAGAR || 0).toLocaleString("es-CO")}
                          </p>
                        </div>
                      </div>

                      {/* Nuevos botones: Guardar y Descargar PDF */}
                      <div className="p-5 bg-slate-50 border-t border-slate-200 flex flex-col gap-3">
                        {saveMessage && (
                          <div
                            className={`p-3 rounded text-sm ${saveMessage.type === "success" ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : "bg-red-100 text-red-800 border border-red-200"}`}
                          >
                            {saveMessage.text}
                          </div>
                        )}
                        {isCerrado ? (
                          <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded shadow-sm text-amber-800">
                            <p className="font-bold flex items-center gap-2 mb-1">
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                              Nómina Cerrada
                            </p>
                            <p className="text-sm">Esta nómina ya se encuentra CERRADA y no puede ser modificada. Puede descargar una copia del desprendible en la pestaña '3. Historial de Nóminas'.</p>
                          </div>
                        ) : (
                          <div className="flex flex-col sm:flex-row gap-3">
                            <button
                              onClick={handleGuardarYDescargar}
                              disabled={isSaving || isDownloading}
                              className={`flex-1 flex items-center justify-center px-4 py-2.5 text-sm font-bold rounded-xl transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 ${(isSaving || isDownloading) ? "bg-slate-200 text-slate-500 cursor-not-allowed" : "bg-emerald-600 hover:bg-emerald-700 text-white"}`}
                            >
                              {(isSaving || isDownloading) ? (
                                <>
                                  <svg
                                    className="animate-spin -ml-1 mr-2 h-4 w-4 text-slate-500"
                                    xmlns="http://www.w3.org/2000/svg"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                  >
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Procesando...
                                </>
                              ) : "Guardar y Descargar Desprendible"}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="p-10 flex flex-col items-center justify-center text-center h-full min-h-[350px]">
                      <div className="w-20 h-20 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mb-5 text-slate-300">
                        <svg
                          className="w-10 h-10"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="1.5"
                            d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                      </div>
                      <h3 className="text-xl font-bold text-slate-700 mb-2">
                        Sin Resultados
                      </h3>
                      <p className="text-sm text-slate-500 max-w-[200px] leading-relaxed">
                        Completa el formulario y presiona{" "}
                        <strong>Liquidar</strong>.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "resumen" && (
            <ResumenNomina
              periodo={periodoLiq}
              quincena={quincenaPago}
              idAportante={empleadorId}
              onRowClick={handleRowClick}
              perfilAportante={perfilAportante}
              refreshKey={refreshResumenKey}
            />
          )}

          {activeTab === "historico" && (
            <DashboardHistorico idAportante={empleadorId} />
          )}

          {activeTab === "reportes" && (perfilAportante?.rol === "SUPERADMIN" || perfilAportante?.rol === "ADMINISTRADOR") && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 w-full mt-8 overflow-hidden">
              <div className="px-6 py-5 bg-[#5b97a9] text-white flex justify-between items-center">
                <h2 className="text-xl font-bold">Reporte de Nóminas Generadas</h2>
              </div>
              
              <div className="p-6">
                {/* Tarjetas de Resumen */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Registros Visibles</p>
                      <p className="text-2xl font-black text-slate-800">{datosFiltrados.length}</p>
                    </div>
                    <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                    </div>
                  </div>
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Sumatoria Devengos</p>
                      <p className="text-2xl font-black text-emerald-600">${totalDevengadoFiltrado.toLocaleString()}</p>
                    </div>
                    <div className="w-10 h-10 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </div>
                  </div>
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Sumatoria IBC</p>
                      <p className="text-2xl font-black text-indigo-600">${totalIbcFiltrado.toLocaleString()}</p>
                    </div>
                    <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-4 border-b border-slate-100 pb-6">
                  <div className="flex flex-col md:flex-row gap-3 items-center w-full md:w-auto">
                    <label className="text-sm font-semibold text-slate-700">Periodo:</label>
                    <select
                      value={reportePeriodo}
                      onChange={(e) => setReportePeriodo(e.target.value)}
                      className="px-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary outline-none"
                    >
                      {generarPeriodos().map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                    <select
                      value={reporteQuincena}
                      onChange={(e) => setReporteQuincena(e.target.value)}
                      className="px-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-unifika-primary outline-none"
                    >
                      <option value="1">Quincena 1</option>
                      <option value="2">Quincena 2</option>
                      <option value="M">Mensualidad (M)</option>
                    </select>
                    <button
                      onClick={handleConsultarReporte}
                      disabled={isFetchingReporte}
                      className="px-6 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-xl transition-colors disabled:opacity-50"
                    >
                      {isFetchingReporte ? "Consultando..." : "Consultar"}
                    </button>
                  </div>

                  <div className="flex flex-col md:flex-row gap-3 items-center w-full md:w-auto">
                    <input
                      type="text"
                      placeholder="Buscar por Empleado, Empresa, ID o Tipo Contrato..."
                      value={reporteFiltro}
                      onChange={handleFiltroChange}
                      className="px-4 py-2 border border-slate-300 rounded-xl w-full md:w-64 focus:ring-2 focus:ring-unifika-primary outline-none"
                    />
                    <button
                      onClick={handleExportarCSVLocal}
                      disabled={datosFiltrados.length === 0}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                      Exportar CSV
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto max-h-[600px] border border-slate-200 rounded-xl">
                  <table className="w-full text-sm text-left text-slate-600 border-collapse">
                    <thead className="text-xs text-slate-700 uppercase bg-slate-100 border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                      <tr>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("razon_social")}>
                          <div className="flex items-center gap-1">Empresa {sortConfig.key === "razon_social" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("id_contrato")}>
                          <div className="flex items-center gap-1">ID Contrato {sortConfig.key === "id_contrato" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("nombre_empleado")}>
                          <div className="flex items-center gap-1">Empleado {sortConfig.key === "nombre_empleado" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("tipo_contrato")}>
                          <div className="flex items-center gap-1">T. Contrato {sortConfig.key === "tipo_contrato" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("dias_laborados")}>
                          <div className="flex items-center justify-center gap-1">Lab. {sortConfig.key === "dias_laborados" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("dias_incapacidad")}>
                          <div className="flex items-center justify-center gap-1">Inc. {sortConfig.key === "dias_incapacidad" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("dias_vacaciones")}>
                          <div className="flex items-center justify-center gap-1">Vac. {sortConfig.key === "dias_vacaciones" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("ibc_pila")}>
                          <div className="flex items-center gap-1">IBC {sortConfig.key === "ibc_pila" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("total_devengado")}>
                          <div className="flex items-center gap-1">Devengado {sortConfig.key === "total_devengado" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("total_deducido")}>
                          <div className="flex items-center gap-1">Deducido {sortConfig.key === "total_deducido" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("neto_pagar")}>
                          <div className="flex items-center gap-1">Neto {sortConfig.key === "neto_pagar" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors" onClick={() => handleSort("estado_cierre")}>
                          <div className="flex items-center justify-center gap-1">Estado {sortConfig.key === "estado_cierre" && (sortConfig.direction === "ascending" ? "▲" : "▼")}</div>
                        </th>
                        <th className="px-4 py-3 text-center text-slate-700">ACCIÓN</th>
                      </tr>
                    </thead>
                    <tbody>
                      {isFetchingReporte ? (
                        <tr>
                          <td colSpan="13" className="px-4 py-8 text-center text-slate-500">
                            <div className="flex justify-center items-center gap-2">
                              <svg className="animate-spin h-5 w-5 text-unifika-primary" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                              Cargando datos...
                            </div>
                          </td>
                        </tr>
                      ) : paginatedData.length === 0 ? (
                        <tr>
                          <td colSpan="13" className="px-4 py-8 text-center text-slate-500">
                            {reporteData.length === 0 ? "No hay datos para el periodo seleccionado." : "No se encontraron coincidencias para tu búsqueda."}
                          </td>
                        </tr>
                      ) : (
                        paginatedData.map((item, idx) => (
                          <tr key={idx} className="bg-white border-b border-slate-100 hover:bg-slate-50 transition-colors whitespace-nowrap">
                            <td className="px-4 py-3 font-medium text-slate-800">{item.razon_social}</td>
                            <td className="px-4 py-3 font-mono text-xs text-slate-500">{item.id_contrato}</td>
                            <td className="px-4 py-3 max-w-[200px] truncate" title={item.nombre_empleado}>{item.nombre_empleado}</td>
                            <td className="px-4 py-3 text-xs text-slate-500">{item.tipo_contrato}</td>
                            <td className="px-4 py-3 text-center">{item.dias_laborados}</td>
                            <td className="px-4 py-3 text-center">{item.dias_incapacidad}</td>
                            <td className="px-4 py-3 text-center">{item.dias_vacaciones}</td>
                            <td className="px-4 py-3 text-slate-600 font-medium">${item.ibc_pila?.toLocaleString()}</td>
                            <td className="px-4 py-3 text-emerald-600 font-medium">${item.total_devengado?.toLocaleString()}</td>
                            <td className="px-4 py-3 text-rose-600 font-medium">${item.total_deducido?.toLocaleString()}</td>
                            <td className="px-4 py-3 font-bold">${item.neto_pagar?.toLocaleString()}</td>
                            <td className="px-4 py-3 text-center">
                              <span className={`px-2 py-1 rounded-full text-[10px] font-bold ${item.estado_cierre === "CERRADA" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                                {item.estado_cierre}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center">
                              <button
                                onClick={() => handleEditarDesdeReporte(item)}
                                className="text-emerald-600 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded p-1.5 transition-colors"
                                title="Editar liquidación"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Controles de Paginación */}
                {totalPages > 0 && (
                  <div className="flex flex-col sm:flex-row justify-between items-center mt-4 gap-4">
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <span>Mostrar</span>
                      <select 
                        value={itemsPerPage} 
                        onChange={handleItemsPerPageChange}
                        className="border border-slate-300 rounded px-2 py-1 outline-none focus:border-unifika-primary"
                      >
                        <option value={10}>10</option>
                        <option value={15}>15</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                      </select>
                      <span>registros</span>
                    </div>

                    <div className="text-sm text-slate-600 font-medium">
                      Página {currentPage} de {totalPages}
                    </div>

                    <div className="flex gap-2">
                      <button 
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        className="px-3 py-1 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Anterior
                      </button>
                      <button 
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        className="px-3 py-1 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Siguiente
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "auditoria" && perfilAportante?.rol === "SUPERADMIN" && (
            <DashboardAuditoria />
          )}
        </main>
      </div>

      {/* MODAL GESTION DE AUSENTISMOS */}
      {isAusentismoModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <span>📅</span> Gestión de Ausentismos
              </h3>
              <button
                onClick={() => {
                  setIsAusentismoModalOpen(false);
                  setTramitarReembolso(false);
                  setSoporteMedico(null);
                }}
                className="text-slate-400 hover:text-slate-600 transition-colors p-1"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto">
              <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1 uppercase tracking-wider">Tipo de Novedad</label>
                    <select
                      value={nuevoAusentismo.tipo_novedad}
                      onChange={(e) => {
                        setNuevoAusentismo({...nuevoAusentismo, tipo_novedad: e.target.value});
                        setTramitarReembolso(false);
                        setSoporteMedico(null);
                      }}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    >
                      <option value="Incapacidad">Incapacidad</option>
                      <option value="Vacaciones">Vacaciones</option>
                      <option value="Licencia No Remunerada">Licencia No Remunerada</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1 uppercase tracking-wider">Fecha Inicio</label>
                    <input
                      type="date"
                      value={nuevoAusentismo.fecha_inicio}
                      onChange={(e) => setNuevoAusentismo({...nuevoAusentismo, fecha_inicio: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1 uppercase tracking-wider">Fecha Fin</label>
                    <input
                      type="date"
                      value={nuevoAusentismo.fecha_fin}
                      onChange={(e) => setNuevoAusentismo({...nuevoAusentismo, fecha_fin: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    />
                  </div>
                </div>

                {/* Renderizado Condicional: Incapacidad y Reembolso */}
                {nuevoAusentismo.tipo_novedad === "Incapacidad" && (
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-white p-4 rounded-xl border border-indigo-50">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="tramitarReembolso"
                        checked={tramitarReembolso}
                        onChange={(e) => setTramitarReembolso(e.target.checked)}
                        className="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500 cursor-pointer"
                      />
                      <label htmlFor="tramitarReembolso" className="text-sm font-semibold text-slate-700 cursor-pointer">
                        Deseo tramitar el reembolso ante la EPS
                      </label>
                    </div>
                    
                    {tramitarReembolso && (
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1 uppercase tracking-wider">
                          Soporte Médico (Obligatorio &gt; 2 días)
                        </label>
                        <input
                          type="file"
                          accept=".pdf, image/*"
                          onChange={(e) => setSoporteMedico(e.target.files[0] || null)}
                          className="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
                        />
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    onClick={async () => {
                      if (!nuevoAusentismo.fecha_inicio || !nuevoAusentismo.fecha_fin) {
                        toast.error("Por favor ingresa fecha de inicio y fin.");
                        return;
                      }
                      if (nuevoAusentismo.fecha_inicio > nuevoAusentismo.fecha_fin) {
                        toast.error("La fecha de inicio no puede ser mayor a la fecha de fin.");
                        return;
                      }

                      // Cálculo de días nativo para validación
                      const ms = new Date(nuevoAusentismo.fecha_fin) - new Date(nuevoAusentismo.fecha_inicio);
                      const dias = Math.ceil(ms / (1000 * 60 * 60 * 24)) + 1;

                      // Validación estricta para Incapacidades
                      if (nuevoAusentismo.tipo_novedad === "Incapacidad" && tramitarReembolso) {
                        if (dias >= 3 && dias <= 180) {
                          if (!soporteMedico) {
                            toast.error("Debe adjuntar el certificado médico para tramitar el reembolso ante la EPS.");
                            return;
                          }
                        }
                      }
                      
                      const targetId = selectedEmpleadoId || formData.ID_CONTRATO;
                      if (!targetId) {
                        toast.error("No hay un empleado seleccionado.");
                        return;
                      }

                      const formDataToSend = new FormData();
                      formDataToSend.append("tipo_novedad", nuevoAusentismo.tipo_novedad);
                      formDataToSend.append("fecha_inicio", nuevoAusentismo.fecha_inicio);
                      formDataToSend.append("fecha_fin", nuevoAusentismo.fecha_fin);
                      formDataToSend.append("tramitar_reembolso", nuevoAusentismo.tipo_novedad === "Incapacidad" ? tramitarReembolso : false);
                      if (periodoLiq) formDataToSend.append("periodo_liq", periodoLiq);
                      if (quincenaPago) formDataToSend.append("quincena_pago", quincenaPago);
                      
                      if (soporteMedico) {
                        formDataToSend.append("soporte_medico", soporteMedico);
                      }

                      const loadingToast = toast.loading("Guardando ausentismo en la nube...");
                      try {
                        const response = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/empleado/${encodeURIComponent(targetId)}/ausentismos`, {
                          method: 'POST',
                          body: formDataToSend
                        });
                        
                        toast.dismiss(loadingToast);
                        
                        if (!response.ok) {
                          const errData = await response.json();
                          toast.error(errData.detail || "Error al guardar el ausentismo");
                          return;
                        }
                        
                        const dataGuardada = await response.json();
                        const responseData = dataGuardada.data || dataGuardada;
                        
                        const nuevaLista = [...ausentismosLocales, { 
                          ...nuevoAusentismo, 
                          tramitar_reembolso: responseData.tramitar_reembolso ?? tramitarReembolso,
                          soporte_url: responseData.soporte_url,
                          id_temp: responseData.id_ausentismo || Date.now().toString() 
                        }];
                        setAusentismosLocales(nuevaLista);
                        
                        // Limpieza
                        setNuevoAusentismo({ tipo_novedad: "Incapacidad", fecha_inicio: "", fecha_fin: "" });
                        setTramitarReembolso(false);
                        setSoporteMedico(null);
                        toast.success("Ausentismo sincronizado exitosamente.");
                        
                      } catch (error) {
                        toast.dismiss(loadingToast);
                        toast.error(error.response?.data?.detail || error.message || "Error al intentar guardar.");
                      }
                    }}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg transition-colors text-sm"
                  >
                    + Agregar Rango
                  </button>
                </div>
              </div>

              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] font-bold">
                    <tr>
                      <th className="px-4 py-3">Tipo</th>
                      <th className="px-4 py-3">Inicio</th>
                      <th className="px-4 py-3">Fin</th>
                      <th className="px-4 py-3 text-center">Días</th>
                      <th className="px-4 py-3 text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {ausentismosLocales.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="px-4 py-6 text-center text-slate-400">No has agregado ausentismos para este periodo.</td>
                      </tr>
                    ) : (
                      ausentismosLocales.map((aus, idx) => {
                        const ms = new Date(aus.fecha_fin) - new Date(aus.fecha_inicio);
                        const dias = Math.ceil(ms / (1000 * 60 * 60 * 24)) + 1;
                        return (
                          <tr key={aus.id_temp || idx} className="hover:bg-slate-50">
                            <td className="px-4 py-3 font-medium text-slate-700">{aus.tipo_novedad}</td>
                            <td className="px-4 py-3 text-slate-600">{aus.fecha_inicio}</td>
                            <td className="px-4 py-3 text-slate-600">{aus.fecha_fin}</td>
                            <td className="px-4 py-3 text-center font-bold text-slate-800">{dias}</td>
                            <td className="px-4 py-3 text-center flex justify-center items-center space-x-2">
                              {(aus.soporte_url || aus.tramitar_reembolso) && (
                                <button
                                  onClick={async () => {
                                    try {
                                      const loadingToast = toast.loading("Obteniendo documento...");
                                      const targetId = aus.id_ausentismo || aus.id_temp;
                                      const response = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/ausentismos/${encodeURIComponent(targetId)}/soporte`);
                                      toast.dismiss(loadingToast);
                                      
                                      if (response.ok) {
                                        const data = await response.json();
                                        window.open(data.url, '_blank');
                                      } else {
                                        const errorData = await response.json().catch(() => ({}));
                                        toast.error(errorData.detail || "No se pudo obtener el soporte médico");
                                      }
                                    } catch (err) {
                                      console.error("Error al abrir soporte:", err);
                                      toast.dismiss();
                                      const msj = err.response?.data?.detail || "Error al intentar abrir el soporte";
                                      toast.error(msj);
                                    }
                                  }}
                                  className="text-indigo-500 hover:text-indigo-700 p-1 transition-colors"
                                  title="Ver Soporte Médico"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                                </button>
                              )}
                              <button
                                onClick={async () => {
                                  try {
                                    const targetId = aus.id_ausentismo || aus.id_temp;
                                    const response = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/ausentismos/${encodeURIComponent(targetId)}`, {
                                      method: 'DELETE'
                                    });
                                    if (response.ok) {
                                      const newList = ausentismosLocales.filter(a => (a.id_ausentismo || a.id_temp) !== targetId);
                                      setAusentismosLocales(newList);
                                      toast.success("Ausentismo eliminado");
                                    } else {
                                      const errData = await response.json().catch(() => ({}));
                                      toast.error(errData.detail || "Error al eliminar en el servidor");
                                    }
                                  } catch (error) {
                                    console.error("Error eliminando ausentismo:", error);
                                    toast.error("Error de red al intentar eliminar.");
                                  }
                                }}
                                className="text-rose-500 hover:text-rose-700 p-1"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => {
                  setIsAusentismoModalOpen(false);
                  setTramitarReembolso(false);
                  setSoporteMedico(null);
                }}
                className="px-6 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-xl transition-colors"
              >
                Aceptar y Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </IdleTimer>
  );
}

export default App;
