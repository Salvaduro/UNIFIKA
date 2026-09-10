import { useState } from "react";
import { apiClient } from "../lib/apiClient";
import toast from "react-hot-toast";

export default function SandboxPila({ perfilAportante }) {
  const [formData, setFormData] = useState({
    idAportante: "EMP-001",
    periodo: "SEPTIEMBRE 2026",
    quincena: "1"
  });
  const [consoleOutput, setConsoleOutput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerarLocal = async () => {
    setIsLoading(true);
    try {
      const url = `${import.meta.env.VITE_API_URL}/api/v1/pila/descargar-txt/${encodeURIComponent(formData.idAportante)}/${encodeURIComponent(formData.periodo)}/${encodeURIComponent(formData.quincena)}`;
      const response = await apiClient(url);
      if (!response.ok) throw new Error("Error al descargar TXT local");
      
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.setAttribute("download", `PILA_LOCAL.txt`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
      
      const text = await blob.text();
      const firstLines = text.split('\n').slice(0, 5).join('\n');
      
      setConsoleOutput(`--- TXT GENERADO LOCALMENTE (Primeras 5 líneas) ---\n\n${firstLines}`);
      toast.success("TXT Generado Localmente");
    } catch (error) {
      setConsoleOutput(`Error: ${error.message}`);
      toast.error("Fallo generación local");
    } finally {
      setIsLoading(false);
    }
  };

  const handleEnviarValidador = async () => {
    setIsLoading(true);
    setConsoleOutput("Enviando a Pago Simple...");
    try {
      const response = await apiClient(`${import.meta.env.VITE_API_URL}/api/v1/pila/sandbox-validar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_aportante: formData.idAportante,
          periodo: formData.periodo,
          quincena: formData.quincena
        })
      });
      const data = await response.json();
      setConsoleOutput(`--- RESPUESTA VALIDADOR SIMPLE ---\n\n${JSON.stringify(data, null, 2)}`);
      if (response.ok) {
        toast.success("Respuesta recibida");
      } else {
        toast.error("Error en validación");
      }
    } catch (error) {
      setConsoleOutput(`Error: ${error.message}`);
      toast.error("Fallo al validar");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 animate-fade-in pt-6">
      <div className="bg-slate-800 p-6 rounded-xl text-white">
        <h2 className="text-2xl font-bold mb-2">Sandbox Integración PILA (Pago Simple)</h2>
        <p className="text-slate-400">Entorno aislado de pruebas de integración con el Gateway de Aportes.</p>
      </div>

      <div className="bg-white p-6 rounded-xl shadow border border-slate-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-1">ID Aportante / NIT</label>
            <input type="text" className="w-full p-2 border rounded" value={formData.idAportante} onChange={(e) => setFormData({...formData, idAportante: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-1">Periodo (Ej. SEPTIEMBRE 2026)</label>
            <input type="text" className="w-full p-2 border rounded" value={formData.periodo} onChange={(e) => setFormData({...formData, periodo: e.target.value.toUpperCase()})} />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-1">Quincena (1, 2, M)</label>
            <input type="text" className="w-full p-2 border rounded" value={formData.quincena} onChange={(e) => setFormData({...formData, quincena: e.target.value.toUpperCase()})} />
          </div>
        </div>

        <div className="flex gap-4">
          <button onClick={handleGenerarLocal} disabled={isLoading} className="bg-slate-600 hover:bg-slate-700 text-white px-6 py-2 rounded font-bold shadow-sm disabled:opacity-50">
            1. Generar TXT Local
          </button>
          <button onClick={handleEnviarValidador} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2 rounded font-bold shadow-sm disabled:opacity-50">
            2. Enviar a Validador SIMPLE
          </button>
        </div>
      </div>

      <div className="bg-black p-4 rounded-xl shadow overflow-hidden flex flex-col h-[500px]">
        <div className="text-emerald-400 font-mono text-sm mb-2 flex justify-between">
          <span>&gt;_ Consola Validador</span>
          {isLoading && <span className="animate-pulse">Ejecutando...</span>}
        </div>
        <pre className="text-emerald-300 font-mono text-sm flex-1 overflow-auto whitespace-pre-wrap">
          {consoleOutput || "Esperando ejecución..."}
        </pre>
      </div>
    </div>
  );
}
