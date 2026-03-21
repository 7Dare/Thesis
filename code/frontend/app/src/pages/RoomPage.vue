<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import InferencePanel from '@/components/inference/InferencePanel.vue';
import VideoWall from '@/components/media/VideoWall.vue';
import {
  closeRoomApi,
  getConversationApi,
  getRoomApi,
  getRoomStudyTimeApi,
  leaveRoomApi,
  listMessagesApi,
  sendMessageApi,
  updateReadCursorApi,
} from '@/services';
import { useAuthStore } from '@/stores/auth';
import { useMediaStore } from '@/stores/media';
import { useRoomStore } from '@/stores/room';
import type { ChatMessage } from '@/types/chat';
import type { RoomStudyTimeRes } from '@/types/room';
import { isApiClientError } from '@/utils/error';
import { PeerManager } from '@/webrtc/peerManager';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const roomStore = useRoomStore();
const mediaStore = useMediaStore();

const loading = ref(false);
const leaving = ref(false);
const closing = ref(false);
const errorText = ref('');
const chatError = ref('');
const conversationId = ref('');
const chatMessages = ref<ChatMessage[]>([]);
const nextBeforeMessageId = ref<number | null>(null);
const chatLoading = ref(false);
const chatLoadingMore = ref(false);
const sending = ref(false);
const messageInput = ref('');
const studyTime = ref<RoomStudyTimeRes | null>(null);
const studyTimeLoading = ref(false);
const studyTimeError = ref('');
let chatPollTimer: ReturnType<typeof setInterval> | null = null;
let studyTimeTimer: ReturnType<typeof setInterval> | null = null;
const peerManager = ref<PeerManager | null>(null);

const roomId = computed(() => String(route.params.roomId || ''));
const room = computed(() => roomStore.currentRoom);
const isHost = computed(() => room.value?.host_user_id === authStore.userId);
const memberNameMap = computed(() => {
  const map = new Map<string, string>();
  for (const member of room.value?.members || []) {
    map.set(member.user_id, member.display_name || member.user_id);
  }
  return map;
});
const hostDisplayName = computed(
  () => memberNameMap.value.get(room.value?.host_user_id || '') || room.value?.host_user_id || '-',
);

async function loadRoom(): Promise<boolean> {
  loading.value = true;
  errorText.value = '';
  try {
    const res = await getRoomApi(roomId.value);
    roomStore.setRoom(res);
    return true;
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '房间加载失败。';
    return false;
  } finally {
    loading.value = false;
  }
}

async function leaveRoom(): Promise<void> {
  leaving.value = true;
  errorText.value = '';
  try {
    await leaveRoomApi(roomId.value, { user_id: authStore.userId });
    cleanupMedia();
    roomStore.clearRoom();
    roomStore.clearLastRoomId();
    await router.push('/lobby');
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '离开房间失败。';
  } finally {
    leaving.value = false;
  }
}

async function closeRoom(): Promise<void> {
  closing.value = true;
  errorText.value = '';
  try {
    await closeRoomApi(roomId.value, { host_user_id: authStore.userId });
    cleanupMedia();
    roomStore.clearRoom();
    roomStore.clearLastRoomId();
    await router.push('/lobby');
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '关闭房间失败。';
  } finally {
    closing.value = false;
  }
}

function mergeMessages(existing: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const map = new Map<number, ChatMessage>();
  for (const item of existing) map.set(item.message_id, item);
  for (const item of incoming) map.set(item.message_id, item);
  return Array.from(map.values()).sort((a, b) => a.message_id - b.message_id);
}

function getSenderDisplayName(senderUserId: string | null): string {
  if (!senderUserId) return 'system';
  if (senderUserId === authStore.userId) return authStore.displayName || '我';
  return memberNameMap.value.get(senderUserId) || '用户';
}

async function markReadLatest(): Promise<void> {
  const lastIndex = chatMessages.value.length - 1;
  if (lastIndex < 0) return;
  const last = chatMessages.value[lastIndex];
  if (!last) return;
  try {
    await updateReadCursorApi(roomId.value, {
      user_id: authStore.userId,
      last_read_message_id: last.message_id,
    });
  } catch {
    // Keep UI usable even if read-cursor update fails.
  }
}

async function initConversationAndMessages(): Promise<void> {
  chatLoading.value = true;
  chatError.value = '';
  try {
    const conv = await getConversationApi(roomId.value, authStore.userId);
    conversationId.value = conv.conversation_id;
    const list = await listMessagesApi(roomId.value, authStore.userId, 20);
    chatMessages.value = list.messages;
    nextBeforeMessageId.value = list.next_before_message_id;
    await markReadLatest();
  } catch (err) {
    chatError.value = isApiClientError(err) ? err.message : '聊天初始化失败。';
  } finally {
    chatLoading.value = false;
  }
}

async function refreshLatestMessages(): Promise<void> {
  if (!conversationId.value) return;
  try {
    const list = await listMessagesApi(roomId.value, authStore.userId, 20);
    chatMessages.value = mergeMessages(chatMessages.value, list.messages);
    await markReadLatest();
  } catch {
    // Silent refresh error to avoid noisy UI during polling.
  }
}

async function loadMoreMessages(): Promise<void> {
  if (!nextBeforeMessageId.value) return;
  chatLoadingMore.value = true;
  chatError.value = '';
  try {
    const list = await listMessagesApi(
      roomId.value,
      authStore.userId,
      20,
      nextBeforeMessageId.value,
    );
    chatMessages.value = mergeMessages(chatMessages.value, list.messages);
    nextBeforeMessageId.value = list.next_before_message_id;
  } catch (err) {
    chatError.value = isApiClientError(err) ? err.message : '加载历史消息失败。';
  } finally {
    chatLoadingMore.value = false;
  }
}

async function sendMessage(): Promise<void> {
  const content = messageInput.value.trim();
  if (!content) return;
  sending.value = true;
  chatError.value = '';
  try {
    const msg = await sendMessageApi(roomId.value, {
      user_id: authStore.userId,
      content,
    });
    chatMessages.value = mergeMessages(chatMessages.value, [msg]);
    messageInput.value = '';
    await markReadLatest();
  } catch (err) {
    chatError.value = isApiClientError(err) ? err.message : '发送消息失败。';
  } finally {
    sending.value = false;
  }
}

function startChatPolling(): void {
  if (chatPollTimer) clearInterval(chatPollTimer);
  chatPollTimer = setInterval(() => {
    void refreshLatestMessages();
  }, 3000);
}

function stopChatPolling(): void {
  if (chatPollTimer) {
    clearInterval(chatPollTimer);
    chatPollTimer = null;
  }
}

function formatSeconds(total: number | undefined): string {
  const value = Math.max(0, Math.floor(total || 0));
  const h = Math.floor(value / 3600);
  const m = Math.floor((value % 3600) / 60);
  const s = value % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

async function refreshStudyTime(showLoading = false): Promise<void> {
  if (showLoading) {
    studyTimeLoading.value = true;
  }
  try {
    const res = await getRoomStudyTimeApi(roomId.value, authStore.userId);
    studyTime.value = res;
    studyTimeError.value = '';
  } catch (err) {
    if (showLoading) {
      studyTimeError.value = isApiClientError(err) ? err.message : '学习时长加载失败。';
    }
  } finally {
    if (showLoading) {
      studyTimeLoading.value = false;
    }
  }
}

function startStudyTimePolling(): void {
  if (studyTimeTimer) clearInterval(studyTimeTimer);
  studyTimeTimer = setInterval(() => {
    void refreshStudyTime();
  }, 10000);
}

function stopStudyTimePolling(): void {
  if (studyTimeTimer) {
    clearInterval(studyTimeTimer);
    studyTimeTimer = null;
  }
}

function cleanupMedia(): void {
  const manager = peerManager.value;
  if (manager) {
    manager.cleanup();
    manager.stopLocalTracks();
    peerManager.value = null;
  }
  mediaStore.resetMediaState();
}

async function handleRoomClosedByHost(): Promise<void> {
  cleanupMedia();
  roomStore.clearRoom();
  roomStore.clearLastRoomId();
  errorText.value = '房间已关闭';
  await router.push('/lobby');
}

async function initMediaAndSignaling(): Promise<void> {
  mediaStore.clearError();
  const manager = new PeerManager(
    roomId.value,
    authStore.userId,
    authStore.displayName || 'member',
    {
      onWsStateChange: (connected) => {
        mediaStore.setWsConnected(connected);
        if (connected) {
          mediaStore.clearError();
        }
      },
      onPeerState: (userId, patch) => {
        const fallbackName = memberNameMap.value.get(userId) || userId;
        mediaStore.upsertPeer(userId, {
          ...patch,
          displayName: patch.displayName || fallbackName,
        });
      },
      onPeerLeave: (userId) => mediaStore.removePeer(userId),
      onError: (message) => mediaStore.setError(message),
      onRoomClosed: () => {
        void handleRoomClosedByHost();
      },
    },
  );
  peerManager.value = manager;

  try {
    const stream = await manager.initLocalStream();
    mediaStore.setLocalStream(stream);
  } catch {
    mediaStore.setPermissionError('未授予摄像头/麦克风权限');
    return;
  }

  try {
    await manager.connectSignaling();
  } catch {
    mediaStore.setError('建立信令失败');
  }
}

function toggleMic(): void {
  const manager = peerManager.value;
  if (!manager) return;
  const enabled = manager.toggleMic();
  mediaStore.setMicEnabled(enabled);
}

function toggleCamera(): void {
  const manager = peerManager.value;
  if (!manager) return;
  const enabled = manager.toggleCamera();
  mediaStore.setCamEnabled(enabled);
}

onMounted(async () => {
  const ok = await loadRoom();
  if (!ok) return;
  await refreshStudyTime(true);
  startStudyTimePolling();
  await initConversationAndMessages();
  startChatPolling();
  await initMediaAndSignaling();
});

onUnmounted(() => {
  stopChatPolling();
  stopStudyTimePolling();
  cleanupMedia();
});
</script>

<template>
  <main class="page page-room">
    <section class="topbar">
      <div>
        <h1 class="title">房间详情</h1>
        <p class="subtitle">room_id: {{ roomId }}</p>
      </div>
      <div class="actions">
        <button class="btn" @click="loadRoom" :disabled="loading">刷新</button>
        <button class="btn" @click="leaveRoom" :disabled="leaving">
          {{ leaving ? '离开中...' : '离开房间' }}
        </button>
        <button v-if="isHost" class="btn btn-danger" @click="closeRoom" :disabled="closing">
          {{ closing ? '关闭中...' : '关闭房间' }}
        </button>
      </div>
    </section>

    <section v-if="loading" class="card">加载中...</section>

    <section v-else-if="room" class="room-layout">
      <div class="room-main">
        <VideoWall
          :local-stream="mediaStore.localStream"
          :local-name="authStore.displayName || authStore.loginUserId || '我'"
          :peers="mediaStore.peers"
          :ws-connected="mediaStore.wsConnected"
          :mic-enabled="mediaStore.micEnabled"
          :cam-enabled="mediaStore.camEnabled"
          :permission-granted="mediaStore.permissionGranted"
          :error-text="mediaStore.lastError"
          @toggle-mic="toggleMic"
          @toggle-cam="toggleCamera"
        />

        <InferencePanel
          :room-id="roomId"
          :user-id="authStore.userId"
          :local-stream="mediaStore.localStream"
        />

        <article class="card">
          <h2>聊天区</h2>

          <div class="chat-panel">
            <div class="chat-toolbar">
              <button
                v-if="nextBeforeMessageId"
                class="btn"
                @click="loadMoreMessages"
                :disabled="chatLoadingMore"
              >
                {{ chatLoadingMore ? '加载中...' : '加载更多' }}
              </button>
              <span class="subtitle">会话：{{ conversationId || '-' }}</span>
            </div>

            <div v-if="chatLoading" class="chat-empty">聊天加载中...</div>
            <ul v-else class="chat-list">
              <li v-if="!chatMessages.length" class="chat-empty">暂无消息</li>
              <li
                v-for="msg in chatMessages"
                :key="msg.message_id"
                class="chat-item"
                :class="{ self: msg.sender_user_id === authStore.userId }"
              >
                <div class="chat-bubble">
                  <div class="chat-meta">
                    <span>{{ getSenderDisplayName(msg.sender_user_id) }}</span>
                    <span>#{{ msg.message_id }}</span>
                  </div>
                  <p class="chat-content">{{ msg.is_deleted ? '[消息已删除]' : msg.content }}</p>
                </div>
              </li>
            </ul>

            <form class="chat-send" @submit.prevent="sendMessage">
              <input v-model="messageInput" maxlength="2000" placeholder="输入消息..." />
              <button class="btn btn-primary" type="submit" :disabled="sending">
                {{ sending ? '发送中...' : '发送' }}
              </button>
            </form>
          </div>

          <p v-if="chatError" class="tip tip-error">{{ chatError }}</p>
        </article>
      </div>

      <aside class="room-sidebar">
        <article class="card">
          <h2>房间信息</h2>
          <ul class="kv-list">
            <li><strong>名称：</strong>{{ room.room_name }}</li>
            <li><strong>状态：</strong>{{ room.status }}</li>
            <li><strong>房主：</strong>{{ hostDisplayName }}</li>
            <li><strong>邀请码：</strong>{{ room.invite_code }}</li>
            <li><strong>成员数：</strong>{{ room.member_count }}</li>
            <li><strong>结束时间：</strong>{{ room.ends_at }}</li>
          </ul>
        </article>

        <article class="card">
          <h2>成员列表</h2>
          <ul class="member-list">
            <li v-for="m in room.members" :key="`${m.user_id}-${m.joined_at}`">
              <span>{{ m.display_name }}</span>
              <span class="badge">{{ m.role }}</span>
            </li>
          </ul>
        </article>

        <article class="card">
          <h2>学习时长统计</h2>
          <p v-if="studyTimeLoading" class="subtitle">加载中...</p>
          <p v-else class="subtitle">
            房间进行时长：{{ formatSeconds(studyTime?.room_elapsed_seconds) }}
          </p>
          <p class="subtitle">房间累计学习：{{ formatSeconds(studyTime?.room_total_seconds) }}</p>
          <p class="subtitle">我的累计学习：{{ formatSeconds(studyTime?.my_total_seconds) }}</p>

          <ul v-if="studyTime?.members?.length" class="member-list">
            <li v-for="m in studyTime.members" :key="`time-${m.user_id}`">
              <span>{{ m.display_name }}</span>
              <span class="badge">{{ formatSeconds(m.total_seconds) }}</span>
            </li>
          </ul>
          <p v-if="studyTimeError" class="tip tip-error">{{ studyTimeError }}</p>
        </article>
      </aside>
    </section>

    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
  </main>
</template>
