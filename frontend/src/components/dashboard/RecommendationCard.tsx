import { useEffect, useState } from "react";
import {
  Check,
  X,
  Edit3,
  ShieldCheck,
  AlertCircle,
  Sparkles,
  CheckCircle2,
} from "lucide-react";

import type { RecommendationStatus } from "../../types/dashboard";
import { useDashboard } from "../../context/DashboardContext";

interface RecommendationCardProps {
  status?: RecommendationStatus;
  onAction?: (
    action: "approve" | "reject" | "modify" | "save_modification",
    modifiedText?: string
  ) => void;
}

function RecommendationCard({ status: statusProp, onAction: onActionProp }: RecommendationCardProps) {
  const ctx = useDashboard();
  const status = statusProp ?? ctx.recommendationStatus;
  const onAction = onActionProp ?? ctx.handleRecommendationAction;
  const recommendationData = ctx.activeRecommendation;

  const [isEditing, setIsEditing] = useState(false);
  const [modifiedText, setModifiedText] = useState(recommendationData.action);

  useEffect(() => {
    setModifiedText(recommendationData.action);
  }, [recommendationData.action]);

  const handleSave = () => {
    setIsEditing(false);
    onAction("save_modification", modifiedText);
  };

  const evidenceIcons = {
    success: CheckCircle2,
    warning: AlertCircle,
    info: Sparkles,
  };

  const evidenceColors = {
    success: "text-emerald-400",
    warning: "text-amber-400",
    info: "text-blue-400",
  };

  return (
    <div className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg flex flex-col justify-between h-full">
      <div>
        <div className="flex items-center justify-between border-b border-[#334155] pb-4 mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles size={18} className="text-violet-400" />
            AI Recommendation
          </h2>
          <div className="flex gap-2">
            <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-0.5 text-xs text-rose-400 font-extrabold">
              HIGH PRIORITY
            </span>
            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs text-emerald-400 font-bold">
              {recommendationData.confidence}% CONFIDENCE
            </span>
          </div>
        </div>

        <div className="mb-4 rounded-xl bg-[#0F172A] border border-[#334155]/50 p-3">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
            Customer
          </span>
          <p className="text-sm font-semibold text-white mt-0.5">
            {recommendationData.customer}
          </p>
        </div>

        <div className="mb-4">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
            Evidence
          </span>
          <div className="mt-2 space-y-2">
            {recommendationData.evidence.map((e, idx) => {
              const Icon = evidenceIcons[e.type];
              return (
                <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                   <Icon size={14} className={`mt-0.5 shrink-0 ${evidenceColors[e.type]}`} />
                  <span>{e.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl bg-[#0F172A] p-4 border border-[#334155]/60 mb-3 text-left">
          <span className="text-[9px] font-bold text-blue-400 uppercase tracking-wider">
            Recommended Action
          </span>
          {isEditing ? (
            <div className="mt-2">
              <input
                type="text"
                value={modifiedText}
                onChange={(e) => setModifiedText(e.target.value)}
                className="w-full bg-[#1E293B] border border-[#334155] rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
                placeholder="Enter custom recommendation..."
              />
              <div className="mt-2 flex justify-end gap-1.5">
                <button
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg bg-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="rounded-lg bg-blue-600 px-2.5 py-1 text-[10px] font-semibold text-white hover:bg-blue-700 transition"
                >
                  Save
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-1">
              <h3 className="text-base font-extrabold text-white">
                {status === "modified" ? modifiedText : recommendationData.action}
              </h3>
              <p className="text-[11px] text-slate-400 mt-2">
                <span className="font-semibold text-slate-300">Reason: </span>
                {recommendationData.reason}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                Expected Impact:{" "}
                <span className="text-emerald-400 font-semibold">
                  {recommendationData.expectedImpact}
                </span>
              </p>
            </div>
          )}
        </div>
      </div>


      <div>
        {status === "approved" ? (
          <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-emerald-400 text-xs font-semibold">
            <ShieldCheck size={18} className="shrink-0" />
            <span>Approved! Task synced to Salesforce and Outlook calendar.</span>
          </div>
        ) : status === "rejected" ? (
          <div className="flex items-center gap-2 rounded-xl bg-rose-500/10 border border-rose-500/20 p-3 text-rose-400 text-xs font-semibold">
            <AlertCircle size={18} className="shrink-0" />
            <span>Rejected. AI routing model weights adjusted for future decisions.</span>
          </div>
        ) : status === "modified" ? (
          <div className="flex items-center gap-2 rounded-xl bg-blue-500/10 border border-blue-500/20 p-3 text-blue-400 text-xs font-semibold mb-2">
            <Edit3 size={18} className="shrink-0" />
            <span>Modified recommendation saved. Awaiting final approval.</span>
          </div>
        ) : null}

        {status === "pending" || status === "modified" ? (
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => onAction("reject")}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/5 py-2.5 text-xs font-bold text-rose-400 hover:bg-rose-500/10 transition cursor-pointer"
            >
              <X size={14} />
              Reject
            </button>
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-[#334155] bg-slate-800 py-2.5 text-xs font-bold text-slate-300 hover:bg-slate-700 transition cursor-pointer"
            >
              <Edit3 size={14} />
              Modify
            </button>
            <button
              onClick={() => onAction("approve")}
              className="flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 py-2.5 text-xs font-bold text-white hover:bg-blue-700 transition shadow-md shadow-blue-500/15 cursor-pointer"
            >
              <Check size={14} />
              Approve
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default RecommendationCard;
