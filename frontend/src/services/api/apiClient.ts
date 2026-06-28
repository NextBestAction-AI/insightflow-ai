import axios from "axios";
import { API_CONFIG } from "../../config/api";

export const apiClient = axios.create({
  baseURL: API_CONFIG.BASE_URL,
  timeout: API_CONFIG.TIMEOUT,
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for friendly error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let friendlyMessage = "An unexpected error occurred. Please try again.";

    if (!error.response) {
      // Network or connection timeout
      if (error.code === "ECONNABORTED") {
        friendlyMessage = "Connection timed out. The server is taking too long to respond.";
      } else {
        friendlyMessage = "Cannot connect to the server. Please check if the backend is running.";
      }
    } else {
      const status = error.response.status;
      const data = error.response.data;

      if (status === 400) {
        friendlyMessage = typeof data?.detail === "string" ? data.detail : "Bad request parameters.";
      } else if (status === 404) {
        friendlyMessage = typeof data?.detail === "string" ? data.detail : "Requested resource not found.";
      } else if (status === 422) {
        friendlyMessage = "Validation error. Please verify the input format.";
        if (data?.detail && Array.isArray(data.detail)) {
          const errors = data.detail.map((err: any) => err.msg || err.type).join(", ");
          friendlyMessage += ` details: ${errors}`;
        }
      } else if (status === 500) {
        friendlyMessage = typeof data?.detail === "string" ? data.detail : "Internal server error occurred on the backend.";
      }
    }

    return Promise.reject(new Error(friendlyMessage));
  }
);
