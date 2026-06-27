import { motion } from "framer-motion";
import { Brain, Database, Cpu, CheckCircle } from "lucide-react";

import { CURRENT_USER } from "../../data/mockDashboard";
import { useDashboard } from "../../context/DashboardContext";

function WelcomeBanner() {
  const { workflowStatus, isAnalyzing } = useDashboard();

  const chips = [
    {
      text: isAnalyzing ? "Planner Running" : "Planner Active",
      color: "text-emerald-400 border-emerald-500/20 bg-emerald-500/5",
      icon: Cpu,
      pulse: isAnalyzing,
    },
    {
      text: "Memory Enabled",
      color: "text-blue-400 border-blue-500/20 bg-blue-500/5",
      icon: Brain,
      pulse: true,
    },
    {
      text: "Knowledge Base Synced",
      color: "text-violet-400 border-violet-500/20 bg-violet-500/5",
      icon: Database,
      pulse: false,
    },
    {
      text: "9 Agents Online",
      color: "text-amber-400 border-amber-500/20 bg-amber-500/5",
      icon: CheckCircle,
      pulse: workflowStatus === "analyzing",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="relative overflow-hidden rounded-[24px] border border-[#334155] bg-gradient-to-r from-slate-900 via-[#1E293B] to-slate-900 p-6 md:p-8 shadow-xl"
    >
      {/* Gradient border glow */}
      <div className="absolute inset-0 rounded-[24px] border border-transparent bg-gradient-to-r from-blue-500/20 via-violet-500/10 to-emerald-500/20 pointer-events-none" />

      <div className="absolute top-0 right-0 -mr-20 -mt-20 h-72 w-72 rounded-full bg-blue-600/10 blur-[80px] animate-pulse" />
      <div className="absolute bottom-0 left-0 -ml-20 -mb-20 h-72 w-72 rounded-full bg-violet-600/10 blur-[80px]" />

      <div className="relative z-10 flex flex-col justify-between h-full">
        <div>
          <motion.h1
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="text-2xl md:text-4xl font-extrabold text-white"
          >
            Welcome back, {CURRENT_USER.name}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-2 text-sm md:text-base font-medium text-blue-400"
          >
            AI Customer Success Platform
          </motion.p>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35, duration: 0.5 }}
            className="mt-2 max-w-2xl text-sm text-slate-300 leading-relaxed"
          >
            Your AI agents are analyzing customer interactions, retrieving knowledge, and
            orchestrating next best actions to minimize churn.
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.6 }}
          className="mt-6 flex flex-wrap gap-3"
        >
          {chips.map((chip, idx) => {
            const Icon = chip.icon;
            return (
              <div
                key={idx}
                className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 text-xs font-semibold ${chip.color} shadow-sm backdrop-blur-sm transition-transform hover:scale-[1.03] duration-200`}
              >
                <Icon size={14} className="shrink-0" />
                {chip.pulse && (
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
                  </span>
                )}
                <span>{chip.text}</span>
              </div>
            );
          })}
        </motion.div>
      </div>
    </motion.div>
  );
}

export default WelcomeBanner;
