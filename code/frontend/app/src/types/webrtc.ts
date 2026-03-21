export type SignalType =
  | 'offer'
  | 'answer'
  | 'ice'
  | 'peer_ping'
  | 'peer_join'
  | 'peer_leave'
  | 'signal_error'
  | 'room_closed';

export interface SignalMessage {
  type: SignalType;
  room_id?: string;
  from_user_id?: string;
  target_user_id?: string;
  payload?: Record<string, unknown>;
  ts?: number;
}

export type PeerConnectionState =
  | 'new'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'failed'
  | 'closed';

export interface PeerState {
  userId: string;
  displayName: string;
  stream: MediaStream | null;
  connectionState: PeerConnectionState;
}

