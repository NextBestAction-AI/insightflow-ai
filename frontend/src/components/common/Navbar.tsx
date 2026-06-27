import { useState } from "react";
import { Bell, Search, Menu, Activity, Compass } from "lucide-react";

import { CURRENT_USER } from "../../data/mockDashboard";

interface NavbarProps {
  onMenuToggle?: () => void;
}

function Navbar({ onMenuToggle }: NavbarProps) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState([
    {
      id: 1,
      text: "Churn risk detected for Acme Corporation",
      time: "2 min ago",
      unread: true,
    },
    {
      id: 2,
      text: "New recommendation: Schedule Executive Business Review",
      time: "15 min ago",
      unread: true,
    },
    {
      id: 3,
      text: "Knowledge base synced — 1,247 documents indexed",
      time: "1 hour ago",
      unread: false,
    },
  ]);

  const markAllRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, unread: false })));
  };

  const unreadCount = notifications.filter((n) => n.unread).length;

  return (
    <header className="relative flex h-16 items-center justify-between border-b border-[#334155] bg-[#0F172A] px-4 md:px-6 z-30">
      {/* Left: Hamburger + Brand */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          className="rounded-lg p-1.5 hover:bg-[#1E293B] text-slate-400 hover:text-white transition lg:hidden shrink-0"
          aria-label="Toggle menu"
        >
          <Menu size={22} />
        </button>

        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-blue-600 to-violet-600 lg:hidden">
            <Compass className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm font-bold text-white lg:hidden">
            InsightFlow <span className="text-blue-500">AI</span>
          </span>
        </div>
      </div>

      {/* Center: Search */}
      <div className="absolute left-1/2 -translate-x-1/2 hidden md:flex items-center rounded-xl border border-[#334155] bg-[#1E293B] px-3 py-1.5 text-slate-400 focus-within:border-blue-500 focus-within:text-white transition-all w-64 lg:w-80">
        <Search size={16} className="mr-2 shrink-0" />
        <input
          type="text"
          placeholder="Search customers..."
          className="w-full bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
        />
        <div className="flex items-center gap-0.5 rounded border border-slate-600 bg-slate-800 px-1.5 text-[10px] font-mono text-slate-400 shrink-0">
          <span>⌘</span>
          <span>K</span>
        </div>
      </div>

      {/* Right: AI Status + Notifications + Profile */}
      <div className="flex items-center gap-3 md:gap-4">
        <div className="hidden lg:flex items-center gap-2.5 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1 text-xs text-emerald-400 font-medium">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span>AI Connected</span>
          <span className="h-3 w-px bg-emerald-500/20" />
          <span className="text-slate-400">Gemini 2.5 Flash</span>
          <span className="h-3 w-px bg-emerald-500/20" />
          <span className="text-slate-400 flex items-center gap-1">
            <Activity size={10} /> Latency 0.6s
          </span>
        </div>

        <div className="lg:hidden flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400 font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Connected</span>
        </div>

        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative rounded-xl p-2 text-slate-400 hover:bg-[#1E293B] hover:text-white transition"
          >
            <Bell size={20} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-[#334155] bg-[#1E293B] p-4 shadow-2xl z-50">
              <div className="flex items-center justify-between border-b border-[#334155] pb-3 mb-2">
                <h3 className="font-semibold text-sm text-white">Notifications</h3>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-xs text-blue-400 hover:text-blue-300 font-medium"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`p-2.5 rounded-xl text-xs transition-colors ${
                      n.unread
                        ? "bg-blue-600/10 border-l-2 border-blue-500"
                        : "bg-slate-900/50"
                    }`}
                  >
                    <p
                      className={`font-medium ${n.unread ? "text-white" : "text-slate-300"}`}
                    >
                      {n.text}
                    </p>
                    <span className="text-[10px] text-slate-500 mt-1 block">{n.time}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 border-l border-[#334155] pl-3 md:pl-4">
          <img
            src={CURRENT_USER.avatar}
            alt={CURRENT_USER.name}
            className="h-8 w-8 rounded-full border border-blue-500/50 object-cover"
          />
          <div className="hidden lg:block text-left">
            <p className="text-xs font-semibold text-white">{CURRENT_USER.name}</p>
            <p className="text-[10px] text-slate-400">{CURRENT_USER.role}</p>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Navbar;
