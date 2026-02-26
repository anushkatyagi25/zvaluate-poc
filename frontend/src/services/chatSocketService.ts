import { io, Socket } from "socket.io-client";

export type SocketState = "connecting" | "connected" | "error";

export type QueryStartedPayload = { message_id: string; chat_id: string };
export type ThinkingPayload = { chat_id?: string; status?: string };
export type ResponseChunkPayload = { message_id: string; chat_id: string; content: string };
export type QueryCompletePayload = { message_id: string; chat_id: string; response: string; timestamp?: string };
export type QueryErrorPayload = { message_id?: string; chat_id?: string; message: string };
export type SendMessagePayload = {
  chatId: string;
  message: string;
  datasetId: string;
  datasetName: string;
  datasetUrl: string;
};

const wsUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

export class ChatSocketService {
  private socket: Socket | null = null;

  connect(handlers: {
    onConnect: () => void;
    onDisconnect: () => void;
    onConnectError: () => void;
    onQueryStarted: (data: QueryStartedPayload) => void;
    onThinking: (data: ThinkingPayload) => void;
    onResponseChunk: (data: ResponseChunkPayload) => void;
    onQueryComplete: (data: QueryCompletePayload) => void;
    onQueryError: (data: QueryErrorPayload) => void;
  }) {
    if (this.socket) return;

    this.socket = io(wsUrl, {
      path: "/socket.io",
      transports: ["websocket"],
      reconnection: true,
    });

    this.socket.on("connect", handlers.onConnect);
    this.socket.on("disconnect", handlers.onDisconnect);
    this.socket.on("connect_error", handlers.onConnectError);
    this.socket.on("query_started", handlers.onQueryStarted);
    this.socket.on("thinking", handlers.onThinking);
    this.socket.on("response_chunk", handlers.onResponseChunk);
    this.socket.on("query_complete", handlers.onQueryComplete);
    this.socket.on("query_error", handlers.onQueryError);
  }

  sendMessage(payload: SendMessagePayload) {
    this.socket?.emit("message", {
      message: payload.message,
      chat_id: payload.chatId,
      dataset_id: payload.datasetId,
      dataset_name: payload.datasetName,
      dataset_url: payload.datasetUrl,
    });
  }

  disconnect() {
    this.socket?.disconnect();
    this.socket = null;
  }
}

export const chatSocketService = new ChatSocketService();
