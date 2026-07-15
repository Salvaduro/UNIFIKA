import { useState, useEffect } from "react";
import { apiClient } from "../lib/apiClient";

export default function ResumenNomina({
  periodo,
  quincena,
  idAportante,
  onRowClick,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCerrado, setIsCerrado] = useState(false);
  const [isClosing, setIsClosing] = useState(false);

  useEffect(() => {
    if (!periodo || !quincena) return;

    const fetchResumen = async () => {
      setLoading(true);
      setError(null);
      try {
        const idQuery = idAportante
          ? `?id_aportante=${encodeURIComponent(idAportante)}`
          : "";
        const url = `http://127.0.0.1:8000/api/v1/nomina/resumen/${encodeURIComponent(periodo)}/${encodeURIComponent(quincena)}${idQuery}`;
        const res = await apiClient(url);
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Error al cargar el resumen");
        }
        const json = await res.json();
        setData(json);

        // Fetch closure status
        const closureUrl = `http://127.0.0.1:8000/api/v1/nomina/estado-cierre/${encodeURIComponent(periodo)}/${encodeURIComponent(quincena)}${idQuery}`;
        const closureRes = await apiClient(closureUrl);
        if (closureRes.ok) {
          const closureData = await closureRes.json();
          setIsCerrado(closureData.cerrado);
        }
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchResumen();
  }, [periodo, quincena]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <svg
          className="animate-spin h-10 w-10 text-unifika-primary mb-4"
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
        <p className="text-slate-500 font-medium text-lg">
          Cargando Resumen Gerencial...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-xl shadow-sm my-6">
        <h3 className="text-red-800 font-bold text-lg mb-2">
          Error al cargar resumen
        </h3>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const { totales, empleados } = data;

  const formatearMoneda = (valor) => {
    return new Intl.NumberFormat("es-CO", {
      style: "currency",
      currency: "COP",
      maximumFractionDigits: 0,
    }).format(valor);
  };

  const obtenerTextoCiclo = (ciclo) => {
    if (!ciclo) return "";
    const c = String(ciclo).toUpperCase().trim();
    if (c === "1" || c === "Q1") return "Primera Quincena";
    if (c === "2" || c === "Q2") return "Segunda Quincena";
    if (c === "M" || c === "MENSUAL") return "Mensualidad";
    return `Ciclo ${ciclo}`;
  };

  return (
    <div className="w-full animate-fade-in space-y-8">
      {/* Título Contextual */}
      <div className="bg-[#5b97a9] rounded-2xl p-6 shadow-md border border-[#5b97a9] flex flex-col md:flex-row justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-white text-center md:text-left">
          Estado de Avance - Período:{" "}
          <span className="text-white opacity-90">{periodo}</span> (
          {obtenerTextoCiclo(quincena)})
        </h2>
        {isCerrado && (
          <div className="inline-flex items-center gap-2 bg-[#babf15] text-slate-900 px-4 py-1.5 rounded-full font-bold text-sm tracking-wide shadow-sm">
            <svg
              className="w-5 h-5 text-slate-900"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              ></path>
            </svg>
            🔒 NÓMINA CERRADA
          </div>
        )}
      </div>

      {/* Cards de Totales */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-center items-start hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <svg
              className="w-16 h-16 text-unifika-primary"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z"></path>
            </svg>
          </div>
          <h4 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1">
            Total a Pagar
          </h4>
          <p className="text-3xl font-black text-slate-800">
            {formatearMoneda(totales.total_empresa_neto)}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-center items-start hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <svg
              className="w-16 h-16 text-slate-600"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"></path>
            </svg>
          </div>
          <h4 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1">
            Total Empleados
          </h4>
          <p className="text-3xl font-black text-slate-800">
            {totales.total_empleados}
          </p>
        </div>

        <div
          className={`bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-center items-start hover:shadow-md transition-shadow relative overflow-hidden group ${totales.empleados_pendientes === 0 ? "border-l-4 border-l-green-500" : "border-l-4 border-l-amber-500"}`}
        >
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <svg
              className="w-16 h-16 text-amber-500"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                clipRule="evenodd"
              ></path>
            </svg>
          </div>
          <h4 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1">
            Empleados Pendientes
          </h4>
          <p
            className={`text-3xl font-black ${totales.empleados_pendientes === 0 ? "text-green-600" : "text-amber-600"}`}
          >
            {totales.empleados_pendientes}
          </p>
        </div>
      </div>

      {/* Tabla de Empleados */}
      <div className="shadow-sm rounded-lg mt-8">
        <div className="p-4 bg-[#688b94] rounded-t-lg flex justify-between items-center">
          <h3 className="text-lg font-bold text-white flex items-center">
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
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
              ></path>
            </svg>
            Detalle de Nómina por Empleado
          </h3>
        </div>
        <div className="overflow-x-auto border-x border-b border-[#688b94]/20 rounded-b-lg bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="px-6 py-4 font-bold">Estado</th>
                <th className="px-6 py-4 font-bold">Empleado</th>
                <th className="px-6 py-4 font-bold">Cargo / Contrato</th>
                <th className="px-6 py-4 font-bold text-right">Neto a Pagar</th>
              </tr>
            </thead>
            <tbody>
              {empleados.map((emp) => (
                <tr
                  key={emp.id_contrato}
                  onClick={() => !isCerrado && onRowClick && onRowClick(emp)}
                  className={`bg-white border-b border-slate-50 transition-colors ${!isCerrado ? "hover:bg-slate-100 cursor-pointer" : "opacity-80"}`}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full shadow-sm ${emp.estado === "LIQUIDADO" ? "bg-green-500 shadow-green-200" : "bg-amber-400 shadow-amber-200"}`}
                      ></div>
                      <span
                        className={`font-semibold ${emp.estado === "LIQUIDADO" ? "text-green-700" : "text-amber-600"}`}
                      >
                        {emp.estado}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 font-medium text-slate-800">
                    {emp.nombre}
                  </td>
                  <td className="px-6 py-4 text-slate-500">
                    {emp.cargo} <br />
                    <span className="text-xs opacity-75">
                      {emp.tipo_contrato}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-bold text-slate-800 text-right">
                    {formatearMoneda(emp.neto_pagar)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Botón de Cierre */}
      {!isCerrado && (
        <div className="flex justify-center pt-6 pb-12">
          <button
            type="button"
            onClick={async () => {
              if (
                window.confirm(
                  "¿Estás seguro? Una vez cerrada la nómina, no podrás realizar más modificaciones para este periodo.",
                )
              ) {
                setIsClosing(true);
                try {
                  const payload = {
                    periodo: String(periodo).toUpperCase().trim(),
                    quincena: String(quincena).trim(),
                    id_aportante: idAportante || null,
                  };

                  const response = await apiClient(
                    "http://127.0.0.1:8000/api/v1/nomina/cerrar",
                    {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(payload),
                    },
                  );

                  if (response.ok) {
                    setIsCerrado(true);
                  } else {
                    const errData = await response.json();
                    alert(errData.detail || "Error al cerrar la nómina");
                  }
                } catch (err) {
                  alert("Error de red al cerrar la nómina");
                } finally {
                  setIsClosing(false);
                }
              }
            }}
            disabled={isClosing}
            className={`inline-flex items-center justify-center gap-3 font-bold py-4 px-12 text-lg text-white transition-colors duration-200 rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#babf15] ${isClosing ? "bg-slate-400 cursor-not-allowed" : "bg-[#babf15] hover:bg-[#a2a812]"}`}
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              ></path>
            </svg>
            {isClosing ? "Cerrando..." : "Aprobar y Cerrar Nómina"}
          </button>
        </div>
      )}
    </div>
  );
}
