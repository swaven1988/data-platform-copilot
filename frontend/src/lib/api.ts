import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("COPILOT_TOKEN");
  if (token) {
    config.headers = config.headers || {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});
