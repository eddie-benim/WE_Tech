"use client";

import { useState } from "react";
import { useChat } from "ai/react";
import { FileText, Search, FolderOpen, Library, Upload, MessageSquarePlus } from "lucide-react";

// --- Presets: this is the "side ribbon" the person asked for -- clickable
// shortcuts to specific structured flows, for when someone doesn't know
// exactly what to ask and just wants to see what's available. Each one either
// pre-fills the chat input with a starting prompt, or (for Browse Library)
// opens a dedicated panel instead of going through chat at all.
const PRESETS = [
  { icon: FolderOpen, label: "Organize a new file", prompt: "I'd like to upload and classify a new engineering file." },
  { icon: FileText, label: "Generate a report", prompt: "Help me generate a report for a new project." },
  { icon: Search, label: "Search reference library", prompt: "Search my reference library for related P&IDs." },
  { icon: Library, label: "Browse indexed files", prompt: null }, // opens a panel, not chat
];

export default function Home() {
  const { messages, input, handleInputChange, handleSubmit, setInput } = useChat({
    api: "/api/chat",
  });
  const [conversations] = useState([
    { id: 1, title: "Gas Seal System Diagram" },
    { id: 2, title: "Q3 Heat Balance Report" },
  ]);

  return (
    <div className="flex h-screen bg-neutral-50 text-neutral-900">
      {/* ---------------- Sidebar ---------------- */}
      <aside className="w-72 border-r border-neutral-200 bg-white flex flex-col">
        <div className="p-3">
          <button className="w-full flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-2 text-sm font-medium hover:bg-neutral-50">
            <MessageSquarePlus size={16} />
            New chat
          </button>
        </div>

        <div className="px-3 pb-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-400 px-1 mb-2">
            Quick actions
          </div>
          <div className="flex flex-col gap-1">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => p.prompt && setInput(p.prompt)}
                className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-left hover:bg-neutral-100"
              >
                <p.icon size={16} className="text-neutral-500" />
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pt-4 border-t border-neutral-100">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-400 px-1 mb-2">
            Recent
          </div>
          {conversations.map((c) => (
            <button
              key={c.id}
              className="w-full text-left rounded-lg px-2 py-2 text-sm hover:bg-neutral-100 truncate"
            >
              {c.title}
            </button>
          ))}
        </div>
      </aside>

      {/* ---------------- Main chat panel ---------------- */}
      <main className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-2xl mx-auto flex flex-col gap-6">
            {messages.length === 0 && (
              <div className="text-center text-neutral-400 mt-20">
                Ask a question, or pick a quick action from the sidebar.
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`rounded-xl px-4 py-3 max-w-[85%] ${
                  m.role === "user"
                    ? "bg-neutral-900 text-white self-end ml-auto"
                    : "bg-white border border-neutral-200 self-start"
                }`}
              >
                {m.content}
              </div>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="border-t border-neutral-200 bg-white p-4">
          <div className="max-w-2xl mx-auto flex items-center gap-2 rounded-xl border border-neutral-300 px-3 py-2">
            <button type="button" className="text-neutral-400 hover:text-neutral-600">
              <Upload size={18} />
            </button>
            <input
              value={input}
              onChange={handleInputChange}
              placeholder="Message the assistant..."
              className="flex-1 outline-none text-sm py-1"
            />
          </div>
        </form>
      </main>

      {/* ---------------- Artifact panel (structured output) ----------------
          When a file gets analyzed, render the extracted valve/instrument/pipe-spec
          data HERE as tables/cards -- not dumped as text into a chat bubble. This is
          the piece that actually showcases what the extractor produces. Wire it to
          show up whenever the last assistant message includes structured results. */}
    </div>
  );
}
