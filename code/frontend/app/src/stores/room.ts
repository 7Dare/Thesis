import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { RoomDetail } from '@/types/room'

const LAST_ROOM_ID_KEY = 'study_last_room_id_v1'

function loadLastRoomId(): string {
  try {
    return localStorage.getItem(LAST_ROOM_ID_KEY) || ''
  } catch {
    return ''
  }
}

function saveLastRoomId(roomId: string): void {
  try {
    if (!roomId) {
      localStorage.removeItem(LAST_ROOM_ID_KEY)
      return
    }
    localStorage.setItem(LAST_ROOM_ID_KEY, roomId)
  } catch {
    // Ignore storage errors.
  }
}

export const useRoomStore = defineStore('room', () => {
  const currentRoom = ref<RoomDetail | null>(null)
  const lastRoomId = ref(loadLastRoomId())
  const autoResumeTried = ref(false)

  function setRoom(room: RoomDetail): void {
    currentRoom.value = room
    lastRoomId.value = room.room_id
    saveLastRoomId(room.room_id)
  }

  function clearRoom(): void {
    currentRoom.value = null
  }

  function setLastRoomId(roomId: string): void {
    lastRoomId.value = roomId
    saveLastRoomId(roomId)
  }

  function clearLastRoomId(): void {
    lastRoomId.value = ''
    saveLastRoomId('')
  }

  function markAutoResumeTried(): void {
    autoResumeTried.value = true
  }

  function resetAutoResumeFlag(): void {
    autoResumeTried.value = false
  }

  return {
    currentRoom,
    lastRoomId,
    autoResumeTried,
    setRoom,
    clearRoom,
    setLastRoomId,
    clearLastRoomId,
    markAutoResumeTried,
    resetAutoResumeFlag,
  }
})
