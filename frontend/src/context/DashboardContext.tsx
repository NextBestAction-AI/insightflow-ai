import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from "react";

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

interface DashboardContextValue {
  workflowStatus: WorkflowStatus;
  isAnalyzing: boolean;
  activeStep: number;
  recommendationStatus: RecommendationStatus;
  metrics: DashboardMetrics;
  activities: ActivityItem[];
  toasts: ToastMessage[];
  startAnalysis: (fileName: string) => void;
  resetWorkflow: () => void;
  handleRecommendationAction: (
    action: "approve" | "reject" | "modify" | "save_modification",
    modifiedText?: string
  ) => void;
  showToast: (message: string, type?: ToastMessage["type"]) => void;
  dismissToast: (id: number) => void;
  user: typeof CURRENT_USER;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>("waiting_approval");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeStep, setActiveStep] = useState(11);
  const [recommendationStatus, setRecommendationStatus] =
    useState<RecommendationStatus>("pending");
  const [metrics, setMetrics] = useState<DashboardMetrics>(DEFAULT_METRICS);
  const [activities, setActivities] = useState<ActivityItem[]>(DEFAULT_ACTIVITIES);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const startAnalysis = useCallback(
    (fileName: string) => {
      if (intervalRef.current) clearInterval(intervalRef.current);

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

      let currentStep = 0;
      intervalRef.current = setInterval(() => {
        currentStep += 1;
        setActiveStep(currentStep);

        const stepTime = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        if (currentStep === 3) {
          setActivities((prev) => [
            {
              id: startId + 3,
              time: stepTime,
              title: "Knowledge retrieved",
              description: "Retrieved contract details and 4 relevant solution manuals.",
              type: "retrieve",
            },
            ...prev,
          ]);
        } else if (currentStep === 5) {
          setActivities((prev) => [
            {
              id: startId + 5,
              time: stepTime,
              title: "Customer health calculated",
              description: "Health score: 89% — engagement signals analyzed across 5 dimensions.",
              type: "health",
            },
            ...prev,
          ]);
        } else if (currentStep === 6) {
          setActivities((prev) => [
            {
              id: startId + 6,
              time: stepTime,
              title: "Risk detected",
              description: "Engagement declined 18%; 3 open escalations flagged.",
              type: "risk",
            },
            ...prev,
          ]);
        } else if (currentStep === 8) {
          setActivities((prev) => [
            {
              id: startId + 8,
              time: stepTime,
              title: "Recommendation generated",
              description: "Schedule Executive Business Review — reduce churn risk by 23%.",
              type: "recommendation",
            },
            ...prev,
          ]);
        } else if (currentStep === 11) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setIsAnalyzing(false);
          setWorkflowStatus("waiting_approval");
          setActivities((prev) => [
            {
              id: startId + 11,
              time: stepTime,
              title: "Multi-agent cycle completed",
              description: "Awaiting human approval on proposed retention recommendation.",
              type: "system",
            },
            ...prev,
          ]);
          showToast("AI analysis complete — recommendation ready for review", "success");
        }
      }, 1200);
    },
    [showToast]
  );

  const resetWorkflow = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setActiveStep(0);
    setIsAnalyzing(false);
    setRecommendationStatus("pending");
    setWorkflowStatus("idle");
    setMetrics(DEFAULT_METRICS);
    setActivities(DEFAULT_ACTIVITIES);
  }, []);

  const handleRecommendationAction = useCallback(
    (
      action: "approve" | "reject" | "modify" | "save_modification",
      modifiedText?: string
    ) => {
      const stepTime = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      const actionId = Date.now();

      if (action === "approve") {
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
            description:
              "Executing 'Schedule Executive Business Review'. Syncing to Salesforce...",
            type: "approval",
          },
          ...prev,
        ]);
        showToast("Recommendation approved — action synced to CRM", "success");
      } else if (action === "reject") {
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
        setRecommendationStatus("modified");
        setWorkflowStatus("modified");
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
    },
    [showToast]
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
