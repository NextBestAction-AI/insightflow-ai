import { motion } from "framer-motion";

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
  const { isAnalyzing, startAnalysis, activities } = useDashboard();

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
          <CustomerHealth />
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
