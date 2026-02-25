import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  chatSocketService,
  type QueryErrorPayload,
  type QueryStartedPayload,
  type ResponseChunkPayload,
  type SocketState,
} from "../services/chatSocketService";

type Role = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  isStreaming?: boolean;
};

const starterChats = [
  { title: "Financial Data Analysis Q1", date: "2 hours ago", active: true },
  { title: "User Feedback Synthesis", date: "Yesterday", active: false },
  { title: "Workflow Validation Rules", date: "Feb 24, 2024", active: false },
];

export function ChatPage() {
  const [socketState, setSocketState] = useState<SocketState>("connecting");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I'm the zValuate Assistant. How can I help you manage your datasets or workflows today?",
    },
  ]);
  const [thinkingText, setThinkingText] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const connectedLabel = useMemo(() => {
    if (socketState === "connected") return "Connected";
    if (socketState === "error") return "Connection issue";
    return "Connecting";
  }, [socketState]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinkingText]);

  useEffect(() => {
    chatSocketService.connect({
      onConnect: () => setSocketState("connected"),
      onDisconnect: () => setSocketState("connecting"),
      onConnectError: () => setSocketState("error"),
      onQueryStarted: (data: QueryStartedPayload) => {
        setMessages((prev) => [...prev, { id: data.message_id, role: "assistant", content: "", isStreaming: true }]);
      },
      onThinking: (data) => {
        setThinkingText(data.status ?? "Analyzing dataset records...");
      },
      onResponseChunk: (data: ResponseChunkPayload) => {
        setThinkingText("");
        setMessages((prev) =>
          prev.map((message) =>
            message.id === data.message_id
              ? { ...message, content: message.content + data.content, isStreaming: true }
              : message
          )
        );
      },
      onQueryComplete: (data) => {
        setThinkingText("");
        setMessages((prev) =>
          prev.map((message) =>
            message.id === data.message_id ? { ...message, content: data.response, isStreaming: false } : message
          )
        );
      },
      onQueryError: (data: QueryErrorPayload) => {
        setThinkingText("");
        if (data.message_id) {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === data.message_id
                ? { ...message, content: `Error: ${data.message}`, isStreaming: false }
                : message
            )
          );
          return;
        }

        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Error: ${data.message}`,
          },
        ]);
      },
    });

    return () => chatSocketService.disconnect();
  }, []);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    chatSocketService.sendMessage(trimmed);
    setInput("");
  };

  return (
    <div className="min-h-screen bg-[#f6f7fb] text-[#1f2a44]">
      <header className="flex h-16 items-center justify-between border-b border-[#e4e7f0] bg-white px-4 md:px-8">
        <div className="flex items-center gap-3 text-[38px] font-semibold">
          <span className="text-[#1f3f93]">&#9651;</span>
          <span className="text-3xl font-extrabold tracking-tight">zValuate</span>
        </div>
        <div className="flex items-center gap-5 text-sm text-[#6a7289]">
          <div className="hidden items-center gap-1 md:flex">
            <span>user org</span>
            <span className="text-xs">▼</span>
          </div>
          <div className="h-8 w-px bg-[#e5e7ef]" />
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2ac88f] font-bold text-white">
              TA
            </span>
            <span className="hidden md:block">Test Argus</span>
          </div>
        </div>
      </header>

      <main className="flex h-[calc(100vh-4rem)]">
        <aside className="hidden w-24 flex-col bg-[#17398d] py-6 text-white md:flex">
          <SidebarItem label="Dataset" active={false} />
          <SidebarItem label="Workflow" active={false} />
          <SidebarItem label="AI Assistant" active />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-[#e4e7f0] bg-white px-5 py-5 md:px-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="text-4xl font-extrabold tracking-tight text-[#17233d]">AI Chat Assistant</h1>
                <p className="mt-1 text-lg text-[#6c7691]">Query your datasets and manage workflows with AI</p>
              </div>
              <button className="rounded-lg border border-[#1d3f99] px-6 py-3 text-lg font-semibold text-[#1d3f99] transition hover:bg-[#f5f7ff]">
                + New Chat Session
              </button>
            </div>
          </div>

          <div className="flex min-h-0 flex-1">
            <aside className="hidden w-[340px] border-r border-[#e4e7f0] bg-[#f8f9fd] p-4 lg:block">
              <div className="flex h-12 items-center rounded-md border border-[#d7dceb] bg-white px-3">
                <input
                  className="h-full flex-1 bg-transparent text-base text-[#4a5370] outline-none placeholder:text-[#98a0b8]"
                  placeholder="Search chats..."
                />
                <span className="text-[#a0a8bf]">⌕</span>
              </div>

              <div className="mt-4 space-y-2">
                {starterChats.map((chat) => (
                  <div
                    key={chat.title}
                    className={`rounded-md p-3 ${
                      chat.active ? "border-l-4 border-[#1f4bc0] bg-[#e8edf9]" : "hover:bg-[#edf1fb]"
                    }`}
                  >
                    <p className="text-lg text-[#24365f]">{chat.title}</p>
                    <p className="mt-1 text-base text-[#8e98b0]">{chat.date}</p>
                  </div>
                ))}
              </div>
            </aside>

            <section className="flex min-w-0 flex-1 flex-col bg-[#f7f8fc]">
              <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
                <div className="mx-auto w-full max-w-[960px] space-y-8">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex items-start gap-4 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {message.role === "assistant" && (
                        <span className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[#1f3f93] text-white">
                          ✦
                        </span>
                      )}
                      <div
                        className={`max-w-[80%] rounded-xl border px-5 py-4 text-[22px] leading-relaxed md:text-[30px] ${
                          message.role === "assistant"
                            ? "border-[#dfe3ef] bg-[#f1f3f8] text-[#28354f]"
                            : "border-[#dbe0ec] bg-white text-[#263451]"
                        }`}
                      >
                        {message.content}
                        {message.isStreaming && <span className="ml-1 animate-pulse">|</span>}
                      </div>
                      {message.role === "user" && (
                        <span className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[#2ac88f] font-bold text-white">
                          TA
                        </span>
                      )}
                    </div>
                  ))}

                  {thinkingText && (
                    <div className="flex items-start gap-4">
                      <span className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[#1f3f93] text-white">
                        ↻
                      </span>
                      <div className="rounded-xl bg-[#e9edf6] px-5 py-3 text-[24px] italic text-[#95a0b9] md:text-[28px]">
                        {thinkingText}
                      </div>
                    </div>
                  )}
                  <div ref={scrollRef} />
                </div>
              </div>

              <div className="border-t border-[#e4e7f0] bg-[#f8f9fc] px-4 py-5 md:px-8">
                <form className="mx-auto w-full max-w-[960px]" onSubmit={handleSubmit}>
                  <div className="flex items-center gap-4 rounded-xl border border-[#d6dceb] bg-white px-4 py-3">
                    <button className="text-3xl text-[#8d96ac]" type="button">
                      ⎔
                    </button>
                    <input
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
                      placeholder="Ask me anything about your datasets..."
                      className="h-11 flex-1 bg-transparent text-xl text-[#3b4867] outline-none placeholder:text-[#9aa3ba] md:text-2xl"
                    />
                    <button
                      type="submit"
                      disabled={!input.trim() || socketState === "connecting"}
                      className="flex h-11 w-11 items-center justify-center rounded-md bg-[#1f3f93] text-xl text-white transition disabled:cursor-not-allowed disabled:bg-[#9ca9ce]"
                    >
                      ➤
                    </button>
                  </div>
                </form>
                <p className="mt-3 text-center text-sm text-[#9ca3b8]">
                  AI Assistant can make mistakes. Please verify important data facts.
                </p>
              </div>
            </section>
          </div>
        </section>
      </main>

      <div className="fixed bottom-4 right-4 rounded-md bg-white px-3 py-2 text-sm text-[#66708b] shadow">
        {connectedLabel}
      </div>
    </div>
  );
}

function SidebarItem({ label, active }: { label: string; active?: boolean }) {
  return (
    <div className={`mx-2 mb-5 rounded-lg p-2 text-center ${active ? "bg-[#2a56cb]" : "opacity-85"}`}>
      <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded border border-white/50 text-lg">▣</div>
      <p className="text-sm">{label}</p>
    </div>
  );
}
