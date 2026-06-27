import { motion } from "framer-motion";

import RecommendationCard from "../components/dashboard/RecommendationCard";
import ExecutiveSummary from "../components/dashboard/ExecutiveSummary";

function Recommendation() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-7xl mx-auto"
    >
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">Recommendations</h1>
        <p className="mt-1 text-sm text-slate-400">
          Review AI-generated next best actions, approve or modify them, and sync to your CRM.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        <RecommendationCard />
        <ExecutiveSummary />
      </div>
    </motion.div>
  );
}

export default Recommendation;
