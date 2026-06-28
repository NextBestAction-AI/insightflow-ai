const API_BASE = "http://localhost:8000/api/v1";

export interface Customer {
  id: number;
  name: string;
  email: string;
  company: string;
  industry?: string;
  account_type?: string;
  region?: string;
  annual_revenue_usd?: number;
  employee_count?: number;
}

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

export interface Approval {
  id: number;
  recommendation_id: number;
  decision: "approved" | "rejected";
  comments?: string;
  reviewed_at: string;
}

export interface AnalysisResponse {
  status: string;
  interaction_id: number;
  recommendations: Recommendation[];
  activities: Array<{
    id: string;
    time: string;
    title: string;
    description: string;
    type: string;
  }>;
  health_assessment?: any;
  risk_assessment?: any;
  business_reasoning?: any;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(
      `API Request failed with status ${response.status}: ${errorBody || response.statusText}`
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  getCustomers: async (skip = 0, limit = 100): Promise<{ total: number; items: Customer[] }> => {
    return request<{ total: number; items: Customer[] }>(`/customers?skip=${skip}&limit=${limit}`);
  },

  getRecommendations: async (skip = 0, limit = 100): Promise<{ total: number; pending: number; items: Recommendation[] }> => {
    return request<{ total: number; pending: number; items: Recommendation[] }>(`/recommendations?skip=${skip}&limit=${limit}`);
  },

  getRecommendation: async (id: number): Promise<Recommendation> => {
    return request<Recommendation>(`/recommendations/${id}`);
  },

  updateRecommendation: async (id: number, data: Partial<Recommendation>): Promise<Recommendation> => {
    return request<Recommendation>(`/recommendations/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  getApprovals: async (skip = 0, limit = 100): Promise<{ total: number; approved: number; rejected: number; items: Approval[] }> => {
    return request<{ total: number; approved: number; rejected: number; items: Approval[] }>(`/approvals?skip=${skip}&limit=${limit}`);
  },

  getApprovalStats: async (): Promise<Record<string, any>> => {
    return request<Record<string, any>>("/approvals/statistics");
  },

  createApproval: async (recommendationId: number, decision: "approved" | "rejected", comments?: string): Promise<Approval> => {
    return request<Approval>("/approvals", {
      method: "POST",
      body: JSON.stringify({
        recommendation_id: recommendationId,
        decision,
        comments,
      }),
    });
  },

  analyzeInteraction: async (customerId: number, interactionType: string, content: string): Promise<AnalysisResponse> => {
    return request<AnalysisResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify({
        customer_id: customerId,
        interaction_type: interactionType,
        content,
      }),
    });
  },
};
