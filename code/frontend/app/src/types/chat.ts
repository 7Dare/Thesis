export interface Conversation {
  conversation_id: string;
  type: 'room';
  room_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SendMessageReq {
  user_id: string;
  content: string;
}

export interface ChatMessage {
  message_id: number;
  conversation_id: string;
  sender_user_id: string | null;
  content_type: 'text' | 'system';
  content: string | null;
  is_deleted: boolean;
  edited_at: string | null;
  created_at: string;
}

export interface ListMessagesRes {
  conversation_id: string;
  messages: ChatMessage[];
  next_before_message_id: number | null;
}

export interface UpdateReadCursorReq {
  user_id: string;
  last_read_message_id: number;
}

export interface UpdateReadCursorRes {
  conversation_id: string;
  user_id: string;
  last_read_message_id: number;
  last_read_at: string;
  updated_at: string;
}
