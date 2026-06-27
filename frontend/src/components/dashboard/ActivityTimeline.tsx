import { motion } from "framer-motion";
import {
  UploadCloud,
  Database,
  AlertTriangle,
  Sparkles,
  CheckCircle2,
  Clock,
  Activity,
} from "lucide-react";

import type { ActivityItem } from "../../types/dashboard";
import { DEFAULT_ACTIVITIES } from "../../data/mockDashboard";

interface ActivityTimelineProps {
  activities?: ActivityItem[];
}

const typeConfig = {
  upload: { icon: UploadCloud, color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  retrieve: { icon: Database, color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  health: { icon: Activity, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  risk: { icon: AlertTriangle, color: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
  recommendation: {
    icon: Sparkles,
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  approval: {
    icon: CheckCircle2,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  system: { icon: Clock, color: "text-slate-400 bg-slate-500/10 border-slate-500/20" },
};

function ActivityTimeline({ activities = DEFAULT_ACTIVITIES }: ActivityTimelineProps) {
  return (
    <div className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg h-full">
      <div className="flex items-center justify-between border-b border-[#334155] pb-4 mb-6">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Clock size={18} className="text-blue-400" />
          Activity Timeline
        </h2>
        <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest bg-slate-900 px-2 py-0.5 rounded border border-[#334155]">
          AI Audit Trail
        </span>
      </div>

      <div className="relative pl-6 space-y-6 text-left">
        <div className="absolute left-3 top-3 bottom-3 w-[1.5px] bg-[#334155]" />

        {activities.map((item, idx) => {
          const config = typeConfig[item.type] || typeConfig.system;
          const Icon = config.icon;

          return (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.4 }}
              key={item.id}
              className="relative flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-6"
            >
              <div className="absolute -left-9 z-10 flex h-7.5 w-7.5 items-center justify-center rounded-lg border bg-[#1E293B] shadow-sm shadow-black/20">
                <div className={`p-1.5 rounded-md ${config.color}`}>
                  <Icon size={12} className="shrink-0" />
                </div>
              </div>

              <div className="sm:w-16 text-[10px] font-bold text-slate-400 font-mono sm:pt-1">
                {item.time}
              </div>

              <div className="flex-1 rounded-xl bg-[#0F172A] border border-[#334155]/30 p-3.5 hover:border-slate-600 transition-colors duration-200">
                <h4 className="text-xs font-bold text-white">{item.title}</h4>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                  {item.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

export default ActivityTimeline;
export type { ActivityItem };
