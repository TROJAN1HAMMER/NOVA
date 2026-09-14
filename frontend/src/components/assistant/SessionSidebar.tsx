import { MessageSquare, Plus, Trash2, Clock } from "lucide-react";
import type { ChatSessionItem } from "../../lib/api/assistant";
import { cn } from "../../lib/utils";
import { motion } from "framer-motion";
import { Button } from "../ui/Button";

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
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-border/80 bg-card/35 backdrop-blur-md p-3">
      <Button
        variant="primary"
        size="sm"
        onClick={onNewSession}
        className="w-full gap-2 text-xs font-semibold uppercase tracking-wider py-2 shadow-xs"
      >
        <Plus className="size-4 shrink-0" />
        <span>New Conversation</span>
      </Button>

      <div className="mt-4 flex-1 space-y-1 overflow-y-auto pr-1" style={{ scrollbarWidth: "thin" }}>
        <div className="flex items-center justify-between px-2 pb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock className="size-3" />
            <span>Chat Sessions</span>
          </span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-mono border border-primary/25 text-primary font-semibold">
            {sessions.length}
          </span>
        </div>

        {sessions.length === 0 ? (
          <div className="px-2 py-8 text-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-xl">
            No previous chats yet
          </div>
        ) : (
          sessions.map((session, idx) => {
            const isActive = session.id === activeSessionId;
            return (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.02 }}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "group relative flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-xs transition-colors border",
                  isActive
                    ? "border-primary/40 bg-primary/10 text-primary font-semibold shadow-xs"
                    : "border-transparent text-muted-foreground hover:border-border hover:bg-muted/50 hover:text-foreground"
                )}
              >
                <div className="flex items-center gap-2.5 overflow-hidden min-w-0">
                  <div className="relative shrink-0">
                    <MessageSquare className={cn("size-3.5", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
                  </div>
                  <span className="truncate">{session.title}</span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="opacity-0 transition-opacity hover:text-danger text-muted-foreground group-hover:opacity-100 p-0.5 rounded ml-1 shrink-0"
                  title="Delete chat"
                  aria-label="Delete chat"
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
