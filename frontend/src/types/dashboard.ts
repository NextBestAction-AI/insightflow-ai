export type WorkflowStatus =
  | "idle"
  | "analyzing"
  | "completed"
  | "waiting_approval"
  | "approved"
  | "rejected"
  | "modified";

export type RecommendationStatus = "pending" | "approved" | "rejected" | "modified";

export type AgentState = "completed" | "running" | "waiting";

export type ActivityType =
  | "upload"
  | "retrieve"
  | "health"
  | "risk"
  | "recommendation"
  | "approval"
  | "system";

export interface ActivityItem {
  id: number;
  time: string;
  title: string;
  description: string;
  type: ActivityType;
}

export interface AgentNode {
  id: number;
  name: string;
  role: string;
  activity: string;
  log: string;
}

export interface CustomerData {
  name: string;
  health: number;
  renewalProbability: number;
  churnRisk: "Low" | "Medium" | "High";
  confidence: number;
}

export interface ToastMessage {
  id: number;
  message: string;
  type: "success" | "error" | "info" | "warning";
}

export interface DashboardMetrics {
  customerHealth: number;
  renewalProbability: number;
  churnRisk: string;
  aiConfidence: number;
}
