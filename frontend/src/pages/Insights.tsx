import { motion } from "framer-motion";
import { BookOpen, Database, FileText, Search, RefreshCw } from "lucide-react";

import { KNOWLEDGE_DOCUMENTS } from "../data/mockDashboard";

const categories = ["All", "Contracts", "Playbooks", "Frameworks", "Product Docs", "Support", "Templates"];

function Insights() {
  const totalChunks = KNOWLEDGE_DOCUMENTS.reduce((sum, doc) => sum + doc.chunks, 0);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 max-w-7xl mx-auto"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white">Knowledge Base</h1>
          <p className="mt-1 text-sm text-slate-400">
            Vector-indexed documents powering AI agent retrieval and recommendations.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-400 font-medium">
          <RefreshCw size={14} />
          Last synced 2 hours ago
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <BookOpen size={14} />
            Documents
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{KNOWLEDGE_DOCUMENTS.length}</p>
        </div>
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <Database size={14} />
            Vector Chunks
          </div>
          <p className="mt-2 text-2xl font-bold text-violet-400">{totalChunks.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-[#334155] bg-[#1E293B] p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
            <FileText size={14} />
            Categories
          </div>
          <p className="mt-2 text-2xl font-bold text-blue-400">{categories.length - 1}</p>
        </div>
      </div>

      <div className="flex items-center rounded-xl border border-[#334155] bg-[#1E293B] px-4 py-2.5 text-slate-400 w-full max-w-md">
        <Search size={16} className="mr-2 shrink-0" />
        <input
          type="text"
          placeholder="Search knowledge base..."
          className="w-full bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              cat === "All"
                ? "bg-blue-600 text-white"
                : "border border-[#334155] bg-[#1E293B] text-slate-400 hover:text-white hover:border-slate-500"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {KNOWLEDGE_DOCUMENTS.map((doc) => (
          <div
            key={doc.id}
            className="rounded-2xl border border-[#334155] bg-[#1E293B] p-5 hover:border-blue-500/30 transition-colors cursor-pointer"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-violet-500/10 p-2.5">
                  <FileText size={18} className="text-violet-400" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">{doc.title}</h3>
                  <p className="text-[11px] text-slate-500 mt-1">{doc.category}</p>
                </div>
              </div>
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400 font-mono shrink-0">
                {doc.chunks} chunks
              </span>
            </div>
            <p className="mt-3 text-[10px] text-slate-500">Synced {doc.lastSynced}</p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default Insights;
