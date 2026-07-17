import { supabase } from "./supabaseClient";

/**
 * Cliente API para hacer peticiones al backend (FastAPI).
 * Automáticamente adjunta el token JWT de Supabase en el header Authorization.
 */
export const apiClient = async (url, options = {}) => {
  // 1. Obtener la sesión actual de Supabase
  const { data: { session } } = await supabase.auth.getSession();

  // 2. Preparar los headers
  const headers = new Headers(options.headers || {});

  // Agregar Content-Type por defecto si no existe y es una petición con body (como JSON)
  if (
    !headers.has("Content-Type") &&
    options.body &&
    typeof options.body === "string"
  ) {
    headers.set("Content-Type", "application/json");
  }

  // 3. Si hay sesión, agregar el token JWT al header de Authorization
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

  // 4. Realizar la petición fetch con los headers actualizados
  const response = await fetch(url, {
    credentials: "include",
    ...options,
    headers,
  });

  // 5. Interceptar errores 401 Globalmente (Sesión Expirada o Inválida)
  if (response.status === 401) {
    alert("Tu sesión ha expirado por seguridad. Por favor, vuelve a ingresar.");
    await supabase.auth.signOut();
    window.location.href = "/";
    return response;
  }

  return response;
};
