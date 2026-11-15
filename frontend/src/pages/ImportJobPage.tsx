import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  CheckCheck,
  Loader2,
  RotateCcw,
  Send,
  ZoomIn,
  ZoomOut,
  X,
} from "lucide-react";
import { api, apiUrl, ApiError } from "@/lib/api";
import type {
  EntryCreate,
  ImportImage,
  ImportJobDetail,
  ImportRow,
  Status,
} from "@/lib/types";
import { useAuth } from "@/context/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/ui/toaster";
import {
  IMAGE_STATUS_BADGE,
  JOB_STATUS_BADGE,
  ROW_STATUS_BADGE,
  ROW_STATUS_LABELS,
  STATUS_LABELS,
  STATUSES,
} from "@/lib/constants";
import { validateEntryRow } from "@/lib/validation";
import { formatVrn } from "@/lib/vrn";
import { cn } from "@/lib/utils";

type EditableField =
  | "vrn"
  | "model"
  | "entry_date"
  | "in_time"
  | "out_date"
  | "out_time"
  | "status"
  | "remarks";

const EDITABLE_FIELDS: EditableField[] = [
  "vrn",
  "model",
  "entry_date",
  "in_time",
  "out_date",
  "out_time",
  "status",
  "remarks",
];

function draftFromPayload(payload: EntryCreate): Record<EditableField, string> {
  return {
    vrn: payload.vrn ?? "",
    model: payload.model ?? "",
    entry_date: payload.entry_date ?? "",
    in_time: payload.in_time ?? "",
    out_date: payload.out_date ?? "",
    out_time: payload.out_time ?? "",
    status: payload.status,
    remarks: payload.remarks ?? "",
  };
}

function draftToPayload(draft: Record<EditableField, string>, locationId: number): EntryCreate {
  return {
    location_id: locationId,
    sr_no: null,
    vrn: draft.vrn,
    model: draft.model || null,
    entry_date: draft.entry_date || null,
    in_time: draft.in_time || null,
    out_date: draft.out_date || null,
    out_time: draft.out_time || null,
    status: draft.status as Status,
    remarks: draft.remarks || null,
  };
}

function ConfidenceBar({ value }: { value?: number }) {
  if (value == null) return null;
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const low = value < 0.7;
  return (
    <div className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={cn("h-full rounded-full", low ? "bg-amber-400" : "bg-emerald-500")}
        style={{ width: `${pct}%` }}
        title={`confidence ${pct}%`}
      />
    </div>
  );
}

interface ReviewRowProps {
  row: ImportRow;
  jobId: number;
  canOperate: boolean;
}

function ReviewRow({ row, jobId, canOperate }: ReviewRowProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<EditableField, string>>(() =>
    draftFromPayload(row.payload),
  );
  const [baseline, setBaseline] = useState(() => JSON.stringify(row.payload));
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const next = draftFromPayload(row.payload);
    if (JSON.stringify(row.payload) !== baseline) {
      setDraft(next);
      setBaseline(JSON.stringify(row.payload));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.payload]);

  const draftJson = JSON.stringify(draft);
  const dirty = draftJson !== baseline;

  const localErrors = useMemo(() => {
    const payload = draftToPayload(draft, row.payload.location_id);
    const errors = validateEntryRow({ ...payload, location_id: payload.location_id });
    delete errors.location_id;
    return errors;
  }, [draft, row.payload.location_id]);

  const allErrors = useMemo(
    () => ({ ...localErrors, ...serverErrors }),
    [localErrors, serverErrors],
  );
  const hasErrors = Object.keys(allErrors).length > 0 || !row.validation.valid;

  const commitMutation = useMutation({
    mutationFn: (payload: EntryCreate) =>
      api.patch<ImportRow>(`/imports/rows/${row.id}`, { payload }),
    onSuccess: (updated) => {
      setServerErrors(updated.validation?.errors ?? {});
      setDraft(draftFromPayload(updated.payload));
      setBaseline(JSON.stringify(updated.payload));
      void queryClient.invalidateQueries({ queryKey: ["import-job", jobId] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.fieldErrors) {
        setServerErrors(err.fieldErrors);
      } else {
        toast({ title: "Could not save row", description: (err as Error).message, variant: "destructive" });
      }
    },
  });

  const statusMutation = useMutation({
    mutationFn: (status: "accepted" | "pending_review") =>
      api.patch<ImportRow>(`/imports/rows/${row.id}`, { status }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["import-job", jobId] }),
    onError: (err) => {
      if (err instanceof ApiError && err.fieldErrors) {
        setServerErrors(err.fieldErrors);
        toast({ title: "Row is invalid", description: "Fix highlighted cells first", variant: "destructive" });
      } else {
        toast({ title: "Action failed", description: (err as Error).message, variant: "destructive" });
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post<ImportRow>(`/imports/rows/${row.id}/reject`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["import-job", jobId] }),
    onError: (err) => toast({ title: "Action failed", description: (err as Error).message, variant: "destructive" }),
  });

  const setField = (field: EditableField, value: string) =>
    setDraft((prev) => ({ ...prev, [field]: value }));

  const commitField = (field: EditableField) => {
    let nextDraft = draft;
    if (field === "vrn") {
      const formatted = formatVrn(draft.vrn);
      if (formatted !== draft.vrn) {
        nextDraft = { ...draft, vrn: formatted };
        setDraft(nextDraft);
      }
    }
    if (!dirty && field !== "vrn") return;
    const payload = draftToPayload(nextDraft, row.payload.location_id);
    commitMutation.mutate(payload);
  };

  const committed = row.status === "committed";
  const readOnly = committed || !canOperate;

  const cellClass = (field: EditableField) =>
    cn(
      "w-full rounded-md border border-transparent bg-transparent px-1.5 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      row.confidence?.[field] != null && row.confidence[field] < 0.7 && "bg-amber-50 dark:bg-amber-950/30",
      allErrors[field] && "border-red-400 bg-red-50 dark:bg-red-950/40",
      readOnly && "pointer-events-none opacity-70",
    );

  const renderField = (field: EditableField, width: string) => (
    <td key={field} className={cn("px-1.5 py-1", width)}>
      {committed ? (
        <span className={cn("block px-1.5 text-sm", field === "vrn" && "font-mono text-xs")}>
          {draft[field] || "—"}
        </span>
      ) : (
        <>
          {field === "status" ? (
            <select
              className={cn(cellClass(field), "appearance-none")}
              value={draft.status}
              onChange={(e) => setField("status", e.target.value)}
              onBlur={() => commitField("status")}
              disabled={readOnly}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={field === "entry_date" || field === "out_date" ? "date" : field === "in_time" || field === "out_time" ? "time" : "text"}
              className={cn(cellClass(field), field === "vrn" && "font-mono")}
              value={draft[field]}
              onChange={(e) => setField(field, e.target.value)}
              onBlur={() => commitField(field)}
              disabled={readOnly}
            />
          )}
          <ConfidenceBar value={row.confidence?.[field]} />
        </>
      )}
    </td>
  );

  return (
    <tr
      className={cn(
        "border-b border-border last:border-0",
        committed && "bg-emerald-50/60 dark:bg-emerald-950/20",
        row.status === "rejected" && "opacity-50",
      )}
    >
      {EDITABLE_FIELDS.map((field) => renderField(field, field === "remarks" ? "min-w-32" : ""))}
      <td className="px-2 py-1">
        <Badge className={ROW_STATUS_BADGE[row.status]}>{ROW_STATUS_LABELS[row.status]}</Badge>
      </td>
      {canOperate && !committed && (
        <td className="px-2 py-1">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-emerald-600"
              title="Accept"
              disabled={statusMutation.isPending || hasErrors || row.status === "accepted"}
              onClick={() => statusMutation.mutate("accepted")}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-red-600"
              title="Reject"
              disabled={rejectMutation.isPending || row.status === "rejected"}
              onClick={() => rejectMutation.mutate()}
            >
              <X className="h-4 w-4" />
            </Button>
            {row.status !== "pending_review" && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                title="Reopen"
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate("pending_review")}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </td>
      )}
    </tr>
  );
}

function ImageCard({
  job,
  image,
  selected,
  canOperate,
  onSelect,
}: {
  job: ImportJobDetail;
  image: ImportImage;
  selected: boolean;
  canOperate: boolean;
  onSelect: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [zoomed, setZoomed] = useState(false);

  const retryMutation = useMutation({
    mutationFn: () => api.post<{ job_id: number }>(`/imports/${job.id}/images/${image.id}/retry`),
    onSuccess: () => {
      toast({ title: "Retry queued", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["import-job", job.id] });
    },
    onError: (err) => toast({ title: "Retry failed", description: (err as Error).message, variant: "destructive" }),
  });

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border bg-card p-3 text-left shadow-sm transition-colors",
        selected ? "border-primary ring-2 ring-ring/40" : "border-border hover:border-primary/40",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium">{image.filename}</span>
        <Badge className={IMAGE_STATUS_BADGE[image.status]}>{image.status}</Badge>
      </div>
      {image.status === "failed" ? (
        <div className="space-y-2">
          <Alert variant="destructive">
            <AlertTitle>Extraction failed</AlertTitle>
            <AlertDescription>{image.error ?? "Unknown error"}</AlertDescription>
          </Alert>
          {canOperate && (
            <Button
              size="sm"
              variant="outline"
              disabled={retryMutation.isPending}
              onClick={(e) => {
                e.stopPropagation();
                retryMutation.mutate();
              }}
            >
              {retryMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" />
              )}
              Retry
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="overflow-hidden rounded-md bg-muted">
            <img
              src={apiUrl(`/imports/${job.id}/images/${image.id}/file`)}
              alt={image.filename}
              className={cn(
                "mx-auto w-full object-contain transition-all",
                zoomed ? "max-h-[80vh] cursor-zoom-out" : "max-h-36 cursor-zoom-in",
              )}
              onClick={(e) => {
                e.stopPropagation();
                setZoomed((z) => !z);
              }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {image.provider ?? "—"} {image.model ? `· ${image.model}` : ""}
              {image.ocr_available ? " · OCR" : ""} · {image.rows.length} rows
            </span>
            {zoomed ? <ZoomOut className="h-3.5 w-3.5" /> : <ZoomIn className="h-3.5 w-3.5" />}
          </div>
        </div>
      )}
    </button>
  );
}

export function ImportJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const id = Number(jobId);
  const { canOperate } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const jobQuery = useQuery({
    queryKey: ["import-job", id],
    queryFn: () => api.get<ImportJobDetail>(`/imports/${id}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 2000 : false;
    },
  });

  const job = jobQuery.data;
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);

  useEffect(() => {
    if (!job?.images.length) return;
    if (selectedImageId == null || !job.images.some((i) => i.id === selectedImageId)) {
      setSelectedImageId(job.images[0].id);
    }
  }, [job, selectedImageId]);

  const selectedImage = job?.images.find((i) => i.id === selectedImageId) ?? null;
  const acceptedCount = job?.row_counts.accepted ?? 0;
  const pendingRows = (selectedImage?.rows ?? []).filter(
    (r) => r.status === "pending_review" && r.validation.valid,
  );

  const commitMutation = useMutation({
    mutationFn: () =>
      api.post<{ committed: number; entry_ids: number[] }>(`/imports/${id}/commit`),
    onSuccess: (res) => {
      toast({
        title: `Committed ${res.committed} ${res.committed === 1 ? "entry" : "entries"}`,
        description: "Rows are now permanent entries.",
        variant: "success",
      });
      void queryClient.invalidateQueries({ queryKey: ["import-job", id] });
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError: (err) =>
      toast({ title: "Commit failed", description: (err as Error).message, variant: "destructive" }),
  });

  const acceptAllMutation = useMutation({
    mutationFn: async () => {
      const results = await Promise.allSettled(
        pendingRows.map((r) => api.patch<ImportRow>(`/imports/rows/${r.id}`, { status: "accepted" })),
      );
      return results.filter((r) => r.status === "fulfilled").length;
    },
    onSuccess: (count) => {
      toast({
        title: count > 0 ? `Accepted ${count} valid ${count === 1 ? "row" : "rows"}` : "No valid rows to accept",
        variant: count > 0 ? "success" : "default",
      });
      void queryClient.invalidateQueries({ queryKey: ["import-job", id] });
    },
  });

  if (jobQuery.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  if (!job) {
    return <EmptyState title="Job not found" description="It may have been removed." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="hidden sm:inline-flex" onClick={() => window.history.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Review queue · Job #{job.id}</h1>
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Badge className={JOB_STATUS_BADGE[job.status]}>{job.status}</Badge>
              by {job.created_by_name}
              {job.provider_label ? ` · ${job.provider_label}` : ""}
              {" · "}
              <Link to="/imports" className="text-primary hover:underline">
                all imports
              </Link>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {job.error && <span className="max-w-64 truncate text-xs text-red-600" title={job.error}>{job.error}</span>}
          {canOperate && (
            <Button
              onClick={() => commitMutation.mutate()}
              disabled={acceptedCount === 0 || commitMutation.isPending}
            >
              {commitMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Commit {acceptedCount} accepted
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Images ({job.images.length})
          </h2>
          {job.images.length === 0 && <EmptyState title="No images in this job" />}
          {job.images.map((image) => (
            <ImageCard
              key={image.id}
              job={job}
              image={image}
              selected={image.id === selectedImageId}
              canOperate={canOperate}
              onSelect={() => setSelectedImageId(image.id)}
            />
          ))}
        </div>

        <div className="min-w-0 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              {selectedImage ? `Rows · ${selectedImage.filename}` : "Rows"}
            </h2>
            {canOperate && selectedImage && (
              <Button
                variant="outline"
                size="sm"
                disabled={acceptAllMutation.isPending || pendingRows.length === 0}
                onClick={() => acceptAllMutation.mutate()}
              >
                {acceptAllMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCheck className="h-4 w-4" />
                )}
                Accept all valid
              </Button>
            )}
          </div>
          {selectedImage && selectedImage.rows.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-2 py-2 font-semibold">VRN</th>
                    <th className="px-2 py-2 font-semibold">Model</th>
                    <th className="px-2 py-2 font-semibold">Entry date</th>
                    <th className="px-2 py-2 font-semibold">In</th>
                    <th className="px-2 py-2 font-semibold">Out date</th>
                    <th className="px-2 py-2 font-semibold">Out</th>
                    <th className="px-2 py-2 font-semibold">Status</th>
                    <th className="px-2 py-2 font-semibold">Remarks</th>
                    <th className="px-2 py-2 font-semibold">State</th>
                    {canOperate && <th className="px-2 py-2 font-semibold">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {selectedImage.rows.map((row) => (
                    <ReviewRow key={row.id} row={row} jobId={id} canOperate={canOperate} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title={selectedImage ? "No rows extracted" : "Select an image"}
              description={
                selectedImage?.status === "processing" || selectedImage?.status === "queued"
                  ? "Extraction in progress — rows will appear automatically."
                  : undefined
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
