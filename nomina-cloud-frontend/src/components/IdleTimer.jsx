import { useEffect, useRef } from "react";
import { supabase } from "../lib/supabaseClient";

export default function IdleTimer({ children }) {
  const timeoutRef = useRef(null);
  
  const TIMEOUT_MS = 900000; // 15 minutos

  const handleLogout = async () => {
    await supabase.auth.signOut();
    localStorage.clear();
    window.location.href = "/login?reason=timeout";
  };

  const resetTimer = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(handleLogout, TIMEOUT_MS);
  };

  useEffect(() => {
    // Iniciar el temporizador
    resetTimer();

    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"];

    const handleUserActivity = () => {
      resetTimer();
    };

    // Registrar los escuchadores
    events.forEach((event) => {
      document.addEventListener(event, handleUserActivity);
    });

    // Cleanup: remover escuchadores y limpiar timer para evitar memory leaks
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      events.forEach((event) => {
        document.removeEventListener(event, handleUserActivity);
      });
    };
  }, []);

  return <>{children}</>;
}
