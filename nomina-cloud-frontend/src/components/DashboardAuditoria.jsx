import { useState, useEffect } from "react";
import { apiClient } from "../lib/apiClient";

export default function DashboardAuditoria() {
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient(
        `${import.meta.env.VITE_API_URL}/api/v1/auditoria/logs`
      );

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const errorObj = new Error(
          errData.detail || `Error HTTP: ${response.status}`
        );
        errorObj.response = { data: errData };
        throw errorObj;
      }

      const resData = await response.json();
      setLogs(resData.data || []);
    } catch (err) {
      console.error("Error al cargar logs de auditoría:", err);
      const detail =
        err.response?.data?.detail ||
        err.message ||
        "No se pudo cargar el historial de auditoría.";
      setError(detail);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleExpand = (idLog) => {
    setExpandedRow(expandedRow === idLog ? null : idLog);
  };

  const formatearFecha = (fechaStr) => {
    if (!fechaStr) return "-";
    try {
      const date = new Date(fechaStr);
      return date.toLocaleString("es-CO", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return fechaStr;
    }
  };

  const getRolBadge = (rol) => {
    const rolUpper = String(rol || "").toUpperCase();
    if (rolUpper === "SUPERADMIN") {
      return (
        <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-purple-100 text-purple-800 border border-purple-200">
          SUPERADMIN
        </span>
      );
    }
    if (rolUpper === "ADMINISTRADOR") {
      return (
        <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-blue-100 text-blue-800 border border-blue-200">
          ADMINISTRADOR
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
        {rol || "EMPLEADOR"}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="flex flex-col items-center">
          <svg
            className="animate-spin h-10 w-10 text-[#5b97a9] mb-4"
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
          <p className="text-slate-600 font-medium">Cargando auditoría...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-lg my-6 max-w-4xl mx-auto shadow-sm">
        <div className="flex items-center mb-2">
          <svg
            className="w-6 h-6 text-red-600 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h4 className="text-base font-bold text-red-800">Error de Auditoría</h4>
        </div>
        <p className="text-red-700 font-medium text-sm">{error}</p>
        <button
          onClick={fetchLogs}
          className="mt-4 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-md text-sm font-semibold transition-colors"
        >
          Intentar de nuevo
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 mt-4 pb-8">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center">
            <svg
              className="w-6 h-6 mr-2 text-[#5b97a9]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            Registro de Auditoría y Telemetría
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Visualiza y supervisa las acciones realizadas por el Staff y Empleadores (Acceso exclusivo SUPERADMIN)
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="mt-4 sm:mt-0 px-4 py-2 bg-[#5b97a9] hover:bg-[#4a7e8d] text-white rounded-lg text-sm font-bold flex items-center transition-colors shadow-sm"
        >
          <svg
            className="w-4 h-4 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Actualizar
        </button>
      </div>

      {logs.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 flex flex-col items-center justify-center text-center mt-6">
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
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-xl font-bold text-slate-700 mb-2">
            No hay registros de auditoría
          </h3>
          <p className="text-sm text-slate-500 max-w-md">
            Aún no se ha registrado ninguna actividad o evento en el sistema.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#5b97a9] text-white font-bold text-xs uppercase tracking-wider">
                  <th className="py-3 px-4">Fecha / Hora</th>
                  <th className="py-3 px-4">Usuario</th>
                  <th className="py-3 px-4">Rol</th>
                  <th className="py-3 px-4">Acción</th>
                  <th className="py-3 px-4">Entidad</th>
                  <th className="py-3 px-4 text-center">Detalles</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {logs.map((log) => {
                  const isExpanded = expandedRow === log.id_log;
                  const hasDetails = log.detalles && Object.keys(log.detalles).length > 0;

                  return (
                    <tr
                      key={log.id_log}
                      className="hover:bg-slate-50/80 transition-colors text-sm"
                    >
                      <td className="py-3.5 px-4 whitespace-nowrap text-slate-600 font-medium">
                        {formatearFecha(log.fecha_evento)}
                      </td>
                      <td className="py-3.5 px-4 text-slate-800 font-semibold">
                        <div>{log.usuario_email || "-"}</div>
                        {log.id_aportante && (
                          <div className="text-xs font-normal text-slate-500 mt-0.5">
                            Empresa ID: {log.id_aportante}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getRolBadge(log.rol_usuario)}
                      </td>
                      <td className="py-3.5 px-4 text-slate-800 font-bold">
                        {log.tipo_accion || "-"}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        <span className="font-mono text-xs bg-slate-100 px-2 py-1 rounded text-slate-700">
                          {log.entidad_afectada || "N/A"}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {hasDetails ? (
                          <div className="flex flex-col items-center">
                            <button
                              onClick={() => toggleExpand(log.id_log)}
                              className="px-3 py-1 text-xs font-bold text-[#5b97a9] hover:text-[#4a7e8d] bg-[#5b97a9]/10 hover:bg-[#5b97a9]/20 rounded-md transition-colors flex items-center"
                            >
                              <span>{isExpanded ? "Ocultar" : "Ver JSON"}</span>
                              <svg
                                className={`w-3.5 h-3.5 ml-1 transform transition-transform ${
                                  isExpanded ? "rotate-180" : ""
                                }`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M19 9l-7 7-7-7"
                                />
                              </svg>
                            </button>
                            {isExpanded && (
                              <div className="mt-2 text-left w-full max-w-md bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto text-xs font-mono shadow-inner border border-slate-700">
                                <pre>{JSON.stringify(log.detalles, null, 2)}</pre>
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Sin datos</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
