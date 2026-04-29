<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  createRoomApi,
  getCurrentActiveRoomApi,
  getRoomRecommendationsApi,
  joinByInviteApi,
  resumeCheckApi,
} from '@/services'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import type { CurrentActiveRoomRes, RecommendedRoom, RoomRecommendationProfile } from '@/types/room'
import { isApiClientError } from '@/utils/error'

const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const creating = ref(false)
const joining = ref(false)
const resuming = ref(false)
const loadingActiveRoom = ref(false)
const loadingRecommendations = ref(false)
const joiningRecommendedRoomId = ref('')
const errorText = ref('')
const recommendationError = ref('')
const activeRoom = ref<CurrentActiveRoomRes | null>(null)
const recommendationProfile = ref<RoomRecommendationProfile | null>(null)
const recommendedRooms = ref<RecommendedRoom[]>([])

const createForm = reactive({
  room_name: '我的自习室',
  duration_minutes: 120,
})

const joinForm = reactive({
  invite_code: '',
})

function resetError(): void {
  errorText.value = ''
}

function intensityLabel(level: string | undefined): string {
  if (level === 'high') return '高强度'
  if (level === 'relaxed') return '轻松型'
  if (level === 'normal') return '均衡型'
  return '新用户'
}

async function createRoom(): Promise<void> {
  resetError()
  creating.value = true
  try {
    const res = await createRoomApi({
      host_user_id: authStore.userId,
      room_name: createForm.room_name.trim() || '自习室',
      duration_minutes: Number(createForm.duration_minutes),
    })
    roomStore.setLastRoomId(res.room_id)
    await router.push(`/room/${res.room_id}`)
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '创建房间失败，请重试。'
  } finally {
    creating.value = false
  }
}

async function joinRoom(): Promise<void> {
  resetError()
  joining.value = true
  try {
    const res = await joinByInviteApi({
      user_id: authStore.userId,
      invite_code: joinForm.invite_code.trim(),
      display_name: authStore.displayName || 'member',
    })
    roomStore.setLastRoomId(res.room_id)
    await router.push(`/room/${res.room_id}`)
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '加入房间失败，请重试。'
  } finally {
    joining.value = false
  }
}

async function joinRecommendedRoom(room: RecommendedRoom): Promise<void> {
  resetError()
  joiningRecommendedRoomId.value = room.room_id
  try {
    const res = await joinByInviteApi({
      user_id: authStore.userId,
      invite_code: room.invite_code,
      display_name: authStore.displayName || 'member',
    })
    roomStore.setLastRoomId(res.room_id)
    await router.push(`/room/${res.room_id}`)
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '加入推荐房间失败，请重试。'
  } finally {
    joiningRecommendedRoomId.value = ''
  }
}

async function logout(): Promise<void> {
  authStore.clearSession()
  roomStore.clearRoom()
  roomStore.clearLastRoomId()
  roomStore.resetAutoResumeFlag()
  await router.push('/auth')
}

async function resumeLastRoom(): Promise<void> {
  if (!roomStore.lastRoomId) return
  resetError()
  resuming.value = true
  try {
    await resumeCheckApi(roomStore.lastRoomId, authStore.userId)
    await router.push(`/room/${roomStore.lastRoomId}`)
  } catch (err) {
    roomStore.clearLastRoomId()
    errorText.value = isApiClientError(err) ? `恢复失败：${err.message}` : '恢复房间失败，请重新加入。'
  } finally {
    resuming.value = false
  }
}

async function loadActiveRoom(): Promise<void> {
  loadingActiveRoom.value = true
  try {
    const res = await getCurrentActiveRoomApi(authStore.userId)
    activeRoom.value = res
    roomStore.setLastRoomId(res.room_id)
  } catch {
    activeRoom.value = null
  } finally {
    loadingActiveRoom.value = false
  }
}

async function loadRecommendations(): Promise<void> {
  loadingRecommendations.value = true
  recommendationError.value = ''
  try {
    const res = await getRoomRecommendationsApi(authStore.userId, 6)
    recommendationProfile.value = res.user_profile
    recommendedRooms.value = res.rooms
  } catch (err) {
    recommendedRooms.value = []
    recommendationProfile.value = null
    recommendationError.value = isApiClientError(err) ? err.message : '推荐房间加载失败。'
  } finally {
    loadingRecommendations.value = false
  }
}

async function enterActiveRoom(): Promise<void> {
  if (!activeRoom.value) return
  resetError()
  roomStore.setLastRoomId(activeRoom.value.room_id)
  await router.push(`/room/${activeRoom.value.room_id}`)
}

onMounted(async () => {
  await loadActiveRoom()
  await loadRecommendations()
  if (roomStore.autoResumeTried) return
  roomStore.markAutoResumeTried()
  if (!roomStore.lastRoomId) return
  await resumeLastRoom()
})
</script>

<template>
  <main class="page page-lobby">
    <section class="topbar">
      <div>
        <h1 class="title">大厅</h1>
        <p class="subtitle">
          你好，{{ authStore.displayName || authStore.loginUserId }}。从这里继续你的房间、创建新的自习室，或通过邀请码加入同伴。
        </p>
      </div>
      <div class="actions">
        <button class="btn" @click="router.push('/profile')">个人主页</button>
        <button
          class="btn"
          @click="resumeLastRoom"
          :disabled="!roomStore.lastRoomId || resuming"
        >
          {{ resuming ? '恢复中...' : '返回上次房间' }}
        </button>
        <button class="btn" @click="logout">退出登录</button>
      </div>
    </section>

    <section class="lobby-hero card">
      <div class="lobby-hero-copy">
        <p class="section-kicker">CONTROL PANEL</p>
        <h2>今天想从哪里开始？</h2>
        <p class="subtitle">
          如果你已经在一个房间里，直接返回；如果没有，就快速创建一个新的空间，或者通过邀请码加入正在进行的讨论。
        </p>
      </div>
      <div class="lobby-hero-stats">
        <div class="lobby-stat">
          <strong>{{ activeRoom ? '1' : '0' }}</strong>
          <span>当前活跃房间</span>
        </div>
        <div class="lobby-stat">
          <strong>{{ roomStore.lastRoomId ? '已记录' : '未记录' }}</strong>
          <span>本地恢复状态</span>
        </div>
        <div class="lobby-stat">
          <strong>{{ authStore.displayName || authStore.loginUserId }}</strong>
          <span>当前账号</span>
        </div>
      </div>
    </section>

    <section class="card recommendation-panel">
      <div class="lobby-card-head">
        <div>
          <p class="section-kicker">MATCHED ROOMS</p>
          <h2>为你推荐的自习室</h2>
        </div>
        <span class="badge">{{ intensityLabel(recommendationProfile?.intensity_level) }}</span>
      </div>

      <div v-if="recommendationProfile" class="recommendation-profile">
        <div class="lobby-info-pill">
          <span>平均单次</span>
          <strong>{{ Math.round(recommendationProfile.avg_session_minutes) }} 分钟</strong>
        </div>
        <div class="lobby-info-pill">
          <span>偏好时长</span>
          <strong>{{ Math.round(recommendationProfile.preferred_duration_minutes) }} 分钟</strong>
        </div>
        <div class="lobby-info-pill">
          <span>近30天</span>
          <strong>{{ recommendationProfile.study_days_30d }} 天 / {{ recommendationProfile.total_minutes_30d }} 分钟</strong>
        </div>
        <div class="lobby-info-pill">
          <span>常见时段</span>
          <strong>{{ recommendationProfile.preferred_period_name }}</strong>
        </div>
      </div>

      <p v-if="loadingRecommendations" class="tip">正在根据你的学习习惯匹配房间...</p>
      <p v-else-if="recommendationError" class="tip tip-error">{{ recommendationError }}</p>
      <p v-else-if="!recommendedRooms.length" class="tip">
        暂时没有可推荐的活跃房间。你可以先创建一个房间，系统会根据时长自动生成标签。
      </p>

      <div v-else class="recommendation-list">
        <article
          v-for="room in recommendedRooms"
          :key="room.room_id"
          class="recommendation-room"
        >
          <div class="recommendation-room-main">
            <div class="recommendation-room-title">
              <h3>{{ room.room_name }}</h3>
              <strong>{{ Math.round(room.match_score * 100) }}%</strong>
            </div>
            <div class="recommendation-tags">
              <span v-for="tag in room.tags" :key="tag.code">{{ tag.name }}</span>
            </div>
            <ul class="recommendation-reasons">
              <li v-for="reason in room.reasons" :key="reason">{{ reason }}</li>
            </ul>
          </div>

          <div class="recommendation-room-side">
            <div class="recommendation-meta">
              <span>{{ room.duration_minutes }} 分钟</span>
              <span>{{ room.member_count }}/{{ room.max_members }} 人</span>
              <span>邀请码 {{ room.invite_code }}</span>
            </div>
            <button
              class="btn btn-primary"
              type="button"
              :disabled="joiningRecommendedRoomId === room.room_id"
              @click="joinRecommendedRoom(room)"
            >
              {{ joiningRecommendedRoomId === room.room_id ? '加入中...' : '加入推荐房间' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="grid-2 lobby-grid">
      <article class="card lobby-feature-card lobby-current-room" v-if="activeRoom">
        <div class="lobby-card-head">
          <div>
            <p class="section-kicker">CURRENT ROOM</p>
            <h2>继续当前房间</h2>
          </div>
          <span class="badge">{{ activeRoom.role === 'host' ? 'host' : 'member' }}</span>
        </div>

        <p class="tip">
          你当前有一个{{ activeRoom.role === 'host' ? '主持中' : '已加入的' }}房间，刷新页面或重新登录后也可以从这里直接回去。
        </p>

        <div class="lobby-current-room-grid">
          <div class="lobby-info-pill">
            <span>房间名</span>
            <strong>{{ activeRoom.room_name }}</strong>
          </div>
          <div class="lobby-info-pill">
            <span>邀请码</span>
            <strong>{{ activeRoom.invite_code }}</strong>
          </div>
          <div class="lobby-info-pill">
            <span>状态</span>
            <strong>{{ activeRoom.status }}</strong>
          </div>
          <div class="lobby-info-pill">
            <span>结束时间</span>
            <strong>{{ activeRoom.ends_at }}</strong>
          </div>
        </div>

        <div class="lobby-inline-actions">
          <button class="btn btn-primary" @click="enterActiveRoom">进入当前房间</button>
          <button class="btn" @click="resumeLastRoom" :disabled="resuming">
            {{ resuming ? '恢复中...' : '用本地记录恢复' }}
          </button>
        </div>
      </article>

      <article class="card lobby-feature-card">
        <div class="lobby-card-head">
          <div>
            <p class="section-kicker">CREATE</p>
            <h2>创建一个新的自习室</h2>
          </div>
        </div>
        <p class="tip">适合你自己开房，或者先建好空间再把邀请码发给别人。</p>

        <form class="form" @submit.prevent="createRoom">
          <label>
            <span>房间名</span>
            <input v-model.trim="createForm.room_name" placeholder="例如：毕业论文冲刺室" required />
          </label>
          <label>
            <span>时长（分钟）</span>
            <input v-model.number="createForm.duration_minutes" min="1" max="1440" type="number" required />
          </label>
          <button class="btn btn-primary" type="submit" :disabled="creating">
            {{ creating ? '创建中...' : '创建并进入' }}
          </button>
        </form>
      </article>

      <article class="card lobby-feature-card">
        <div class="lobby-card-head">
          <div>
            <p class="section-kicker">JOIN</p>
            <h2>通过邀请码加入房间</h2>
          </div>
        </div>
        <p class="tip">输入 12 位数字邀请码，快速进入你同伴正在进行的房间。</p>

        <form class="form" @submit.prevent="joinRoom">
          <label>
            <span>邀请码（12位数字）</span>
            <input
              v-model.trim="joinForm.invite_code"
              minlength="12"
              maxlength="12"
              placeholder="例如：366885432712"
              required
            />
          </label>
          <button class="btn btn-primary" type="submit" :disabled="joining">
            {{ joining ? '加入中...' : '加入房间' }}
          </button>
        </form>
      </article>

      <article class="card lobby-feature-card lobby-side-note">
        <div class="lobby-card-head">
          <div>
            <p class="section-kicker">FLOW</p>
            <h2>推荐使用方式</h2>
          </div>
        </div>
        <ul class="kv-list">
          <li><strong>1.</strong><span>登录后先看“当前房间”，避免重复创建。</span></li>
          <li><strong>2.</strong><span>自己开房时，用明确房间名，后续更容易恢复。</span></li>
          <li><strong>3.</strong><span>邀请别人时直接复制邀请码，不需要再发完整 URL。</span></li>
        </ul>
      </article>
    </section>

    <p v-if="loadingActiveRoom" class="tip">正在检查你的当前房间...</p>
    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
  </main>
</template>
