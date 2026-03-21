<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import StudyHeatmap from '@/components/profile/StudyHeatmap.vue';
import { getStudyCalendarApi } from '@/services';
import { useAuthStore } from '@/stores/auth';
import type { StudyCalendarRes } from '@/types/user-stats';
import { isApiClientError } from '@/utils/error';

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const errorText = ref('');
const stats = ref<StudyCalendarRes | null>(null);

function formatDuration(seconds: number | undefined): string {
  const sec = Math.max(0, Math.floor(seconds || 0));
  const hours = sec / 3600;
  if (hours >= 1) return `${hours.toFixed(1)} 小时`;
  return `${Math.floor(sec / 60)} 分钟`;
}

const summaryCards = computed(() => {
  const s = stats.value?.summary;
  if (!s) return [];
  return [
    { title: formatDuration(s.total_seconds_all_time), subtitle: '累计学习时长（全部）' },
    { title: formatDuration(s.total_seconds_365d), subtitle: '累计学习时长（近365天）' },
    { title: formatDuration(s.total_seconds_30d), subtitle: '累计学习时长（近30天）' },
    { title: `${s.streak_max_all_time_days} 天`, subtitle: '最大连续学习（全部）' },
    { title: `${s.streak_max_365d_days} 天`, subtitle: '最大连续学习（近365天）' },
    { title: `${s.streak_max_30d_days} 天`, subtitle: '最大连续学习（近30天）' },
  ];
});

async function loadStats(): Promise<void> {
  loading.value = true;
  errorText.value = '';
  try {
    stats.value = await getStudyCalendarApi(authStore.userId, 365);
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '学习统计加载失败。';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadStats();
});
</script>

<template>
  <main class="page page-profile">
    <section class="topbar">
      <div>
        <h1 class="title">个人学习数据</h1>
        <p class="subtitle">最近 365 天学习时长热力图</p>
      </div>
      <div class="actions">
        <button class="btn" @click="loadStats" :disabled="loading">刷新</button>
        <button class="btn" @click="router.push('/lobby')">返回大厅</button>
      </div>
    </section>

    <section v-if="loading" class="card">加载中...</section>
    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>

    <template v-if="stats">
      <StudyHeatmap :days="stats.heatmap" />
      <section class="profile-summary-grid">
        <article v-for="(card, idx) in summaryCards" :key="`s-${idx}`" class="profile-summary-item">
          <h3>{{ card.title }}</h3>
          <p>{{ card.subtitle }}</p>
        </article>
      </section>
    </template>
  </main>
</template>

