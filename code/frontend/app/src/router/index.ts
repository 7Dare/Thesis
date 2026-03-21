import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '@/stores'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    redirect: '/lobby',
  },
  {
    path: '/auth',
    name: 'auth',
    component: () => import('@/pages/AuthPage.vue'),
  },
  {
    path: '/lobby',
    name: 'lobby',
    component: () => import('@/pages/LobbyPage.vue'),
  },
  {
    path: '/room/:roomId',
    name: 'room',
    component: () => import('@/pages/RoomPage.vue'),
    props: true,
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/pages/ProfilePage.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const authStore = useAuthStore(pinia)

  if (!authStore.isAuthed && to.path !== '/auth') {
    return '/auth'
  }

  if (authStore.isAuthed && to.path === '/auth') {
    return '/lobby'
  }

  return true
})
