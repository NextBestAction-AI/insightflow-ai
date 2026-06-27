import { motion } from "framer-motion";
import { Users, AlertTriangle, TrendingUp, DollarSign } from "lucide-react";

import CustomerHealth from "../components/dashboard/CustomerHealth";
import { MOCK_CUSTOMERS } from "../data/mockDashboard";

function CommandCenter() {
  const criticalCount = MOCK_CUSTOMERS.filter((c) => c.churnRisk === "High").length;
  const avgHealth = Math.round(
    MOCK_CUSTOMERS.reduce((sum, c) => sum + c.health, 0) / MOCK_CUSTOMERS.length
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-7xl mx-auto"
    >
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">Customer Command Center</h1>
        <p className="mt-1 text-sm text-slate-400">
          Monitor portfolio health, renewal risk, and account status across your book of business.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <Users size={14} />
            Total Accounts
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{MOCK_CUSTOMERS.length}</p>
        </div>
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <TrendingUp size={14} />
            Avg Health Score
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-400">{avgHealth}%</p>
        </div>
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <AlertTriangle size={14} />
            Critical Accounts
          </div>
          <p className="mt-2 text-2xl font-bold text-rose-400">{criticalCount}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 rounded-[24px] border border-[#334155] bg-[#1E293B] p-5 shadow-lg overflow-hidden">
          <h2 className="text-lg font-bold text-white mb-4">Customer Portfolio</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[#334155] text-[10px] uppercase tracking-wider text-slate-500">
                  <th className="pb-3 pr-4">Customer</th>
                  <th className="pb-3 pr-4">Health</th>
                  <th className="pb-3 pr-4">ARR</th>
                  <th className="pb-3 pr-4">Renewal</th>
                  <th className="pb-3 pr-4">Risk</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_CUSTOMERS.map((customer) => (
                  <tr
                    key={customer.id}
                    className="border-b border-[#334155]/50 hover:bg-[#0F172A]/50 transition-colors"
                  >
                    <td className="py-3 pr-4 font-semibold text-white">{customer.name}</td>
                    <td className="py-3 pr-4">
                      <span
                        className={`font-bold ${
                          customer.health >= 80
                            ? "text-emerald-400"
                            : customer.health >= 60
                            ? "text-amber-400"
                            : "text-rose-400"
                        }`}
                      >
                        {customer.health}%
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-slate-300 flex items-center gap-1">
                      <DollarSign size={12} className="text-slate-500" />
                      {customer.arr.replace("$", "")}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">{customer.renewalDays}d</td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          customer.churnRisk === "Low"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : customer.churnRisk === "Medium"
                            ? "bg-amber-500/10 text-amber-400"
                            : "bg-rose-500/10 text-rose-400"
                        }`}
                      >
                        {customer.churnRisk}
                      </span>
                    </td>
                    <td className="py-3 text-slate-300">{customer.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-4">
          <CustomerHealth score={89} />
        </div>
      </div>
    </motion.div>
  );
}

export default CommandCenter;
