import axios from "axios";

export const BACKEND_URL: string =
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: BACKEND_URL,
  timeout: 30000,
});

export default api;

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
