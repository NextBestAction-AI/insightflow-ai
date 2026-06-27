import { motion } from "framer-motion";
import { Bell, Bot, Shield, User } from "lucide-react";

import { CURRENT_USER } from "../data/mockDashboard";

function DecisionCenter() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-3xl mx-auto"
    >
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">Settings</h1>
        <p className="mt-1 text-sm text-slate-400">
          Manage your profile, AI preferences, and notification settings.
        </p>
      </div>

      <section className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <User size={16} className="text-blue-400" />
          Profile
        </h2>
        <div className="flex items-center gap-4 mb-4">
          <img
            src={CURRENT_USER.avatar}
            alt={CURRENT_USER.name}
            className="h-14 w-14 rounded-full border border-blue-500/30 object-cover"
          />
          <div>
            <p className="font-semibold text-white">{CURRENT_USER.name}</p>
            <p className="text-xs text-slate-400">{CURRENT_USER.role}</p>
            <p className="text-xs text-slate-500">{CURRENT_USER.email}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase">Display Name</label>
            <input
              type="text"
              defaultValue={CURRENT_USER.name}
              className="mt-1 w-full rounded-xl border border-[#334155] bg-[#0F172A] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase">Email</label>
            <input
              type="email"
              defaultValue={CURRENT_USER.email}
              className="mt-1 w-full rounded-xl border border-[#334155] bg-[#0F172A] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </section>

      <section className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <Bot size={16} className="text-violet-400" />
          AI Configuration
        </h2>
        <div className="space-y-4">
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase">Default Model</label>
            <select className="mt-1 w-full rounded-xl border border-[#334155] bg-[#0F172A] px-3 py-2 text-sm text-white outline-none focus:border-blue-500">
              <option>Gemini 2.5 Flash</option>
              <option>GPT-4o</option>
              <option>Claude 3.5 Sonnet</option>
            </select>
          </div>
          <label className="flex items-center justify-between rounded-xl border border-[#334155] bg-[#0F172A] px-4 py-3 cursor-pointer">
            <span className="text-sm text-slate-300">Auto-approve low-risk recommendations</span>
            <input type="checkbox" className="h-4 w-4 rounded accent-blue-600" />
          </label>
          <label className="flex items-center justify-between rounded-xl border border-[#334155] bg-[#0F172A] px-4 py-3 cursor-pointer">
            <span className="text-sm text-slate-300">Enable semantic memory updates</span>
            <input type="checkbox" defaultChecked className="h-4 w-4 rounded accent-blue-600" />
          </label>
        </div>
      </section>

      <section className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg">
        <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
          <Bell size={16} className="text-amber-400" />
          Notifications
        </h2>
        <div className="space-y-3">
          {[
            "Churn risk alerts",
            "New AI recommendations",
            "Knowledge base sync complete",
            "Agent workflow failures",
          ].map((label) => (
            <label
              key={label}
              className="flex items-center justify-between rounded-xl border border-[#334155] bg-[#0F172A] px-4 py-3 cursor-pointer"
            >
              <span className="text-sm text-slate-300">{label}</span>
              <input type="checkbox" defaultChecked className="h-4 w-4 rounded accent-blue-600" />
            </label>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-xs text-emerald-400">
        <Shield size={14} />
        Your data is encrypted at rest and in transit. SOC 2 Type II compliant.
      </div>
    </motion.div>
  );
}

export default DecisionCenter;
