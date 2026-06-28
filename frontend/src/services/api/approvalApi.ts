import { apiClient } from "./apiClient";

export interface Approval {
  id: number;
  recommendation_id: number;
  decision: "approved" | "rejected";
  comments?: string;
  reviewed_at: string;
}

export const approvalApi = {
  getApprovals: async (skip = 0, limit = 100): Promise<{ total: number; approved: number; rejected: number; items: Approval[] }> => {
    const res = await apiClient.get<{ total: number; approved: number; rejected: number; items: Approval[] }>(`/approvals?skip=${skip}&limit=${limit}`);
    return res.data;
  },

  createApproval: async (recommendationId: number, decision: "approved" | "rejected", comments?: string): Promise<Approval> => {
    const res = await apiClient.post<Approval>("/approvals", {
      recommendation_id: recommendationId,
      decision,
      comments,
    });
    return res.data;
  },
};
