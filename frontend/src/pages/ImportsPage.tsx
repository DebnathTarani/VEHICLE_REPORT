import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ImagePlus, Loader2, UploadCloud, X } from "lucide-react";
import { api, buildQuery } from "@/lib/api";
import type { ImportJobCreateResult, ImportJobSummary, Page, Provider } from "@/lib/types";
import { useAuth } from "@/context/auth";
import { useLocations } from "@/hooks/useLocations";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  Dialog,
  DialogBody,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { JOB_STATUS_BADGE } from "@/lib/constants";
import { formatDateTime } from "@/lib/dates";

const MAX_FILES = 20;

function NewImportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const { data: locations } = useLocations(open);
  const { data: providers } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.get<Provider[]>("/settings/providers"),
    enabled: open && isAdmin,
  });

  const [files, setFiles] = useState<File[]>([]);
  const [providerId, setProviderId] = useState<string>("");
  const [locationId, setLocationId] = useState<string>("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const images = Array.from(incoming).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => {
      const merged = [...prev];
      for (const f of images) {
        if (merged.length >= MAX_FILES) {
          toast({ title: `Only ${MAX_FILES} images per job`, variant: "destructive" });
          break;
        }
        if (!merged.some((existing) => existing.name === f.name && existing.size === f.size)) {
          merged.push(f);
        }
      }
      return merged;
    });
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const createMutation = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      if (providerId) form.append("provider_id", providerId);
      if (locationId) form.append("location_id", locationId);
      return api.postForm<ImportJobCreateResult>("/imports", form);
    },
    onSuccess: (res) => {
      toast({ title: "Import job created", description: `Job #${res.job_id} queued`, variant: "success" });
      onClose();
      setFiles([]);
      void navigate(`/imports/${res.job_id}`);
    },
    onError: (err: Error) =>
      toast({ title: "Import failed", description: err.message, variant: "destructive" }),
  });

  return (
    <Dialog open={open} onClose={onClose} className="max-w-xl">
      <DialogHeader>
        <DialogTitle>New Import</DialogTitle>
        <DialogDescription>Upload up to {MAX_FILES} images for AI extraction and review.</DialogDescription>
      </DialogHeader>
      <DialogBody>
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
            dragOver ? "border-primary bg-accent" : "border-border hover:border-primary/50"
          }`}
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm font-medium">Drag &amp; drop images here, or click to browse</p>
          <p className="text-xs text-muted-foreground">image/* · up to {MAX_FILES} files</p>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>
        {files.length > 0 && (
          <ul className="max-h-40 space-y-1 overflow-auto rounded-md border border-border p-2">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">
                  {f.name} <span className="text-muted-foreground">({Math.round(f.size / 1024)} KB)</span>
                </span>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-red-600"
                  onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                  aria-label={`Remove ${f.name}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="grid grid-cols-2 gap-4">
          {isAdmin && (
            <div className="space-y-1.5">
              <Label>Provider (optional)</Label>
              <Select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
                <option value="">Auto (default)</option>
                {providers?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.kind}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Location (optional)</Label>
            <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Ask at review</option>
              {locations
                ?.filter((l) => l.is_active)
                .map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
            </Select>
          </div>
        </div>
      </DialogBody>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => createMutation.mutate()} disabled={files.length === 0 || createMutation.isPending}>
          {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
          Start import
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

export function ImportsPage() {
  const { canOperate } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const pageSize = 15;

  const { data, isPending } = useQuery({
    queryKey: ["imports", page],
    queryFn: () => api.get<Page<ImportJobSummary>>(`/imports${buildQuery({ page, page_size: pageSize })}`),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((j) => j.status === "queued" || j.status === "processing") ? 3000 : false;
    },
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Imports</h1>
          <p className="text-sm text-muted-foreground">AI image imports awaiting review and commit.</p>
        </div>
        {canOperate && <Button onClick={() => setDialogOpen(true)}><ImagePlus className="h-4 w-4" /> New Import</Button>}
      </div>

      {isPending && (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      )}
      {data && data.items.length === 0 && (
        <EmptyState title="No imports yet" description="Create an import job to extract entries from images." />
      )}
      {data && data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>By</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Rows</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((job) => (
                <TableRow
                  key={job.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/imports/${job.id}`)}
                >
                  <TableCell className="font-medium">#{job.id}</TableCell>
                  <TableCell>
                    <Badge className={JOB_STATUS_BADGE[job.status]}>{job.status}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDateTime(job.created_at)}
                  </TableCell>
                  <TableCell>{job.created_by_name}</TableCell>
                  <TableCell>{job.provider_label ?? "—"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1.5 text-xs">
                      <Badge variant="warning">{job.row_counts.pending_review} pending</Badge>
                      <Badge variant="default">{job.row_counts.accepted} accepted</Badge>
                      <Badge variant="destructive">{job.row_counts.rejected} rejected</Badge>
                      <Badge variant="success">{job.row_counts.committed} committed</Badge>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Page {data.page} of {totalPages} · {data.total} jobs
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Prev
              </Button>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      <NewImportDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}
