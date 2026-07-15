import { useState, useEffect } from "react";
import { apiClient } from "../lib/apiClient";

export default function DashboardHistorico({ idAportante }) {
  const [periodos, setPeriodos] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [periodoExpandido, setPeriodoExpandido] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    fetchHistorico();
  }, [idAportante]);

  const fetchHistorico = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const queryParam = idAportante
        ? `?aportante_id=${encodeURIComponent(idAportante)}`
        : "";
      const response = await apiClient(
        `http://127.0.0.1:8000/api/v1/nomina/periodos-historico${queryParam}`,
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Error HTTP: ${response.status}`);
      }

      const data = await response.json();
      setPeriodos(data || []);
    } catch (err) {
      console.error("Error al cargar histórico:", err);
      setError(err.message || "No se pudo cargar el historial de nóminas.");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleExpand = (periodoKey) => {
    if (periodoExpandido === periodoKey) {
      setPeriodoExpandido(null);
    } else {
      setPeriodoExpandido(periodoKey);
    }
  };

  const descargarPDF = async (id_contrato, periodo, quincena) => {
    setIsDownloading(true);
    try {
      const response = await apiClient(
        `http://127.0.0.1:8000/api/v1/nomina/desprendible-pdf/${encodeURIComponent(id_contrato)}/${encodeURIComponent(periodo)}/${encodeURIComponent(quincena)}`,
        {
          // El backend envía binario (application/pdf) o error en texto
          // Pero necesitamos configurarlo si el api client lo soporta o simplemente
          // usar la respuesta estándar ya que blob() resuelve el body
        },
      );

      if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;

      const periodoStr = periodo
        ? periodo.replace(/\s+/g, "_").toUpperCase()
        : "PERIODO";
      const quincenaStr =
        quincena === "1" ? "Q1" : quincena === "2" ? "Q2" : quincena;

      link.setAttribute(
        "download",
        `Desprendible_${id_contrato}_${periodoStr}_${quincenaStr}.pdf`,
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Error al descargar PDF:", err);
      alert("Hubo un error al generar el PDF. Por favor, intenta de nuevo.");
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="flex flex-col items-center">
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
          <p className="text-slate-600 font-medium">Cargando histórico...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg my-6 max-w-4xl mx-auto">
        <p className="text-red-700 font-medium">{error}</p>
        <button
          onClick={fetchHistorico}
          className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
        >
          Intentar de nuevo
        </button>
      </div>
    );
  }

  if (periodos.length === 0) {
    return (
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
          No hay nóminas históricas
        </h3>
        <p className="text-sm text-slate-500 max-w-md">
          Aún no tienes periodos de nómina registrados.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 mt-4 pb-8">
      {periodos.map((periodoObj, idx) => {
        const p_liq = periodoObj.periodo_liq || "PERIODO DESCONOCIDO";
        const q_pago = periodoObj.quincena_pago || "";
        const p_estado = periodoObj.estado || "CERRADO";
        const empleados = periodoObj.empleados || [];
        const periodoKey = `${p_liq}-${q_pago}-${idx}`;
        const isExpanded = periodoExpandido === periodoKey;

        return (
          <div
            key={periodoKey}
            className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden transition-all duration-200"
          >
            {/* Header del Periodo */}
            <div
              className="px-6 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center cursor-pointer hover:bg-slate-50 transition-colors"
              onClick={() => toggleExpand(periodoKey)}
            >
              <div className="flex items-center mb-2 sm:mb-0">
                <div
                  className={`w-1.5 h-10 rounded-full mr-4 ${p_estado === "CERRADO" ? "bg-emerald-500" : "bg-blue-400"}`}
                ></div>
                <div>
                  <h3 className="text-lg font-bold text-slate-800">
                    {p_liq}{" "}
                    {q_pago && q_pago !== "M"
                      ? `- Quincena ${q_pago}`
                      : q_pago === "M"
                        ? "- Mensual"
                        : ""}
                  </h3>
                  <p className="text-sm text-slate-500">
                    {empleados.length} empleado(s) registrado(s)
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <span
                  className={`px-3 py-1 text-xs font-bold rounded-full flex items-center ${
                    p_estado === "CERRADO"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-blue-50 text-blue-700 border border-blue-200"
                  }`}
                >
                  {p_estado === "CERRADO" && (
                    <svg
                      className="w-3 h-3 mr-1"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                        clipRule="evenodd"
                      ></path>
                    </svg>
                  )}
                  {p_estado}
                </span>

                <button className="text-slate-400 hover:text-slate-600 transition-colors focus:outline-none">
                  <svg
                    className={`w-5 h-5 transform transition-transform ${isExpanded ? "rotate-180" : ""}`}
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
              </div>
            </div>

            {/* Acordeón: Lista de empleados */}
            {isExpanded && (
              <div className="border-t border-slate-100 bg-slate-50/50 px-6 py-4 animate-fade-in">
                {empleados.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr>
                          <th className="py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            Empleado
                          </th>
                          <th className="py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden sm:table-cell">
                            Cargo
                          </th>
                          <th className="py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">
                            Desprendible
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200">
                        {empleados.map((emp, empIdx) => (
                          <tr
                            key={empIdx}
                            className="hover:bg-white transition-colors"
                          >
                            <td className="py-3 text-sm font-medium text-slate-800">
                              {emp.nombre_empleado || emp.NOMBRE_EMPLEADO}
                              <div className="text-xs font-normal text-slate-500 mt-0.5">
                                {emp.id_contrato || emp.ID_CONTRATO}
                              </div>
                            </td>
                            <td className="py-3 text-sm text-slate-600 hidden sm:table-cell">
                              {emp.cargo ||
                                emp.CARGO ||
                                emp.cargo_desempeneado ||
                                emp.CARGO_DESEMPENEADO ||
                                "N/A"}
                            </td>
                            <td className="py-3 text-right">
                              <button
                                onClick={() =>
                                  descargarPDF(
                                    emp.id_contrato || emp.ID_CONTRATO,
                                    p_liq,
                                    q_pago,
                                  )
                                }
                                disabled={isDownloading}
                                className="inline-flex items-center justify-center p-2 rounded-lg bg-white border border-slate-200 shadow-sm text-unifika-primary hover:bg-unifika-primary hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title="Descargar Desprendible PDF"
                              >
                                {isDownloading ? (
                                  <svg
                                    className="animate-spin h-5 w-5"
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
                                ) : (
                                  <svg
                                    className="w-5 h-5"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth="1.5"
                                      d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                    />
                                  </svg>
                                )}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 italic py-2 text-center">
                    No se encontraron empleados detallados para este periodo.
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
