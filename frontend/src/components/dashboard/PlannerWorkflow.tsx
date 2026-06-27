import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Loader,
  Play,
  RotateCcw,
} from "lucide-react";

import { AGENT_NODES } from "../../data/mockDashboard";
import { useDashboard } from "../../context/DashboardContext";

interface PlannerWorkflowProps {
  activeStep?: number;
  isAnalyzing?: boolean;
  onReset?: () => void;
  onStartAnalysis?: (fileName: string) => void;
}

function PlannerWorkflow({
  activeStep: activeStepProp,
  isAnalyzing: isAnalyzingProp,
  onReset: onResetProp,
  onStartAnalysis: onStartAnalysisProp,
}: PlannerWorkflowProps) {
  const ctx = useDashboard();
  const activeStep = activeStepProp ?? ctx.activeStep;
  const isAnalyzing = isAnalyzingProp ?? ctx.isAnalyzing;
  const onReset = onResetProp ?? ctx.resetWorkflow;
  const onStartAnalysis = onStartAnalysisProp ?? ctx.startAnalysis;

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "Console ready. Upload an interaction to initialize.",
  ]);

  useEffect(() => {
    if (activeStep === 0) {
      const timer = setTimeout(() => {
        setTerminalLogs(["Console ready. Upload an interaction to initialize."]);
      }, 0);
      return () => clearTimeout(timer);
    }

    if (activeStep > 0 && activeStep <= AGENT_NODES.length) {
      const activeNode = AGENT_NODES[activeStep - 1];
      const timeString = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      const timer = setTimeout(() => {
        setTerminalLogs((prev) => [
          ...prev,
          `[${timeString}] [${activeNode.name.toUpperCase()}] ${activeNode.log}`,
        ]);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [activeStep]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [terminalLogs]);

  const runningAgent =
    activeStep > 0 && activeStep <= AGENT_NODES.length
      ? AGENT_NODES[activeStep - 1]
      : null;

  return (
    <div className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-5 shadow-lg flex flex-col h-full">
      <div className="flex flex-wrap items-center justify-between border-b border-[#334155] pb-4 mb-4 gap-3">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 ${
                  isAnalyzing ? "animate-ping" : ""
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isAnalyzing ? "bg-blue-500" : "bg-slate-500"
                }`}
              />
            </span>
            Live Planner Workflow
          </h2>
          <p className="text-[11px] text-slate-400">
            {isAnalyzing && runningAgent
              ? `Step ${activeStep}/11 — ${runningAgent.activity}`
              : "Multi-Agent Orchestration Pipeline"}
          </p>
        </div>

        <div className="flex gap-2">
          {isAnalyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-blue-600/10 px-2.5 py-1 text-[10px] text-blue-400 font-semibold border border-blue-500/20">
              <Loader size={12} className="animate-spin" />
              <span>Step {activeStep}/11</span>
            </div>
          ) : (
            <>
              {activeStep > 0 && (
                <button
                  onClick={onReset}
                  className="flex items-center gap-1 rounded-lg bg-slate-800 border border-[#334155] px-2.5 py-1 text-[10px] text-slate-400 font-semibold hover:bg-slate-700 hover:text-white transition"
                  title="Reset Simulation"
                >
                  <RotateCcw size={12} />
                  <span>Reset</span>
                </button>
              )}
              <button
                onClick={() => onStartAnalysis("meeting_transcript.pdf")}
                className="flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1 text-[10px] text-white font-semibold hover:bg-blue-700 transition"
              >
                <Play size={12} />
                <span>Simulate</span>
              </button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5 flex-1 min-h-[420px] overflow-hidden">
        <div className="lg:col-span-3 overflow-y-auto max-h-[480px] pr-2 scrollbar-thin">
          <div className="relative pl-6 space-y-3.5">
            <div className="absolute left-3.5 top-3.5 bottom-3.5 w-[2px] bg-slate-700" />

            <div
              className="absolute left-3.5 top-3.5 w-[2px] bg-blue-500 transition-all duration-500"
              style={{
                height: `${
                  activeStep === 0
                    ? 0
                    : activeStep >= AGENT_NODES.length
                    ? 100
                    : ((activeStep - 0.5) / AGENT_NODES.length) * 100
                }%`,
              }}
            />

            {AGENT_NODES.map((node, index) => {
              const stepIndex = index + 1;
              const isCompleted = activeStep > stepIndex;
              const isRunning = activeStep === stepIndex;
              const isWaiting = activeStep < stepIndex;

              return (
                <div
                  key={node.id}
                  className={`relative flex items-center gap-3 transition-opacity duration-300 ${
                    isWaiting ? "opacity-40" : "opacity-100"
                  }`}
                >
                  <div className="absolute -left-5 z-10 flex h-6 w-6 items-center justify-center">
                    {isCompleted ? (
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white shadow-md shadow-emerald-500/20">
                        <CheckCircle2 size={12} />
                      </div>
                    ) : isRunning ? (
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-500/50 animate-pulse">
                        <Loader size={10} className="animate-spin" />
                      </div>
                    ) : (
                      <div className="h-3 w-3 rounded-full bg-slate-700 border border-slate-600" />
                    )}
                  </div>

                  <div
                    className={`flex flex-1 flex-col rounded-xl border p-2.5 transition-all ${
                      isRunning
                        ? "border-blue-500/40 bg-blue-500/5 shadow-md shadow-blue-500/5"
                        : "border-[#334155] bg-[#0F172A]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-white">{node.name}</h4>
                      {isCompleted && (
                        <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[8px] text-emerald-400 font-bold">
                          ✓ Done
                        </span>
                      )}
                      {isRunning && (
                        <span className="rounded-full bg-blue-500/15 px-1.5 py-0.5 text-[8px] text-blue-400 font-extrabold animate-pulse">
                          Running
                        </span>
                      )}
                      {isWaiting && (
                        <span className="text-[8px] text-slate-500 font-semibold">Waiting</span>
                      )}
                    </div>
                    <p className="text-[9px] text-slate-500 mt-0.5">{node.role}</p>
                    {isRunning && (
                      <p className="text-[10px] text-blue-300 mt-1 font-medium">
                        {node.activity}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-2 flex flex-col h-full bg-black/40 rounded-2xl border border-[#334155] p-3 overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#334155]/60 pb-2 mb-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
              Agent Terminal Logs
            </span>
            <span className="flex h-2 w-2 rounded-full bg-red-500 animate-pulse" />
          </div>

          <div className="flex-1 overflow-y-auto font-mono text-[10px] text-slate-300 space-y-1.5 leading-relaxed p-1 text-left scrollbar-thin">
            {terminalLogs.map((log, index) => (
              <div
                key={index}
                className={
                  log.includes("CRITICAL")
                    ? "text-rose-400 bg-rose-500/5 p-1 rounded"
                    : log.includes("Complete") || log.includes("calculated")
                    ? "text-emerald-400"
                    : log.includes("Ready") || log.includes("initialize")
                    ? "text-slate-500"
                    : "text-blue-300"
                }
              >
                {log}
              </div>
            ))}
            <div ref={terminalEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlannerWorkflow;
export { PlannerWorkflow as PlannerStatus };
