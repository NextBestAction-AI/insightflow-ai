import { apiClient } from "./apiClient";
import type { Recommendation } from "./recommendationApi";

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

export const analysisApi = {
  analyzeInteraction: async (customerId: number, interactionType: string, content: string): Promise<AnalysisResponse> => {
    const res = await apiClient.post<AnalysisResponse>("/analyze", {
      customer_id: customerId,
      interaction_type: interactionType,
      content,
    });
    return res.data;
  },
};
