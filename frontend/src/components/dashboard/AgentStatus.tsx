import { CheckCircle2, Loader, Circle } from "lucide-react";

import { AGENT_NODES } from "../../data/mockDashboard";
import { useDashboard } from "../../context/DashboardContext";
import type { AgentState } from "../../types/dashboard";

function getAgentState(stepIndex: number, activeStep: number): AgentState {
  if (activeStep > stepIndex) return "completed";
  if (activeStep === stepIndex) return "running";
  return "waiting";
}

function AgentStatus() {
  const { activeStep, isAnalyzing } = useDashboard();

  const completedCount = activeStep === 0 ? 0 : Math.min(activeStep, AGENT_NODES.length);
  const runningAgent =
    activeStep > 0 && activeStep <= AGENT_NODES.length
      ? AGENT_NODES[activeStep - 1]
      : null;

  return (
    <div className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-5 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#334155] pb-4 mb-4">
        <div>
          <h2 className="text-sm font-bold text-white">Agent Fleet Status</h2>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {completedCount}/{AGENT_NODES.length} agents completed
            {runningAgent && isAnalyzing && (
              <span className="text-blue-400">
                {" "}
                · {runningAgent.name} running
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1 text-emerald-400">
            <CheckCircle2 size={10} /> Completed
          </span>
          <span className="flex items-center gap-1 text-blue-400">
            <Loader size={10} className={isAnalyzing ? "animate-spin" : ""} /> Running
          </span>
          <span className="flex items-center gap-1 text-slate-500">
            <Circle size={10} /> Waiting
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-11 gap-2">
        {AGENT_NODES.map((agent, index) => {
          const stepIndex = index + 1;
          const state = getAgentState(stepIndex, activeStep);

          return (
            <div
              key={agent.id}
              className={`rounded-xl border p-2.5 text-center transition-all ${
                state === "running"
                  ? "border-blue-500/40 bg-blue-500/5 shadow-md shadow-blue-500/10"
                  : state === "completed"
                  ? "border-emerald-500/20 bg-emerald-500/5"
                  : "border-[#334155] bg-[#0F172A] opacity-50"
              }`}
            >
              <div className="flex justify-center mb-1.5">
                {state === "completed" ? (
                  <CheckCircle2 size={14} className="text-emerald-400" />
                ) : state === "running" ? (
                  <Loader size={14} className="text-blue-400 animate-spin" />
                ) : (
                  <Circle size={14} className="text-slate-600" />
                )}
              </div>
              <p className="text-[9px] font-semibold text-white leading-tight truncate">
                {agent.name.replace(" Agent", "")}
              </p>
              <p
                className={`text-[8px] mt-0.5 font-bold uppercase ${
                  state === "running"
                    ? "text-blue-400"
                    : state === "completed"
                    ? "text-emerald-400"
                    : "text-slate-500"
                }`}
              >
                {state}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AgentStatus;
