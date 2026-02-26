export type StoredChatMessage = {
  user_message: string;
  llm_response: string;
  timestamp: string;
};

export type ChatThread = {
  chat_id: string;
  user_id: string | null;
  messages: StoredChatMessage[];
  created_at: string;
  updated_at: string;
};

export type ChatSummary = {
  chat_id: string;
  user_id: string | null;
  message_count: number;
  last_user_message?: string;
  last_llm_response?: string;
  created_at: string;
  updated_at: string;
};

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function createChat(): Promise<ChatThread> {
  const response = await fetch(`${apiUrl}/api/chats`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  const payload = await readJson<{ chat: ChatThread }>(response);
  return payload.chat;
}

export async function listChats(): Promise<ChatSummary[]> {
  const response = await fetch(`${apiUrl}/api/chats`);
  const payload = await readJson<{ chats: ChatSummary[] }>(response);
  return payload.chats;
}

export async function getChat(chatId: string): Promise<ChatThread> {
  const response = await fetch(`${apiUrl}/api/chats/${encodeURIComponent(chatId)}`);
  const payload = await readJson<{ chat: ChatThread }>(response);
  return payload.chat;
}
