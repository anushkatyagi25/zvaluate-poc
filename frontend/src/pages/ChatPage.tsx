import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createChat,
  deleteChat,
  getChat,
  listChats,
  type ChatSummary,
  type ChatThread,
  type StoredChatMessage,
} from "../services/chatApiService";
import {
  chatSocketService,
  type QueryErrorPayload,
  type QueryStartedPayload,
  type ResponseChunkPayload,
  type SocketState,
} from "../services/chatSocketService";
import { fetchDatasets, type DatasetOption } from "../services/datasetsApiService";

type Role = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  isStreaming?: boolean;
};

function toChatSummary(chat: ChatThread): ChatSummary {
  const lastMessage = chat.messages[chat.messages.length - 1];
  return {
    chat_id: chat.chat_id,
    user_id: chat.user_id,
    message_count: chat.messages.length,
    last_user_message: lastMessage?.user_message,
    last_llm_response: lastMessage?.llm_response,
    created_at: chat.created_at,
    updated_at: chat.updated_at,
  };
}

function mapStoredMessages(messages: StoredChatMessage[]): ChatMessage[] {
  const mapped: ChatMessage[] = [];

  messages.forEach((message, index) => {
    mapped.push({
      id: `${message.timestamp}-${index}-user`,
      role: "user",
      content: message.user_message,
    });

    mapped.push({
      id: `${message.timestamp}-${index}-assistant`,
      role: "assistant",
      content: message.llm_response,
    });
  });

  return mapped;
}

function getChatTitle(chat: ChatSummary): string {
  const source = (chat.last_user_message ?? chat.last_llm_response ?? "New Chat Session").trim();
  if (source.length <= 52) {
    return source;
  }
  return `${source.slice(0, 52)}...`;
}

function formatRelativeDate(rawDate: string): string {
  const date = new Date(rawDate);
  if (Number.isNaN(date.getTime())) {
    return "Recently";
  }

  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);

  if (minutes < 1) {
    return "Just now";
  }

  if (minutes < 60) {
    return `${minutes} min ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hr ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function ChatPage() {
  const [socketState, setSocketState] = useState<SocketState>("connecting");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinkingText, setThinkingText] = useState("");
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const [chatToDelete, setChatToDelete] = useState<ChatSummary | null>(null);
  const [chatListError, setChatListError] = useState("");
  const [datasets, setDatasets] = useState<DatasetOption[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetsError, setDatasetsError] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");

  const activeChatIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const connectedLabel = useMemo(() => {
    if (socketState === "connected") return "Connected";
    if (socketState === "error") return "Connection issue";
    return "Connecting";
  }, [socketState]);

  const filteredChats = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    if (!query) {
      return chats;
    }

    return chats.filter((chat) => getChatTitle(chat).toLowerCase().includes(query));
  }, [chats, searchText]);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId]
  );

  const refreshChats = useCallback(async (preferredChatId?: string) => {
    const chatList = await listChats();
    setChats(chatList);
    setActiveChatId((current) => {
      if (current && chatList.some((chat) => chat.chat_id === current)) {
        return current;
      }

      if (preferredChatId && chatList.some((chat) => chat.chat_id === preferredChatId)) {
        return preferredChatId;
      }

      return chatList[0]?.chat_id ?? null;
    });
  }, []);

  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinkingText]);

  useEffect(() => {
    let isMounted = true;

    const loadDatasets = async () => {
      try {
        setDatasetsLoading(true);
        setDatasetsError("");
        const options = await fetchDatasets();
        if (!isMounted) return;
        setDatasets(options);
      } catch (error) {
        if (!isMounted) return;
        const message = error instanceof Error ? error.message : "Failed to load datasets";
        setDatasetsError(message);
      } finally {
        if (isMounted) {
          setDatasetsLoading(false);
        }
      }
    };

    void loadDatasets();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    chatSocketService.connect({
      onConnect: () => setSocketState("connected"),
      onDisconnect: () => setSocketState("connecting"),
      onConnectError: () => setSocketState("error"),
      onQueryStarted: (data: QueryStartedPayload) => {
        if (data.chat_id !== activeChatIdRef.current) {
          return;
        }
      },
      onThinking: (data) => {
        if (data.chat_id && data.chat_id !== activeChatIdRef.current) {
          return;
        }

        setThinkingText(data.status ?? "Analyzing dataset records...");
      },
      onResponseChunk: (data: ResponseChunkPayload) => {
        if (data.chat_id !== activeChatIdRef.current) {
          return;
        }

        setThinkingText("");
        setMessages((prev) => {
          const existingIndex = prev.findIndex((message) => message.id === data.message_id);
          if (existingIndex === -1) {
            return [...prev, { id: data.message_id, role: "assistant", content: data.content, isStreaming: true }];
          }

          return prev.map((message) =>
            message.id === data.message_id
              ? { ...message, content: message.content + data.content, isStreaming: true }
              : message
          );
        });
      },
      onQueryComplete: (data) => {
        setThinkingText("");

        if (data.chat_id === activeChatIdRef.current) {
          setMessages((prev) => {
            const existingIndex = prev.findIndex((message) => message.id === data.message_id);
            if (existingIndex === -1) {
              return [...prev, { id: data.message_id, role: "assistant", content: data.response, isStreaming: false }];
            }

            return prev.map((message) =>
              message.id === data.message_id ? { ...message, content: data.response, isStreaming: false } : message
            );
          });
        }

        void refreshChats(data.chat_id);
      },
      onQueryError: (data: QueryErrorPayload) => {
        setThinkingText("");

        if (data.chat_id && data.chat_id !== activeChatIdRef.current) {
          return;
        }

        const messageId = data.message_id;
        if (messageId) {
          setMessages((prev) => {
            const exists = prev.some((message) => message.id === messageId);
            if (!exists) {
              return [
                ...prev,
                {
                  id: messageId,
                  role: "assistant",
                  content: data.message,
                  isStreaming: false,
                },
              ];
            }

            return prev.map((message) =>
              message.id === messageId
                ? { ...message, content: data.message, isStreaming: false }
                : message
            );
          });
          return;
        }

        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.message,
          },
        ]);
      },
    });

    return () => chatSocketService.disconnect();
  }, [refreshChats]);

  useEffect(() => {
    let isCancelled = false;

    const bootstrapChats = async () => {
      setIsLoadingChats(true);

      try {
        const existingChats = await listChats();
        if (isCancelled) {
          return;
        }

        if (existingChats.length > 0) {
          setChats(existingChats);
          setActiveChatId(existingChats[0].chat_id);
          return;
        }

        const chat = await createChat();
        if (isCancelled) {
          return;
        }

        setChats([toChatSummary(chat)]);
        setActiveChatId(chat.chat_id);
      } catch (error) {
        if (isCancelled) {
          return;
        }

        setMessages([
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Error: ${(error as Error).message}`,
          },
        ]);
      } finally {
        if (!isCancelled) {
          setIsLoadingChats(false);
        }
      }
    };

    void bootstrapChats();

    return () => {
      isCancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeChatId) {
      setMessages([]);
      return;
    }

    let isCancelled = false;

    const fetchChatHistory = async () => {
      setIsLoadingMessages(true);
      setThinkingText("");

      try {
        const chat = await getChat(activeChatId);
        if (isCancelled) {
          return;
        }
        setMessages(mapStoredMessages(chat.messages));
      } catch (error) {
        if (isCancelled) {
          return;
        }

        setMessages([
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Error: ${(error as Error).message}`,
          },
        ]);
      } finally {
        if (!isCancelled) {
          setIsLoadingMessages(false);
        }
      }
    };

    void fetchChatHistory();

    return () => {
      isCancelled = true;
    };
  }, [activeChatId]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !activeChatId || !selectedDataset) {
      return;
    }

    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    chatSocketService.sendMessage({
      chatId: activeChatId,
      message: trimmed,
      datasetId: selectedDataset.id,
      datasetName: selectedDataset.name,
      datasetUrl: selectedDataset.url,
    });
    setInput("");
  };

  const handleCreateNewChat = async () => {
    if (isCreatingChat) {
      return;
    }

    setIsCreatingChat(true);
    setThinkingText("");

    try {
      const chat = await createChat();
      setChats((prev) => [toChatSummary(chat), ...prev.filter((existing) => existing.chat_id !== chat.chat_id)]);
      setActiveChatId(chat.chat_id);
      setMessages([]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Error: ${(error as Error).message}`,
        },
      ]);
    } finally {
      setIsCreatingChat(false);
    }
  };

  const handleDeleteClick = (chat: ChatSummary) => {
    if (deletingChatId) {
      return;
    }
    setChatListError("");
    setChatToDelete(chat);
  };

  const handleDeleteChat = async () => {
    if (!chatToDelete || deletingChatId) {
      return;
    }

    const chatId = chatToDelete.chat_id;
    setDeletingChatId(chatId);
    setChatListError("");
    setThinkingText("");

    try {
      const deletedActiveChat = activeChatIdRef.current === chatId;
      await deleteChat(chatId);
      await refreshChats();
      if (deletedActiveChat) {
        setMessages([]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to delete chat";
      setChatListError(message);
    } finally {
      setDeletingChatId(null);
      setChatToDelete(null);
    }
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
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight text-[#17233d] md:text-4xl">AI Chat Assistant</h1>
                <p className="mt-1 text-base text-[#6c7691] md:text-lg">Query your datasets and manage workflows with AI</p>
              </div>
              <button
                onClick={handleCreateNewChat}
                disabled={isCreatingChat}
                className="rounded-lg border border-[#1d3f99] px-5 py-2.5 text-base font-semibold text-[#1d3f99] transition hover:bg-[#f5f7ff] disabled:cursor-not-allowed disabled:border-[#9ca9ce] disabled:text-[#9ca9ce]"
              >
                {isCreatingChat ? "Creating..." : "+ New Chat Session"}
              </button>
            </div>
          </div>

          <div className="flex min-h-0 flex-1">
            <aside className="hidden w-[260px] min-h-0 flex-col border-r border-[#e4e7f0] bg-[#f8f9fd] p-3 lg:flex xl:w-[272px]">
              <div className="flex h-10 items-center rounded-md border border-[#d7dceb] bg-white px-2.5">
                <input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  className="h-full flex-1 bg-transparent text-sm text-[#4a5370] outline-none placeholder:text-[#98a0b8]"
                  placeholder="Search chats..."
                />
                <span className="text-sm text-[#a0a8bf]">⌕</span>
              </div>
              {chatListError && <p className="mt-2 px-2.5 text-xs text-[#b63b4d]">{chatListError}</p>}

              <div className="mt-3 min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
                {isLoadingChats && <p className="px-2.5 py-2 text-xs text-[#8e98b0]">Loading chats...</p>}

                {!isLoadingChats && filteredChats.length === 0 && (
                  <p className="px-2.5 py-2 text-xs text-[#8e98b0]">No chats found.</p>
                )}

                {filteredChats.map((chat) => {
                  const isActive = chat.chat_id === activeChatId;
                  const isDeleting = deletingChatId === chat.chat_id;
                  return (
                    <div
                      key={chat.chat_id}
                      className={`flex items-center gap-1 rounded-md ${
                        isActive ? "border-l-4 border-[#1f4bc0] bg-[#e8edf9]" : "hover:bg-[#edf1fb]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setActiveChatId(chat.chat_id);
                          setThinkingText("");
                        }}
                        className="min-w-0 flex-1 p-2.5 text-left"
                      >
                        <p className="truncate text-sm font-medium text-[#24365f]">{getChatTitle(chat)}</p>
                        <p className="mt-1 text-xs text-[#8e98b0]">{formatRelativeDate(chat.updated_at)}</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteClick(chat)}
                        disabled={!!deletingChatId}
                        aria-label={`Delete ${getChatTitle(chat)}`}
                        className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded text-[#cf3d4c] transition hover:bg-[#fdecef] hover:text-[#b92736] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isDeleting ? (
                          "…"
                        ) : (
                          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18" />
                            <path d="M8 6V4h8v2" />
                            <path d="M19 6l-1 14H6L5 6" />
                            <path d="M10 11v6" />
                            <path d="M14 11v6" />
                          </svg>
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </aside>

            <section className="flex min-w-0 flex-1 flex-col bg-[#f7f8fc]">
              <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
                <div className="mx-auto w-full max-w-[760px] space-y-5">
                  {isLoadingMessages && <p className="text-lg text-[#8e98b0]">Loading messages...</p>}

                  {!isLoadingMessages && messages.length === 0 && (
                    <div className="rounded-xl border border-[#dfe3ef] bg-[#f1f3f8] px-4 py-3 text-base text-[#607091] md:text-lg">
                      Start a new conversation in this chat session.
                    </div>
                  )}

                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex items-start gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {message.role === "assistant" && (
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#1f3f93] text-sm text-white">
                          ✦
                        </span>
                      )}
                      <div
                        className={`max-w-[85%] whitespace-pre-wrap break-words rounded-xl border px-4 py-3 text-[15px] leading-relaxed md:max-w-[78%] md:text-base ${
                          message.role === "assistant"
                            ? "border-[#dfe3ef] bg-[#f1f3f8] text-[#28354f]"
                            : "border-[#dbe0ec] bg-white text-[#263451]"
                        }`}
                      >
                        {message.content}
                        {message.isStreaming && <span className="ml-1 animate-pulse">|</span>}
                      </div>
                      {message.role === "user" && (
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#2ac88f] text-xs font-bold text-white">
                          TA
                        </span>
                      )}
                    </div>
                  ))}

                  {thinkingText && (
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#1f3f93] text-sm text-white">
                        ↻
                      </span>
                      <div className="rounded-xl bg-[#e9edf6] px-4 py-3 text-base italic text-[#95a0b9]">
                        {thinkingText}
                      </div>
                    </div>
                  )}
                  <div ref={scrollRef} />
                </div>
              </div>

              <div className="border-t border-[#e4e7f0] bg-[#f8f9fc] px-4 py-5 md:px-8">
                <form className="mx-auto w-full max-w-[760px]" onSubmit={handleSubmit}>
                  <div className="flex items-center gap-3 rounded-xl border border-[#d6dceb] bg-white px-3 py-2.5">
                    <select
                      id="dataset-select"
                      value={selectedDatasetId}
                      onChange={(event) => setSelectedDatasetId(event.target.value)}
                      disabled={datasetsLoading || !!datasetsError}
                      className="h-8 min-w-[150px] rounded-md border border-[#cfd6ea] bg-[#f7f9ff] px-2 text-xs text-[#24365f] outline-none transition focus:border-[#1f4bc0] disabled:cursor-not-allowed disabled:bg-[#f3f5fb] disabled:text-[#9aa3ba]"
                    >
                      <option value="">select dataset</option>
                      {datasetsLoading && <option value="">Loading datasets...</option>}
                      {!datasetsLoading && datasetsError && <option value="">Failed to load datasets</option>}
                      {!datasetsLoading &&
                        !datasetsError &&
                        datasets.map((dataset) => (
                          <option key={dataset.id} value={dataset.id}>
                            {dataset.name}
                          </option>
                        ))}
                    </select>
                    <input
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
                      placeholder="ask me anything"
                      className="h-10 flex-1 bg-transparent text-base text-[#3b4867] outline-none placeholder:text-[#9aa3ba]"
                    />
                    <button
                      type="submit"
                      disabled={!input.trim() || socketState !== "connected" || !activeChatId || !selectedDataset}
                      className="flex h-9 w-9 items-center justify-center rounded-md bg-[#1f3f93] text-base text-white transition disabled:cursor-not-allowed disabled:bg-[#9ca9ce]"
                    >
                      ➤
                    </button>
                  </div>
                </form>
                {datasetsError && <p className="mx-auto mt-2 w-full max-w-[960px] text-sm text-[#b63b4d]">{datasetsError}</p>}
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

      {chatToDelete && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#0c1530]/45 p-4">
          <div className="w-full max-w-md rounded-xl border border-[#e2e6f2] bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-[#1f2a44]">Delete Chat</h3>
            <p className="mt-2 text-sm text-[#5f6986]">
              Are you sure you want to delete &quot;{getChatTitle(chatToDelete)}&quot;? This action cannot be undone.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setChatToDelete(null)}
                disabled={!!deletingChatId}
                className="rounded-md border border-[#d4d9e8] px-3 py-2 text-sm font-medium text-[#4f5b79] transition hover:bg-[#f6f8fe] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteChat()}
                disabled={!!deletingChatId}
                className="rounded-md bg-[#cf3d4c] px-3 py-2 text-sm font-semibold text-white transition hover:bg-[#b92d3b] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingChatId ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
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
