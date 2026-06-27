import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  trend: string;
  trendDirection: "up" | "down" | "neutral";
  trendType: "success" | "warning" | "danger" | "info";
  icon: LucideIcon;
  iconColor: string;
  iconBg: string;
}

function StatCard({
  title,
  value,
  trend,
  trendDirection,
  trendType,
  icon: Icon,
  iconColor,
  iconBg,
}: StatCardProps) {
  // Simple integer count animator if value is numeric
  const numericValue = parseInt(value.replace(/[^0-9]/g, ""), 10);
  const suffix = value.replace(/[0-9]/g, "");
  const [count, setCount] = useState(isNaN(numericValue) ? 0 : Math.floor(numericValue * 0.3));

  useEffect(() => {
    if (isNaN(numericValue)) return;
    const start = Math.floor(numericValue * 0.3);
    const duration = 1000; // ms
    const startTime = performance.now();

    let animationFrameId: number;

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out quad
      const easeProgress = progress * (2 - progress);
      const currentCount = Math.floor(start + (numericValue - start) * easeProgress);
      
      setCount(currentCount);

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        setCount(numericValue);
      }
    };

    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [numericValue]);

  const trendColorClass = {
    success: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    warning: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    danger: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    info: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  }[trendType];

  return (
    <motion.div
      whileHover={{ y: -4, scale: 1.01, boxShadow: "0 10px 30px -10px rgba(37, 99, 235, 0.15)" }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className="relative overflow-hidden rounded-[20px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg transition-shadow duration-300"
    >
      {/* Visual background highlight on card corners */}
      <div className="absolute -top-10 -right-10 h-24 w-24 rounded-full bg-blue-500/5 blur-xl group-hover:bg-blue-500/10 transition-all duration-300" />

      <div className="flex items-center justify-between">
        <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">
          {title}
        </span>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg} ${iconColor} shadow-inner`}>
          <Icon size={20} />
        </div>
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <h2 className="text-3xl font-extrabold text-white tracking-tight">
          {isNaN(numericValue) ? value : `${suffix === "%" ? "" : suffix}${count}${suffix === "%" ? "%" : ""}`}
        </h2>
        
        <span className={`inline-flex items-center gap-0.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${trendColorClass}`}>
          {trendDirection === "up" && "↑"}
          {trendDirection === "down" && "↓"}
          {trend}
        </span>
      </div>

      <p className="mt-2 text-slate-400 text-xs font-medium">
        vs last billing cycle
      </p>
    </motion.div>
  );
}

export default StatCard;