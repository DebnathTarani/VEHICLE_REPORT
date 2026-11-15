import { z } from "zod";
import { isValidVrn } from "./vrn";
import type { EntryCreate, Status } from "./types";

export const STATUSES: Status[] = ["work_done", "in_progress", "pending", "cancelled"];

const optionalDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD")
  .optional()
  .nullable()
  .or(z.literal("").transform(() => null));

const optionalTime = z
  .string()
  .regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Use HH:MM (24h)")
  .optional()
  .nullable()
  .or(z.literal("").transform(() => null));

export const entryRowSchema = z.object({
  location_id: z.number().int().positive("Location is required"),
  sr_no: z.number().int().positive().optional().nullable(),
  vrn: z
    .string()
    .min(1, "VRN is required")
    .refine((v) => isValidVrn(v), { message: "Invalid VRN (e.g. AS-01-AB-1234)" }),
  model: z.string().optional().nullable().or(z.literal("").transform(() => null)),
  entry_date: optionalDate,
  in_time: optionalTime,
  out_date: optionalDate,
  out_time: optionalTime,
  status: z.enum(["work_done", "in_progress", "pending", "cancelled"], {
    errorMap: () => ({ message: "Pick a valid status" }),
  }),
  remarks: z.string().optional().nullable().or(z.literal("").transform(() => null)),
});

export type EntryRowInput = z.input<typeof entryRowSchema>;

/** Validate one entry row; returns a field -> message map (empty when valid). */
export function validateEntryRow(row: EntryRowInput): Record<string, string> {
  const result = entryRowSchema.safeParse(row);
  if (result.success) return {};
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path[0];
    if (typeof key === "string" && !errors[key]) errors[key] = issue.message;
  }
  return errors;
}

/** Convert a draft row to an EntryCreate payload ready for POST. */
export function rowToEntryCreate(
  row: EntryRowInput,
  locationId: number,
  srNo: number | null,
): EntryCreate {
  const parsed = entryRowSchema.parse(row);
  return {
    location_id: parsed.location_id ?? locationId,
    sr_no: srNo,
    vrn: parsed.vrn,
    model: parsed.model || null,
    entry_date: parsed.entry_date || null,
    in_time: parsed.in_time || null,
    out_date: parsed.out_date || null,
    out_time: parsed.out_time || null,
    status: parsed.status,
    remarks: parsed.remarks || null,
  };
}
