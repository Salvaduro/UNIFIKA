import { useState, useEffect } from "react";
import { supabase } from "../lib/supabaseClient";

export default function ResetPassword() {
  const [loading, setLoading] = useState(false);
  const [nuevaContrasena, setNuevaContrasena] = useState("");
  const [confirmarContrasena, setConfirmarContrasena] = useState("");
  const [message, setMessage] = useState({ type: "", text: "" });

  useEffect(() => {
    supabase.auth.onAuthStateChange(async (event) => {
      if (event == "PASSWORD_RECOVERY") {
      }
    });
  }, []);

  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    if (nuevaContrasena !== confirmarContrasena) {
      setMessage({ type: "error", text: "Las contraseñas no coinciden." });
      return;
    }
    if (nuevaContrasena.length < 6) {
      setMessage({
        type: "error",
        text: "La contraseña debe tener al menos 6 caracteres.",
      });
      return;
    }

    setLoading(true);
    setMessage({ type: "", text: "" });

    const { error } = await supabase.auth.updateUser({
      password: nuevaContrasena,
    });

    if (error) {
      setMessage({ type: "error", text: error.message });
      setLoading(false);
    } else {
      setMessage({
        type: "success",
        text: "Contraseña actualizada exitosamente. Redirigiendo...",
      });

      localStorage.removeItem("bloqueo_recuperacion");
      await supabase.auth.signOut();

      setTimeout(() => {
        window.location.href = "/";
      }, 2000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-3xl shadow-xl p-8 sm:p-10 border border-slate-200/60">
        <div className="text-center mb-8">
          <img
            src="/logo-unifika.png"
            alt="UNIFIKA Logo"
            className="w-auto h-16 mx-auto mb-4"
          />
          <h2 className="text-2xl font-bold text-slate-800">
            Actualizar Contraseña
          </h2>
          <p className="text-sm text-slate-500 mt-2">
            Ingresa tu nueva contraseña
          </p>
        </div>

        {message.text && (
          <div
            className={`p-4 rounded-xl mb-6 text-sm font-medium animate-fade-in ${message.type === "error" ? "bg-red-50 text-red-600 border border-red-100" : "bg-emerald-50 text-emerald-600 border border-emerald-100"}`}
          >
            {message.text}
          </div>
        )}

        <form className="space-y-5" onSubmit={handleUpdatePassword}>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Nueva Contraseña
            </label>
            <input
              type="password"
              value={nuevaContrasena}
              onChange={(e) => setNuevaContrasena(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-unifika-accent focus:border-unifika-accent outline-none transition-all bg-slate-50 focus:bg-white"
              placeholder="••••••••"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Confirmar Contraseña
            </label>
            <input
              type="password"
              value={confirmarContrasena}
              onChange={(e) => setConfirmarContrasena(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-unifika-accent focus:border-unifika-accent outline-none transition-all bg-slate-50 focus:bg-white"
              placeholder="••••••••"
              required
            />
          </div>

          <div className="pt-4 flex flex-col space-y-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-unifika-accent hover:bg-unifika-accent-hover text-white font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70 shadow-sm"
            >
              {loading ? "Procesando..." : "Actualizar"}
            </button>
            <button
              type="button"
              onClick={() => (window.location.href = "/")}
              disabled={loading}
              className="w-full bg-white border-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
