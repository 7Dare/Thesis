<script setup lang="ts">
import { computed } from 'vue';

import type { StudyCalendarDay } from '@/types/user-stats';

const props = defineProps<{
  days: StudyCalendarDay[];
}>();

type Cell = StudyCalendarDay | null;

function toDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

const dayMap = computed(() => {
  const map = new Map<string, StudyCalendarDay>();
  for (const item of props.days) {
    map.set(item.date, item);
  }
  return map;
});

const firstDate = computed(() => {
  if (!props.days.length) return null;
  const first = props.days[0];
  return first ? toDate(first.date) : null;
});

const lastDate = computed(() => {
  if (!props.days.length) return null;
  const last = props.days[props.days.length - 1];
  return last ? toDate(last.date) : null;
});

const gridStart = computed(() => {
  if (!firstDate.value) return null;
  const d = new Date(firstDate.value);
  const day = d.getUTCDay();
  const mondayOffset = (day + 6) % 7;
  d.setUTCDate(d.getUTCDate() - mondayOffset);
  return d;
});

const cells = computed(() => {
  if (!gridStart.value || !lastDate.value) return [] as Cell[];
  const out: Cell[] = [];
  const end = new Date(lastDate.value);
  const cursor = new Date(gridStart.value);
  while (cursor <= end) {
    const k = cursor.toISOString().slice(0, 10);
    out.push(dayMap.value.get(k) || null);
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return out;
});

const weeks = computed(() => {
  const out: Cell[][] = [];
  for (let i = 0; i < cells.value.length; i += 7) {
    out.push(cells.value.slice(i, i + 7));
  }
  return out;
});

const monthLabels = computed(() => {
  const labels: Array<{ text: string; col: number }> = [];
  const seen = new Set<string>();
  weeks.value.forEach((week, col) => {
    const first = week.find((v) => v !== null);
    if (!first) return;
    const d = toDate(first.date);
    const key = `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
    if (seen.has(key)) return;
    seen.add(key);
    labels.push({
      text: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }),
      col,
    });
  });
  return labels;
});

function cellClass(cell: Cell): string {
  const level = cell?.level ?? 0;
  return `heat-cell level-${level}`;
}

function cellTitle(cell: Cell): string {
  if (!cell) return '';
  return `${cell.date} · ${cell.minutes} 分钟`;
}
</script>

<template>
  <section class="profile-heatmap-card">
    <div class="heat-months">
      <span
        v-for="item in monthLabels"
        :key="`${item.text}-${item.col}`"
        class="heat-month"
        :style="{ gridColumnStart: item.col + 1 }"
      >
        {{ item.text }}
      </span>
    </div>
    <div class="heat-wrap">
      <div class="heat-week-labels">
        <span>Mon</span>
        <span>Wed</span>
        <span>Fri</span>
      </div>
      <div class="heat-grid">
        <div v-for="(week, wIdx) in weeks" :key="`w-${wIdx}`" class="heat-week">
          <div
            v-for="(cell, dIdx) in week"
            :key="`c-${wIdx}-${dIdx}`"
            :class="cellClass(cell)"
            :title="cellTitle(cell)"
          />
        </div>
      </div>
    </div>
  </section>
</template>
