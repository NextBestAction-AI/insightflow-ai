import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { api, type Customer } from "../services/api";

import type {
  ActivityItem,
  DashboardMetrics,
  RecommendationStatus,
  ToastMessage,
  WorkflowStatus,
} from "../types/dashboard";
import {
  DEFAULT_ACTIVITIES,
  DEFAULT_METRICS,
  CURRENT_USER,
} from "../data/mockDashboard";

export interface RecommendationData {
  id?: number;
  customer: string;
  action: string;
  reason: string;
  confidence: number;
  expectedImpact: string;
  evidence: Array<{ text: string; type: "success" | "warning" | "info" }>;
}

const DEFAULT_RECOMMENDATION: RecommendationData = {
  id: 0,
  customer: "Acme Corporation",
  action: "Schedule Executive Business Review",
  reason: "Customer engagement decreased 18% over the past two weeks.",
  confidence: 96,
  expectedImpact: "Reduce churn risk by 23%",
  evidence: [
    { text: "Meeting transcript analyzed", type: "success" as const },
    { text: "CRM history reviewed", type: "success" as const },
    { text: "Product usage declined 18%", type: "warning" as const },
    { text: "Support tickets increased (+3 open tickets)", type: "warning" as const },
    { text: "Contract renewal due in 14 days", type: "info" as const },
  ],
};

const DEFAULT_SUMMARY_POINTS = [
  "Customer engagement has declined 18% over the past two weeks.",
  "Support volume increased with 3 open escalations.",
  "Renewal is approaching in 14 days ($128,000 ARR).",
  "Recommended proactive outreach via Executive Business Review.",
];

const DEFAULT_REASONING_QUOTE = "Based on cross-agent analysis of Acme Corporation, proactive executive engagement is the highest-impact intervention before renewal.";

interface DashboardContextValue {
  workflowStatus: WorkflowStatus;
  isAnalyzing: boolean;
  activeStep: number;
  recommendationStatus: RecommendationStatus;
  metrics: DashboardMetrics;
  activities: ActivityItem[];
  toasts: ToastMessage[];
  customers: Customer[];
  selectedCustomerId: number;
  setSelectedCustomerId: (id: number) => void;
  activeRecommendation: RecommendationData;
  summaryPoints: string[];
  reasoningQuote: string;
  startAnalysis: (fileName: string) => Promise<void>;
  resetWorkflow: () => void;
  handleRecommendationAction: (
    action: "approve" | "reject" | "modify" | "save_modification",
    modifiedText?: string
  ) => Promise<void>;
  showToast: (message: string, type?: ToastMessage["type"]) => void;
  dismissToast: (id: number) => void;
  user: typeof CURRENT_USER;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>("idle");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [recommendationStatus, setRecommendationStatus] =
    useState<RecommendationStatus>("pending");
  const [metrics, setMetrics] = useState<DashboardMetrics>(DEFAULT_METRICS);
  const [activities, setActivities] = useState<ActivityItem[]>(DEFAULT_ACTIVITIES);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number>(1);
  const [activeRecommendation, setActiveRecommendation] = useState<RecommendationData>(DEFAULT_RECOMMENDATION);
  const [summaryPoints, setSummaryPoints] = useState<string[]>(DEFAULT_SUMMARY_POINTS);
  const [reasoningQuote, setReasoningQuote] = useState<string>(DEFAULT_REASONING_QUOTE);

  const loadCustomersAndRecommendations = useCallback(async () => {
    try {
      const res = await api.getCustomers();
      setCustomers(res.items);
      
      // If there's a customer, set selected customer ID
      if (res.items.length > 0) {
        setSelectedCustomerId(res.items[0].id);
      }
    } catch (err) {
      console.error("Failed to load customer list:", err);
    }
  }, []);

  useEffect(() => {
    loadCustomersAndRecommendations();
  }, [loadCustomersAndRecommendations]);

  const showToast = useCallback((message: string, type: ToastMessage["type"] = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Text content library matching doc types
  const sampleContents: Record<string, string> = {
    "transcript": `[CS Rep]: Hello Alice, thank you for joining today's account review.
[Alice (Acme Corporation)]: Hi. I wanted to discuss our ongoing dashboard latency issues. Our team is experiencing query timeouts exceeding 30 seconds when running reports over a 30-day window. This is severely impacting our daily operations.
[CS Rep]: I understand. I will escalate this to database engineering to see if read replicas or query pre-aggregation can be configured.
[Alice]: Please do. Also, our renewal is coming up in 60 days, and if these issues are not resolved, we will have to look at other options.`,
    "crm notes": `Customer CUST-101 (Acme Corporation) has flagged severe dissatisfaction with dashboard performance. Renewal approaches on 2026-08-15 (ACV: $120,000). There are 3 open support tickets regarding timeout failures. DAU/MAU adoption ratio has dropped to 12%.`,
    "email": `Subject: Urgent: Dissatisfaction with reporting latency
Dear Team, we are writing to express our frustration with the report generation timeout failures we are experiencing. The dashboard frequently hangs when retrieving rows. Please let us know the timeline for remediation, otherwise we will request a billing credit.`,
    "support ticket": `Ticket ID: #4402 - Dashboard query timeout error. Customer Acme Corporation reports live charts fail to load with SQL execution limit errors. Severity: Critical. Status: Escalated.`,
    "conversation": `Acme Corporation is reporting slow analytics queries. They are currently looking to optimize live chart latency. The customer success rep promised to check DB replication lagging metrics.`
  };

  const startAnalysis = useCallback(
    async (fileName: string) => {
      setIsAnalyzing(true);
      setActiveStep(0);
      setRecommendationStatus("pending");
      setWorkflowStatus("analyzing");

      const timeStr = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      const startId = Date.now();

      setActivities([
        {
          id: startId,
          time: timeStr,
          title: "Interaction uploaded",
          description: `Analyzing customer interactions from "${fileName}"...`,
          type: "upload",
        },
      ]);

      // Deduce doc type from filename or select default
      const docTypeLower = fileName.split(".")[0].replace(/_/g, " ").toLowerCase();
      let selectedType = "transcript";
      for (const t of Object.keys(sampleContents)) {
        if (docTypeLower.includes(t)) {
          selectedType = t;
          break;
        }
      }
      const content = sampleContents[selectedType] || sampleContents["transcript"];

      try {
        // Trigger live analysis in backend FastAPI + AI Orchestrator
        const response = await api.analyzeInteraction(selectedCustomerId, selectedType, content);

        if (response.status === "success") {
          // Play back steps step-by-step for cool UX
          const backendActivities = response.activities || [];
          let currentStep = 0;
          
          const interval = setInterval(() => {
            currentStep += 1;
            setActiveStep(currentStep);

            if (currentStep >= backendActivities.length) {
              clearInterval(interval);
              setIsAnalyzing(false);
              setWorkflowStatus("waiting_approval");
              
              const formattedActivities = backendActivities.map((act: any, idx: number) => ({
                id: Number(act.id) || (startId + idx),
                time: act.time,
                title: act.title,
                description: act.description,
                type: act.type as any
              }));
              setActivities(formattedActivities);
              
              // Load generated recommendations
              const firstRec = response.recommendations?.[0];
              const customerName = customers.find(c => c.id === selectedCustomerId)?.company || "Acme Corporation";
              
              if (firstRec) {
                // Map DB recommendation to UI
                const actionTitle = firstRec.action.split(":")[0] || firstRec.action;
                
                setActiveRecommendation({
                  id: firstRec.id,
                  customer: customerName,
                  action: actionTitle,
                  reason: firstRec.reason.split("Reasoning:")[1]?.split("Evidence:")[0]?.trim() || firstRec.reason,
                  confidence: Math.round(firstRec.confidence * 100),
                  expectedImpact: "Mitigate customer renewal risk",
                  evidence: [
                    { text: "Meeting transcript analyzed", type: "success" },
                    { text: "CRM history reviewed", type: "success" },
                    { text: "Product usage metrics synced", type: "info" }
                  ]
                });
              }

              // Load Metrics
              setMetrics({
                customerHealth: response.health_assessment?.score ?? 89,
                renewalProbability: response.risk_assessment?.overall_level === "low" ? 91 : response.risk_assessment?.overall_level === "medium" ? 75 : 45,
                churnRisk: response.risk_assessment?.overall_level ? (response.risk_assessment.overall_level.charAt(0).toUpperCase() + response.risk_assessment.overall_level.slice(1)) : "Low",
                aiConfidence: Math.round((response.risk_assessment?.confidence ?? 0.95) * 100),
              });

              // Load Executive Summary Points from reasoning findings
              const findings = response.business_reasoning?.key_findings || [];
              if (findings.length > 0) {
                setSummaryPoints(findings.map((f: any) => f.reasoning || f.title));
              }
              if (response.business_reasoning?.summary) {
                setReasoningQuote(response.business_reasoning.summary);
              }

              showToast("AI analysis complete — recommendation ready for review", "success");
            }
          }, 800);
        }
      } catch (err: any) {
        console.error("AI analysis execution failed:", err);
        setIsAnalyzing(false);
        setWorkflowStatus("idle");
        showToast(err.message || "Failed to complete AI Orchestrator analysis", "error");
      }
    },
    [selectedCustomerId, customers, showToast]
  );

  const resetWorkflow = useCallback(() => {
    setActiveStep(0);
    setIsAnalyzing(false);
    setRecommendationStatus("pending");
    setWorkflowStatus("idle");
    setMetrics(DEFAULT_METRICS);
    setActivities(DEFAULT_ACTIVITIES);
    setActiveRecommendation(DEFAULT_RECOMMENDATION);
    setSummaryPoints(DEFAULT_SUMMARY_POINTS);
    setReasoningQuote(DEFAULT_REASONING_QUOTE);
  }, []);

  const handleRecommendationAction = useCallback(
    async (
      action: "approve" | "reject" | "modify" | "save_modification",
      modifiedText?: string
    ) => {
      const stepTime = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      const actionId = Date.now();

      if (!activeRecommendation.id) {
        showToast("No active recommendation to act on", "error");
        return;
      }

      try {
        if (action === "approve") {
          await api.createApproval(activeRecommendation.id, "approved", "Approved via dashboard CS Command Center");
          await api.updateRecommendation(activeRecommendation.id, { status: "approved" });

          setRecommendationStatus("approved");
          setWorkflowStatus("approved");
          setMetrics((prev) => ({
            ...prev,
            aiConfidence: Math.min(prev.aiConfidence + 1, 99),
          }));
          setActivities((prev) => [
            {
              id: actionId,
              time: stepTime,
              title: `Approved by ${CURRENT_USER.name}`,
              description: `Executing '${activeRecommendation.action}'. Syncing to Salesforce...`,
              type: "approval",
            },
            ...prev,
          ]);
          showToast("Recommendation approved — action synced to CRM", "success");
        } else if (action === "reject") {
          await api.createApproval(activeRecommendation.id, "rejected", "Rejected via dashboard");
          await api.updateRecommendation(activeRecommendation.id, { status: "rejected" });

          setRecommendationStatus("rejected");
          setWorkflowStatus("rejected");
          setActivities((prev) => [
            {
              id: actionId,
              time: stepTime,
              title: "Recommendation rejected",
              description: "Proposed action dismissed. Adjusting model inference weights.",
              type: "system",
            },
            ...prev,
          ]);
          showToast("Recommendation rejected", "error");
        } else if (action === "save_modification") {
          await api.updateRecommendation(activeRecommendation.id, {
            action: modifiedText || activeRecommendation.action,
          });

          setRecommendationStatus("modified");
          setWorkflowStatus("modified");
          setActiveRecommendation(prev => ({
            ...prev,
            action: modifiedText || prev.action,
          }));
          setActivities((prev) => [
            {
              id: actionId,
              time: stepTime,
              title: "Recommendation modified",
              description: `Updated action: "${modifiedText}". Resaved to operations buffer.`,
              type: "system",
            },
            ...prev,
          ]);
          showToast("Recommendation updated successfully", "info");
        }
      } catch (err: any) {
        console.error("Failed to execute recommendation action:", err);
        showToast(err.message || "Failed to sync action to backend database", "error");
      }
    },
    [activeRecommendation, showToast]
  );

  return (
    <DashboardContext.Provider
      value={{
        workflowStatus,
        isAnalyzing,
        activeStep,
        recommendationStatus,
        metrics,
        activities,
        toasts,
        customers,
        selectedCustomerId,
        setSelectedCustomerId,
        activeRecommendation,
        summaryPoints,
        reasoningQuote,
        startAnalysis,
        resetWorkflow,
        handleRecommendationAction,
        showToast,
        dismissToast,
        user: CURRENT_USER,
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return context;
}
