import type {
  ImportImageStatus,
  ImportJobStatus,
  ImportRowStatus,
  Status,
  VisionStatus,
} from "./types";

export const STATUSES: Status[] = ["work_done", "in_progress", "pending", "cancelled"];

export const STATUS_LABELS: Record<Status, string> = {
  work_done: "Work done",
  in_progress: "In progress",
  pending: "Pending",
  cancelled: "Cancelled",
};

export const STATUS_BADGE: Record<Status, string> = {
  work_done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  pending: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  cancelled: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

export const JOB_STATUS_BADGE: Record<ImportJobStatus, string> = {
  queued: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  partial: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

export const IMAGE_STATUS_BADGE: Record<ImportImageStatus, string> = {
  queued: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  extracted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

export const ROW_STATUS_BADGE: Record<ImportRowStatus, string> = {
  pending_review: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  accepted: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  committed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
};

export const ROW_STATUS_LABELS: Record<ImportRowStatus, string> = {
  pending_review: "Pending review",
  accepted: "Accepted",
  rejected: "Rejected",
  committed: "Committed",
};

export const VISION_LABELS: Record<VisionStatus, string> = {
  unknown: "Vision unknown",
  supported: "Vision supported",
  unsupported: "Vision unsupported",
};

export const VISION_BADGE: Record<VisionStatus, string> = {
  unknown: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  supported: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  unsupported: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};
