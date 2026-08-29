import { MessageSquare, Plus, Trash2, Sparkles, Clock } from "lucide-react";
import type { ChatSessionItem } from "../../lib/api/assistant";
import { cn } from "../../lib/utils";
import { motion } from "framer-motion";

interface SessionSidebarProps {
  sessions: ChatSessionItem[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: SessionSidebarProps) {
  return (
    <div className="flex h-full w-64 flex-col border-r border-slate-800/80 bg-slate-950/70 backdrop-blur-xl p-3 shadow-xl">
      <button
        onClick={onNewSession}
        className="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-cyan-500 via-teal-500 to-emerald-500 py-2.5 text-xs font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition-all duration-200 hover:scale-[1.02] hover:shadow-cyan-500/40 active:scale-[0.98]"
      >
        <span className="absolute inset-0 bg-white/20 opacity-0 transition-opacity group-hover:opacity-100" />
        <Plus className="size-4 shrink-0 transition-transform group-hover:rotate-90" />
        <span className="uppercase tracking-wider">New Conversation</span>
        <Sparkles className="size-3.5 text-slate-900/80 animate-pulse" />
      </button>

      <div className="mt-4 flex-1 space-y-1 overflow-y-auto pr-1" style={{ scrollbarWidth: "thin" }}>
        <div className="flex items-center justify-between px-2 pb-2 text-[10px] font-bold uppercase tracking-wider text-cyan-400/80">
          <span className="flex items-center gap-1.5">
            <Clock className="size-3" />
            <span>Chat Sessions</span>
          </span>
          <span className="rounded-full bg-cyan-950 px-1.5 py-0.5 text-[9px] font-mono border border-cyan-500/30 text-cyan-300">
            {sessions.length}
          </span>
        </div>

        {sessions.length === 0 ? (
          <div className="px-2 py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800/80 rounded-xl">
            No previous chats yet
          </div>
        ) : (
          sessions.map((session, idx) => {
            const isActive = session.id === activeSessionId;
            return (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.03 }}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "group relative flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 text-xs transition-all duration-150 border",
                  isActive
                    ? "border-cyan-500/40 bg-gradient-to-r from-cyan-950/80 via-slate-900 to-slate-900 text-cyan-200 font-semibold shadow-md shadow-cyan-950/40"
                    : "border-transparent text-slate-400 hover:border-slate-800 hover:bg-slate-900/50 hover:text-slate-200"
                )}
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <div className="relative shrink-0">
                    <MessageSquare className={cn("size-3.5", isActive ? "text-cyan-400" : "text-slate-500 group-hover:text-slate-300")} />
                    {isActive && <span className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-cyan-400 animate-ping" />}
                  </div>
                  <span className="truncate">{session.title}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="opacity-0 transition-all hover:scale-110 hover:text-rose-400 group-hover:opacity-100"
                  title="Delete chat"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
