import { Heart, RefreshCw, ShieldAlert, Target } from "lucide-react";
import StatCard from "./StatCard";
import { useDashboard } from "../../context/DashboardContext";

function StatsGrid() {
  const { metrics } = useDashboard();

  return (
    <div className="grid gap-4 sm:gap-6 grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="Customer Health"
        value={`${metrics.customerHealth}%`}
        trend="+4.8%"
        trendDirection="up"
        trendType="success"
        icon={Heart}
        iconColor="text-emerald-400"
        iconBg="bg-emerald-500/10 border border-emerald-500/20"
      />

      <StatCard
        title="Renewal Probability"
        value={`${metrics.renewalProbability}%`}
        trend="+2.1%"
        trendDirection="up"
        trendType="success"
        icon={RefreshCw}
        iconColor="text-blue-400"
        iconBg="bg-blue-500/10 border border-blue-500/20"
      />

      <StatCard
        title="Churn Risk"
        value={metrics.churnRisk}
        trend="Stable"
        trendDirection="neutral"
        trendType="success"
        icon={ShieldAlert}
        iconColor="text-amber-400"
        iconBg="bg-amber-500/10 border border-amber-500/20"
      />

      <StatCard
        title="AI Confidence"
        value={`${metrics.aiConfidence}%`}
        trend="High Accuracy"
        trendDirection="neutral"
        trendType="success"
        icon={Target}
        iconColor="text-violet-400"
        iconBg="bg-violet-500/10 border border-violet-500/20"
      />
    </div>
  );
}

export default StatsGrid;
