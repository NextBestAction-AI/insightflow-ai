import { apiClient } from "./apiClient";

export const healthApi = {
  getHealth: async (): Promise<{ status: string; service: string }> => {
    const res = await apiClient.get<{ status: string; service: string }>("/health");
    return res.data;
  },
};
