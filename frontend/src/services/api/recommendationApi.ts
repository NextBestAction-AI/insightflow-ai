import { apiClient } from "./apiClient";

export interface Recommendation {
  id: number;
  interaction_id: number;
  customer_id: number;
  action: string;
  confidence: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "executed";
  created_at: string;
}

export const recommendationApi = {
  getRecommendations: async (skip = 0, limit = 100): Promise<{ total: number; pending: number; items: Recommendation[] }> => {
    const res = await apiClient.get<{ total: number; pending: number; items: Recommendation[] }>(`/recommendations?skip=${skip}&limit=${limit}`);
    return res.data;
  },

  getCustomerRecommendations: async (customerId: number): Promise<Recommendation[]> => {
    const res = await apiClient.get<Recommendation[]>(`/customers/${customerId}/recommendations`);
    return res.data;
  },

  updateRecommendation: async (id: number, data: Partial<Recommendation>): Promise<Recommendation> => {
    const res = await apiClient.put<Recommendation>(`/recommendations/${id}`, data);
    return res.data;
  },
};
