<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createRoomApi, joinByInviteApi, resumeCheckApi } from '@/services'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { isApiClientError } from '@/utils/error'

const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const creating = ref(false)
const joining = ref(false)
const resuming = ref(false)
const errorText = ref('')

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

onMounted(async () => {
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
        <p class="subtitle">你好，{{ authStore.displayName || authStore.loginUserId }}</p>
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

    <section class="grid-2">
      <article class="card">
        <h2>创建房间</h2>
        <form class="form" @submit.prevent="createRoom">
          <label>
            <span>房间名</span>
            <input v-model.trim="createForm.room_name" required />
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

      <article class="card">
        <h2>邀请码入房</h2>
        <form class="form" @submit.prevent="joinRoom">
          <label>
            <span>邀请码（12位数字）</span>
            <input v-model.trim="joinForm.invite_code" minlength="12" maxlength="12" required />
          </label>
          <button class="btn btn-primary" type="submit" :disabled="joining">
            {{ joining ? '加入中...' : '加入房间' }}
          </button>
        </form>
      </article>
    </section>

    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
  </main>
</template>
