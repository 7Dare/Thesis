import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'study_auth_session_v1'

type SessionPayload = {
  userId: string
  loginUserId: string
  displayName: string
}

function loadSession(): SessionPayload | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SessionPayload
    if (!parsed.userId || !parsed.loginUserId) return null
    return parsed
  } catch {
    return null
  }
}

function saveSession(payload: SessionPayload | null): void {
  if (!payload) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export const useAuthStore = defineStore('auth', () => {
  const init = loadSession()

  const userId = ref(init?.userId ?? '')
  const loginUserId = ref(init?.loginUserId ?? '')
  const displayName = ref(init?.displayName ?? '')

  const isAuthed = computed(() => Boolean(userId.value))

  function setSession(payload: SessionPayload): void {
    userId.value = payload.userId
    loginUserId.value = payload.loginUserId
    displayName.value = payload.displayName
    saveSession(payload)
  }

  function clearSession(): void {
    userId.value = ''
    loginUserId.value = ''
    displayName.value = ''
    saveSession(null)
  }

  return {
    userId,
    loginUserId,
    displayName,
    isAuthed,
    setSession,
    clearSession,
  }
})
