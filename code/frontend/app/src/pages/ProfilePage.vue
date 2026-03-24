<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import StudyHeatmap from '@/components/profile/StudyHeatmap.vue';
import { getStudyCalendarApi, updateProfileApi } from '@/services';
import { useAuthStore } from '@/stores/auth';
import type { StudyCalendarRes } from '@/types/user-stats';
import { isApiClientError } from '@/utils/error';

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const errorText = ref('');
const stats = ref<StudyCalendarRes | null>(null);
const displayNameForm = ref('');
const emailForm = ref('');
const profilePending = ref(false);
const profileSuccessText = ref('');

const avatarInitial = computed(() => {
  const base = authStore.displayName || authStore.loginUserId || 'U';
  return base.slice(0, 1).toUpperCase();
});

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

async function saveProfile(): Promise<void> {
  profilePending.value = true;
  errorText.value = '';
  profileSuccessText.value = '';
  try {
    const res = await updateProfileApi({
      user_id: authStore.userId,
      display_name: displayNameForm.value.trim(),
      email: emailForm.value.trim() || undefined,
    });
    authStore.setProfile({
      displayName: res.display_name,
      email: res.email || '',
    });
    displayNameForm.value = res.display_name;
    emailForm.value = res.email || '';
    profileSuccessText.value = '资料已更新。';
  } catch (err) {
    errorText.value = isApiClientError(err) ? err.message : '资料更新失败。';
  } finally {
    profilePending.value = false;
  }
}

onMounted(() => {
  displayNameForm.value = authStore.displayName || '';
  emailForm.value = authStore.email || '';
  void loadStats();
});
</script>

<template>
  <main class="page page-profile">
    <section class="topbar">
      <div>
        <h1 class="title">个人学习数据</h1>
        <p class="subtitle">查看你的账号信息、学习记录与阶段性专注表现。</p>
      </div>
      <div class="actions">
        <button class="btn" @click="loadStats" :disabled="loading">刷新</button>
        <button class="btn" @click="router.push('/lobby')">返回大厅</button>
      </div>
    </section>

    <section class="profile-hero card">
      <div class="profile-avatar-wrap">
        <div class="profile-avatar">{{ avatarInitial }}</div>
        <p class="tip">头像预留位</p>
      </div>

      <div class="profile-hero-copy">
        <p class="section-kicker">PROFILE</p>
        <h2>{{ authStore.displayName || authStore.loginUserId }}</h2>
        <p class="subtitle">基础账号信息与学习统计总览。</p>

        <div class="profile-meta-grid">
          <div class="profile-meta-item">
            <span>显示名</span>
            <strong>{{ authStore.displayName || '-' }}</strong>
          </div>
          <div class="profile-meta-item profile-meta-item-wide">
            <span>邮箱</span>
            <strong>{{ authStore.email || '暂未设置邮箱' }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="card profile-settings-card">
      <div class="profile-settings-head">
        <div>
          <p class="section-kicker">ACCOUNT</p>
          <h2>资料设置</h2>
        </div>
        <span class="subtitle">修改显示名与邮箱</span>
      </div>

      <form class="form profile-email-form" @submit.prevent="saveProfile">
        <label>
          <span>显示名</span>
          <input
            v-model.trim="displayNameForm"
            type="text"
            maxlength="64"
            placeholder="输入你希望展示给别人的名字"
            required
          />
        </label>
        <label>
          <span>邮箱地址</span>
          <input
            v-model.trim="emailForm"
            type="email"
            placeholder="name@example.com，留空可清除邮箱"
          />
        </label>
        <div class="profile-email-actions">
          <button class="btn btn-primary" type="submit" :disabled="profilePending">
            {{ profilePending ? '保存中...' : '保存资料' }}
          </button>
        </div>
      </form>
    </section>

    <section v-if="loading" class="card">加载中...</section>
    <p v-if="errorText" class="tip tip-error">{{ errorText }}</p>
    <p v-if="profileSuccessText" class="tip tip-success">{{ profileSuccessText }}</p>

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
