import { motion } from "framer-motion";
import { Database } from "lucide-react";

import WelcomeBanner from "../components/dashboard/WelcomeBanner";
import StatsGrid from "../components/dashboard/StatsGrid";
import UploadCard from "../components/dashboard/UploadCard";
import PlannerWorkflow from "../components/dashboard/PlannerWorkflow";
import AgentStatus from "../components/dashboard/AgentStatus";
import RecommendationCard from "../components/dashboard/RecommendationCard";
import CustomerHealth from "../components/dashboard/CustomerHealth";
import ExecutiveSummary from "../components/dashboard/ExecutiveSummary";
import ActivityTimeline from "../components/dashboard/ActivityTimeline";
import { useDashboard } from "../context/DashboardContext";

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 100, damping: 15 },
  },
};

function Dashboard() {
  const { isAnalyzing, startAnalysis, activities, metrics, customers, loadDemoData } = useDashboard();

  if (customers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-8 max-w-xl mx-auto space-y-6 bg-slate-900/50 backdrop-blur-md border border-[#334155] rounded-[24px] shadow-2xl">
        <div className="h-16 w-16 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-full flex items-center justify-center animate-pulse">
          <Database size={32} />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white font-sans">No Customers Available</h2>
          <p className="text-sm text-slate-400 font-sans leading-relaxed">
            It looks like the local database is currently empty. You can quickly seed the database with sample customer profiles to experience the multi-agent pipeline.
          </p>
        </div>
        <button
          onClick={loadDemoData}
          className="px-6 py-3.5 bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-xs font-bold text-white rounded-xl shadow-lg shadow-blue-500/20 transition duration-300 transform hover:scale-[1.02] uppercase tracking-wider cursor-pointer font-sans"
        >
          Load Demo Data
        </button>
      </div>
    );
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-6 max-w-7xl mx-auto"
    >
      <motion.div variants={itemVariants}>
        <WelcomeBanner />
      </motion.div>

      <motion.div variants={itemVariants}>
        <StatsGrid />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        <motion.div variants={itemVariants} className="lg:col-span-4 h-full">
          <UploadCard onStartAnalysis={startAnalysis} isAnalyzing={isAnalyzing} />
        </motion.div>
        <motion.div variants={itemVariants} className="lg:col-span-8 h-full">
          <PlannerWorkflow />
        </motion.div>
      </div>

      <motion.div variants={itemVariants}>
        <AgentStatus />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        <motion.div variants={itemVariants} className="h-full">
          <RecommendationCard />
        </motion.div>
        <motion.div variants={itemVariants} className="h-full">
          <CustomerHealth score={metrics.customerHealth} />
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        <motion.div variants={itemVariants} className="h-full">
          <ExecutiveSummary />
        </motion.div>
        <motion.div variants={itemVariants} className="h-full">
          <ActivityTimeline activities={activities} />
        </motion.div>
      </div>
    </motion.div>
  );
}

export default Dashboard;
