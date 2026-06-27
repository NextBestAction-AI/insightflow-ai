import { useState } from "react";
import {
  LayoutDashboard,
  Users,
  Bot,
  BookOpen,
  ClipboardCheck,
  History as HistoryIcon,
  Settings,
  Sun,
  Moon,
  X,
  Compass,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { CURRENT_USER } from "../../data/mockDashboard";

const menu = [
  { title: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { title: "Customers", path: "/customers", icon: Users },
  { title: "AI Agents", path: "/analysis", icon: Bot },
  { title: "Knowledge Base", path: "/knowledge", icon: BookOpen },
  { title: "Recommendations", path: "/recommendation", icon: ClipboardCheck },
  { title: "History", path: "/history", icon: HistoryIcon },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const [isDarkMode, setIsDarkMode] = useState(true);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-[#334155] bg-[#0F172A] transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
        isOpen ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div className="flex h-16 items-center justify-between border-b border-[#334155] px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-violet-600 shadow-md shadow-blue-500/20">
            <Compass className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            InsightFlow <span className="text-blue-500">AI</span>
          </span>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-1 hover:bg-[#1E293B] text-slate-400 hover:text-white transition lg:hidden"
            aria-label="Close sidebar"
          >
            <X size={20} />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1.5 p-4 overflow-y-auto">
        <div className="px-3 mb-2 text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
          Customer Success
        </div>
        {menu.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-gradient-to-r from-blue-600 to-blue-600/80 text-white shadow-md shadow-blue-500/10"
                    : "text-slate-400 hover:bg-[#1E293B] hover:text-slate-200 hover:translate-x-0.5"
                }`
              }
            >
              <Icon size={18} className="transition-transform group-hover:scale-110" />
              {item.title}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-[#334155] p-4 bg-[#0B0F19]">
        <div className="flex items-center justify-between mb-4 px-2">
          <div className="flex items-center gap-1 rounded-full bg-[#1E293B] p-1">
            <button
              onClick={() => setIsDarkMode(false)}
              className={`rounded-full p-1 text-slate-400 hover:text-white transition-colors ${
                !isDarkMode ? "bg-blue-600 text-white" : ""
              }`}
              title="Light Mode"
            >
              <Sun size={14} />
            </button>
            <button
              onClick={() => setIsDarkMode(true)}
              className={`rounded-full p-1 text-slate-400 hover:text-white transition-colors ${
                isDarkMode ? "bg-blue-600 text-white" : ""
              }`}
              title="Dark Mode"
            >
              <Moon size={14} />
            </button>
          </div>

          <NavLink
            to="/settings"
            onClick={onClose}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Settings size={15} />
            <span>Settings</span>
          </NavLink>
        </div>

        <div className="flex items-center gap-3 rounded-xl bg-[#1E293B]/50 border border-[#334155]/50 p-3 mb-3">
          <img
            src={CURRENT_USER.avatar}
            alt={CURRENT_USER.name}
            className="h-9 w-9 rounded-full border border-blue-500/30 object-cover"
          />
          <div className="flex-1 overflow-hidden">
            <h4 className="text-xs font-semibold text-white truncate">{CURRENT_USER.name}</h4>
            <p className="text-[10px] text-slate-400 truncate">{CURRENT_USER.role}</p>
          </div>
          <div className="h-2 w-2 rounded-full bg-emerald-500" />
        </div>

        <div className="flex items-center justify-between px-2 text-[10px] text-slate-500 font-mono">
          <span>InsightFlow Platform</span>
          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
