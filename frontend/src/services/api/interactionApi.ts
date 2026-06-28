import { apiClient } from "./apiClient";

export interface Interaction {
  id: number;
  customer_id: number;
  type: string;
  content: string;
  created_at: string;
}

export const interactionApi = {
  createInteraction: async (data: { customer_id: number; type: string; content: string }): Promise<Interaction> => {
    const res = await apiClient.post<Interaction>("/interactions", data);
    return res.data;
  },

  getInteractions: async (skip = 0, limit = 100): Promise<{ total: number; items: Interaction[] }> => {
    const res = await apiClient.get<{ total: number; items: Interaction[] }>(`/interactions?skip=${skip}&limit=${limit}`);
    return res.data;
  },
};
