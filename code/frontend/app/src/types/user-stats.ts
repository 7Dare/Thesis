export interface StudyCalendarRange {
  start_date: string;
  end_date: string;
  days: number;
}

export interface StudyCalendarSummary {
  total_seconds_all_time: number;
  total_seconds_365d: number;
  total_seconds_30d: number;
  streak_max_all_time_days: number;
  streak_max_365d_days: number;
  streak_max_30d_days: number;
}

export interface StudyCalendarDay {
  date: string;
  seconds: number;
  minutes: number;
  level: 0 | 1 | 2 | 3 | 4;
}

export interface StudyCalendarRes {
  user_id: string;
  range: StudyCalendarRange;
  summary: StudyCalendarSummary;
  heatmap: StudyCalendarDay[];
  levels: Record<string, string>;
}

