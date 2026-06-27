import { motion } from "framer-motion";

import UploadCard from "../components/dashboard/UploadCard";
import PlannerWorkflow from "../components/dashboard/PlannerWorkflow";
import AgentStatus from "../components/dashboard/AgentStatus";
import { useDashboard } from "../context/DashboardContext";

function Analysis() {
  const { isAnalyzing, startAnalysis } = useDashboard();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-7xl mx-auto"
    >
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">AI Agent Orchestrator</h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload customer interactions and watch the multi-agent pipeline analyze, retrieve knowledge,
          and generate recommendations.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        <div className="lg:col-span-4 h-full">
          <UploadCard onStartAnalysis={startAnalysis} isAnalyzing={isAnalyzing} />
        </div>
        <div className="lg:col-span-8 h-full">
          <PlannerWorkflow />
        </div>
      </div>

      <AgentStatus />
    </motion.div>
  );
}

export default Analysis;
