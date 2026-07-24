import axios from "axios";

// Local dev defaults to localhost. In production, set VITE_BACKEND_URL as a
// build-time env var (Vite only exposes vars prefixed with VITE_).
export const BACKEND_URL: string =
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: BACKEND_URL,
  timeout: 30000,
});

export default api;

/** Extracts a readable error message from an axios error, mirroring the
 * res.json().get('detail') pattern the original Streamlit apps used. */
export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.code === "ECONNABORTED") return "Request timed out.";
    if (!error.response) return `Could not connect to the backend at ${BACKEND_URL}.`;
    return `Backend error (${error.response.status}): ${error.message}`;
  }
  return String(error);
}
