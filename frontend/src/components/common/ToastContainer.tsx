import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from "lucide-react";

import { useDashboard } from "../../context/DashboardContext";

const iconMap = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const colorMap = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  error: "border-rose-500/30 bg-rose-500/10 text-rose-400",
  info: "border-blue-500/30 bg-blue-500/10 text-blue-400",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-400",
};

function ToastContainer() {
  const { toasts, dismissToast } = useDashboard();

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => {
          const Icon = iconMap[toast.type];
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              className={`pointer-events-auto flex items-center gap-3 rounded-xl border px-4 py-3 shadow-2xl backdrop-blur-md ${colorMap[toast.type]}`}
            >
              <Icon size={18} className="shrink-0" />
              <span className="text-sm font-medium text-white">{toast.message}</span>
              <button
                onClick={() => dismissToast(toast.id)}
                className="ml-2 rounded-lg p-0.5 text-slate-400 hover:text-white transition"
                aria-label="Dismiss"
              >
                <X size={14} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

export default ToastContainer;
