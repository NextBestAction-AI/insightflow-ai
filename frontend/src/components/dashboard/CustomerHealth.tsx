import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  TrendingUp,
  Activity,
  Users,
  Ticket,
  Target,
  CalendarCheck,
} from "lucide-react";

import { CUSTOMER } from "../../data/mockDashboard";
import { useDashboard } from "../../context/DashboardContext";

interface CustomerHealthProps {
  score?: number;
}

function CustomerHealth({ score: scoreProp }: CustomerHealthProps) {
  const { workflowStatus, activeStep } = useDashboard();
  const score = scoreProp ?? CUSTOMER.health;
  const [animatedScore, setAnimatedScore] = useState(0);

  const showFullData =
    activeStep >= 5 ||
    workflowStatus === "waiting_approval" ||
    workflowStatus === "approved" ||
    workflowStatus === "completed" ||
    workflowStatus === "modified" ||
    workflowStatus === "rejected";

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScore(showFullData ? score : 0);
    }, 200);
    return () => clearTimeout(timer);
  }, [score, showFullData]);

  const radius = 70;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (animatedScore / 100) * circumference;

  const metrics = [
    { name: "Usage", value: "78%", meter: 78, status: "warning" as const, icon: Activity },
    { name: "Adoption", value: "87%", meter: 87, status: "success" as const, icon: Users },
    { name: "Support Tickets", value: "3 Open", meter: 40, status: "warning" as const, icon: Ticket },
    { name: "Engagement", value: "72%", meter: 72, status: "warning" as const, icon: Target },
    {
      name: "Renewal Probability",
      value: "91%",
      meter: 91,
      status: "success" as const,
      icon: CalendarCheck,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg h-full flex flex-col gap-4"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <TrendingUp size={18} className="text-emerald-400" />
          Customer Health
        </h2>
        <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs text-emerald-400 font-bold flex items-center gap-1">
          <ShieldCheck size={12} /> Healthy
        </span>
      </div>

      <div className="flex flex-col items-center gap-6 py-2">
        <div className="relative flex h-44 w-44 items-center justify-center flex-shrink-0">
          <div className="absolute inset-0 rounded-full bg-emerald-500/5 blur-xl" />
          <svg className="h-full w-full -rotate-90">
            <circle
              cx="88"
              cy="88"
              r={radius}
              className="stroke-[#0F172A]"
              strokeWidth={strokeWidth}
              fill="transparent"
            />
            <motion.circle
              cx="88"
              cy="88"
              r={radius}
              stroke="url(#healthGradient)"
              strokeWidth={strokeWidth}
              fill="transparent"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset }}
              transition={{ duration: 1.5, ease: "easeOut" }}
              strokeLinecap="round"
            />
            <defs>
              <linearGradient id="healthGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#2563EB" />
                <stop offset="50%" stopColor="#7C3AED" />
                <stop offset="100%" stopColor="#22C55E" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute text-center">
            <motion.h1
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, type: "spring", stiffness: 180 }}
              className="text-4xl font-extrabold text-white tracking-tight"
            >
              {showFullData ? `${animatedScore}%` : "—"}
            </motion.h1>
            <p className="text-[10px] uppercase font-bold text-slate-400 tracking-widest mt-0.5">
              {showFullData ? "Healthy" : "Pending"}
            </p>
            <p className="text-[9px] text-slate-500 mt-1">{CUSTOMER.name}</p>
          </div>
        </div>
      </div>

      {showFullData && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {metrics.map((metric, idx) => {
            const Icon = metric.icon;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.08 }}
                className="bg-[#0F172A] border border-[#334155]/30 rounded-xl p-3"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={14} className="text-slate-400" />
                  <span className="text-[10px] font-semibold text-slate-400">{metric.name}</span>
                </div>
                <div className="flex items-end justify-between mb-2">
                  <span className="text-lg font-bold text-white">{metric.value}</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${metric.meter}%` }}
                    transition={{ duration: 1, delay: 0.3 + idx * 0.1 }}
                    className={`h-full rounded-full ${
                      metric.status === "success" ? "bg-emerald-500" : "bg-amber-500"
                    }`}
                  />
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}

export default CustomerHealth;
