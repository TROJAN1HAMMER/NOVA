import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { ChatSessionItem } from "../../lib/api/assistant";
import { cn } from "../../lib/utils";

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
    <div className="flex h-full w-64 flex-col border-r border-border bg-card p-3">
      <button
        onClick={onNewSession}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
      >
        <Plus className="size-4" />
        New Conversation
      </button>

      <div className="mt-4 flex-1 space-y-1 overflow-y-auto">
        <div className="px-2 pb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Past Conversations
        </div>

        {sessions.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            No previous chats yet
          </div>
        ) : (
          sessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "group relative flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{session.title}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  title="Delete chat"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
