<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { loginApi, registerApi } from '@/services'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { isApiClientError } from '@/utils/error'

const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const mode = ref<'login' | 'register'>('login')
const pending = ref(false)
const errorText = ref('')
const successText = ref('')

const form = reactive({
  login_user_id: '',
  password: '',
  display_name: '',
  email: '',
})

const isRegister = computed(() => mode.value === 'register')

function resetTips(): void {
  errorText.value = ''
  successText.value = ''
}

async function submit(): Promise<void> {
  resetTips()
  pending.value = true
  try {
    if (isRegister.value) {
      await registerApi({
        login_user_id: form.login_user_id.trim(),
        password: form.password,
        display_name: form.display_name.trim(),
        email: form.email.trim() || undefined,
      })
      mode.value = 'login'
      successText.value = '注册成功，请登录。'
      return
    }

    const res = await loginApi({
      login_user_id: form.login_user_id.trim(),
      password: form.password,
    })

    authStore.setSession({
      userId: res.user_id,
      loginUserId: res.login_user_id,
      displayName: res.display_name,
      email: res.email,
    })
    roomStore.resetAutoResumeFlag()

    await router.push('/lobby')
  } catch (err) {
    if (isApiClientError(err)) {
      errorText.value = err.message
    } else {
      errorText.value = '请求失败，请稍后重试。'
    }
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <main class="page page-auth">
    <section class="card auth-card">
      <div class="auth-hero">
        <p class="section-kicker">ONLINE STUDY ROOM</p>
        <h1 class="title">把专注感和陪伴感放进同一个房间里。</h1>
        <p class="subtitle">
          {{ isRegister ? '创建账号后登录，开始你的专注记录。' : '输入账号后进入大厅，继续你的房间与学习进度。' }}
        </p>

        <div class="auth-highlights">
          <div class="auth-highlight">
            <strong>房间协作</strong>
            <span>创建邀请码房间，快速回到你的学习小组。</span>
          </div>
          <div class="auth-highlight">
            <strong>状态追踪</strong>
            <span>记录学习时长、聊天、房间恢复和在线状态。</span>
          </div>
          <div class="auth-highlight">
            <strong>视觉专注</strong>
            <span>更安静的界面，更明确的当前任务入口。</span>
          </div>
        </div>
      </div>

      <div class="auth-panel">
        <div class="auth-panel-header">
          <div>
            <p class="section-kicker">{{ isRegister ? 'CREATE ACCOUNT' : 'WELCOME BACK' }}</p>
            <h2>{{ isRegister ? '注册新账号' : '登录你的账号' }}</h2>
          </div>
          <span class="badge auth-mode-badge">{{ isRegister ? 'register' : 'login' }}</span>
        </div>

        <form class="form" @submit.prevent="submit">
          <label>
            <span>登录 ID</span>
            <input v-model.trim="form.login_user_id" placeholder="例如：ryh" required />
          </label>

          <label>
            <span>密码</span>
            <input v-model="form.password" type="password" placeholder="至少 6 位" required />
          </label>

          <label v-if="isRegister">
            <span>显示名</span>
            <input v-model.trim="form.display_name" placeholder="别人会看到的名字" required />
          </label>

          <label v-if="isRegister">
            <span>邮箱（可选）</span>
            <input v-model.trim="form.email" type="email" placeholder="name@example.com" />
          </label>

          <button class="btn btn-primary auth-submit" :disabled="pending" type="submit">
            {{ pending ? '处理中...' : isRegister ? '注册并继续' : '进入大厅' }}
          </button>
        </form>

        <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
        <p v-if="successText" class="tip tip-success">{{ successText }}</p>

        <button class="btn btn-link" @click="mode = isRegister ? 'login' : 'register'">
          {{ isRegister ? '已有账号？切换到登录' : '没有账号？先创建一个' }}
        </button>
      </div>
    </section>
  </main>
</template>
