import { motion } from "framer-motion";

import ActivityTimeline from "../components/dashboard/ActivityTimeline";
import { useDashboard } from "../context/DashboardContext";

function History() {
  const { activities } = useDashboard();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-4xl mx-auto"
    >
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">Activity History</h1>
        <p className="mt-1 text-sm text-slate-400">
          Full audit trail of AI agent actions, recommendations, and human approvals.
        </p>
      </div>

      <ActivityTimeline activities={activities} />
    </motion.div>
  );
}

export default History;
