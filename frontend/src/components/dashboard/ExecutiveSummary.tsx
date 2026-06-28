import { motion } from "framer-motion";
import { Brain, Sparkles } from "lucide-react";

import { useDashboard } from "../../context/DashboardContext";

function ExecutiveSummary() {
  const { workflowStatus, summaryPoints, reasoningQuote } = useDashboard();

  const isLive =
    workflowStatus === "analyzing" ||
    workflowStatus === "waiting_approval" ||
    workflowStatus === "approved";

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="relative overflow-hidden rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg"
    >
      <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-violet-600/10 blur-[60px]" />

      <div className="relative z-10">
        <div className="flex items-center justify-between border-b border-[#334155] pb-4 mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Brain size={18} className="text-violet-400" />
            Executive Summary
          </h2>
          {isLive && (
            <span className="flex items-center gap-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 px-2.5 py-0.5 text-[10px] text-violet-400 font-semibold">
              <Sparkles size={10} />
              AI Generated
            </span>
          )}
        </div>

        <div className="space-y-3">
          {summaryPoints.map((point, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + idx * 0.1 }}
              className="flex items-start gap-3"
            >
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
              <p className="text-sm text-slate-300 leading-relaxed">{point}</p>
            </motion.div>
          ))}
        </div>

        <div className="mt-4 rounded-xl bg-[#0F172A] border border-[#334155]/50 p-3">
          <p className="text-xs text-slate-400 italic leading-relaxed">
            &ldquo;{reasoningQuote}&rdquo;
          </p>
          <p className="mt-2 text-[10px] text-violet-400 font-medium">
            — Business Reasoning Agent
          </p>
        </div>
      </div>
    </motion.div>
  );
}

export default ExecutiveSummary;
