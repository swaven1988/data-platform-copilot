import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  config.headers = config.headers || {};

  // Auth — fallback to dev token when not explicitly set
  const token = localStorage.getItem("COPILOT_TOKEN") || "dev_admin_token";
  config.headers["Authorization"] = `Bearer ${token}`;

  // Tenant — required by TenantIsolationMiddleware on every request
  const tenant = localStorage.getItem("COPILOT_TENANT") || "default";
  config.headers["X-Tenant"] = tenant;

  return config;
});
