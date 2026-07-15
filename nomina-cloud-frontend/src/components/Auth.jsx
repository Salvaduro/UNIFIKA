import { useState } from "react";
import { supabase } from "../lib/supabaseClient";

export default function Auth() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState({ type: "", text: "" });

  const [isForgotPasswordMode, setIsForgotPasswordMode] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: "", text: "" });

    // Clear any residual period state to force dynamic initialization on load
    localStorage.removeItem("periodo_seleccionado");
    localStorage.removeItem("quincena_seleccionada");

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setMessage({ type: "error", text: error.message });
    }
    setLoading(false);
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: "", text: "" });

    const { error } = await supabase.auth.signUp({
      email,
      password,
    });

    if (error) {
      setMessage({ type: "error", text: error.message });
    } else {
      setMessage({
        type: "success",
        text: "Revisa tu correo para verificar tu cuenta o espera la aprobación del administrador.",
      });
    }
    setLoading(false);
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    if (!email) {
      setMessage({
        type: "error",
        text: "Por favor, ingresa tu correo electrónico.",
      });
      return;
    }
    setLoading(true);
    setMessage({ type: "", text: "" });

    localStorage.setItem("bloqueo_recuperacion", "true");

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + "/actualizar-password",
    });

    if (error) {
      setMessage({ type: "error", text: error.message });
    } else {
      setMessage({
        type: "success",
        text: "Te hemos enviado un enlace para restablecer tu contraseña. Revisa tu bandeja de entrada.",
      });
    }
    setLoading(false);
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
          <h2 className="text-2xl font-bold text-slate-800">Bienvenido</h2>
          <p className="text-sm text-slate-500 mt-2">
            Inicia sesión en UNIFIKA Nómina Cloud
          </p>
        </div>

        {message.text && (
          <div
            className={`p-4 rounded-xl mb-6 text-sm font-medium animate-fade-in ${message.type === "error" ? "bg-red-50 text-red-600 border border-red-100" : "bg-emerald-50 text-emerald-600 border border-emerald-100"}`}
          >
            {message.text}
          </div>
        )}

        <form className="space-y-5">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              Correo Electrónico
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary outline-none transition-all bg-slate-50 focus:bg-white"
              placeholder="tu@email.com"
              required
            />
          </div>
          {!isForgotPasswordMode && (
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-unifika-primary focus:border-unifika-primary outline-none transition-all bg-slate-50 focus:bg-white"
                placeholder="••••••••"
                required
              />
            </div>
          )}

          {!isForgotPasswordMode && (
            <div className="text-right">
              <button
                type="button"
                onClick={() => {
                  setIsForgotPasswordMode(true);
                  setMessage({ type: "", text: "" });
                }}
                className="text-sm text-unifika-primary hover:underline font-medium"
              >
                ¿Olvidaste tu contraseña?
              </button>
            </div>
          )}

          <div className="pt-4 flex flex-col space-y-3">
            {isForgotPasswordMode ? (
              <>
                <button
                  onClick={handleForgotPassword}
                  disabled={loading}
                  className="w-full bg-unifika-primary hover:bg-[#002f5a] text-white font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70 shadow-sm"
                >
                  {loading ? "Procesando..." : "Enviar Enlace de Recuperación"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsForgotPasswordMode(false);
                    setMessage({ type: "", text: "" });
                  }}
                  className="w-full bg-white border-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70"
                >
                  Volver al inicio de sesión
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleLogin}
                  disabled={loading}
                  className="w-full bg-unifika-primary hover:bg-[#002f5a] text-white font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70 shadow-sm"
                >
                  {loading ? "Procesando..." : "Iniciar Sesión"}
                </button>
                <button
                  onClick={handleSignUp}
                  disabled={loading}
                  className="w-full bg-white border-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold py-3 px-4 rounded-xl transition-all disabled:opacity-70"
                >
                  Crear Cuenta Nueva
                </button>
              </>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
