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
      <h1 class="title">自习室系统</h1>
      <p class="subtitle">{{ isRegister ? '创建账号后登录' : '输入账号进入大厅' }}</p>

      <form class="form" @submit.prevent="submit">
        <label>
          <span>登录 ID</span>
          <input v-model.trim="form.login_user_id" required />
        </label>

        <label>
          <span>密码</span>
          <input v-model="form.password" type="password" required />
        </label>

        <label v-if="isRegister">
          <span>显示名</span>
          <input v-model.trim="form.display_name" required />
        </label>

        <label v-if="isRegister">
          <span>邮箱（可选）</span>
          <input v-model.trim="form.email" type="email" />
        </label>

        <button class="btn btn-primary" :disabled="pending" type="submit">
          {{ pending ? '处理中...' : isRegister ? '注册' : '登录' }}
        </button>
      </form>

      <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
      <p v-if="successText" class="tip tip-success">{{ successText }}</p>

      <button class="btn btn-link" @click="mode = isRegister ? 'login' : 'register'">
        {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
      </button>
    </section>
  </main>
</template>
