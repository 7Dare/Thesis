import type {
  Conversation,
  ListMessagesRes,
  SendMessageReq,
  ChatMessage,
  UpdateReadCursorReq,
  UpdateReadCursorRes,
} from '@/types/chat';

import { apiGet, apiPost } from './http';

export function getConversationApi(roomId: string, userId: string): Promise<Conversation> {
  return apiGet<Conversation>(`/rooms/${roomId}/chat/conversation`, {
    params: { user_id: userId },
  });
}

export function sendMessageApi(roomId: string, req: SendMessageReq): Promise<ChatMessage> {
  return apiPost<SendMessageReq, ChatMessage>(`/rooms/${roomId}/chat/messages`, req);
}

export function listMessagesApi(
  roomId: string,
  userId: string,
  limit = 20,
  beforeMessageId?: number,
): Promise<ListMessagesRes> {
  return apiGet<ListMessagesRes>(`/rooms/${roomId}/chat/messages`, {
    params: {
      user_id: userId,
      limit,
      before_message_id: beforeMessageId,
    },
  });
}

export function updateReadCursorApi(
  roomId: string,
  req: UpdateReadCursorReq,
): Promise<UpdateReadCursorRes> {
  return apiPost<UpdateReadCursorReq, UpdateReadCursorRes>(`/rooms/${roomId}/chat/read-cursor`, req);
}
