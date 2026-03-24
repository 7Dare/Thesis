import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'study_auth_session_v1'

type SessionPayload = {
  userId: string
  loginUserId: string
  displayName: string
  email?: string | null
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
  const email = ref(init?.email ?? '')

  const isAuthed = computed(() => Boolean(userId.value))

  function setSession(payload: SessionPayload): void {
    userId.value = payload.userId
    loginUserId.value = payload.loginUserId
    displayName.value = payload.displayName
    email.value = payload.email || ''
    saveSession(payload)
  }

  function clearSession(): void {
    userId.value = ''
    loginUserId.value = ''
    displayName.value = ''
    email.value = ''
    saveSession(null)
  }

  function setEmail(value: string): void {
    email.value = value
    saveSession({
      userId: userId.value,
      loginUserId: loginUserId.value,
      displayName: displayName.value,
      email: value,
    })
  }

  function setProfile(payload: { displayName: string; email: string }): void {
    displayName.value = payload.displayName
    email.value = payload.email
    saveSession({
      userId: userId.value,
      loginUserId: loginUserId.value,
      displayName: payload.displayName,
      email: payload.email,
    })
  }

  return {
    userId,
    loginUserId,
    displayName,
    email,
    isAuthed,
    setSession,
    setEmail,
    setProfile,
    clearSession,
  }
})
