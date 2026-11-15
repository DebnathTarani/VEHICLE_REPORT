import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Loader2, Plus, Save, Trash2, Pencil } from "lucide-react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@/lib/api";
import type { Entry, EntryCreate, Page, Status } from "@/lib/types";
import { useLocations } from "@/hooks/useLocations";
import { useAuth } from "@/context/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { formatVrn } from "@/lib/vrn";
import { formatDate, formatTime } from "@/lib/dates";
import { STATUS_BADGE, STATUS_LABELS, STATUSES } from "@/lib/constants";
import { rowToEntryCreate, validateEntryRow } from "@/lib/validation";
import { buildQuery } from "@/lib/api";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 10;

interface GridRow {
  key: string;
  vrn: string;
  model: string;
  entry_date: string;
  in_time: string;
  out_date: string;
  out_time: string;
  status: Status;
  remarks: string;
}

let rowSeq = 0;
function makeRow(overrides: Partial<GridRow> = {}): GridRow {
  rowSeq += 1;
  return {
    key: `row-${rowSeq}-${Date.now()}`,
    vrn: "",
    model: "",
    entry_date: "",
    in_time: "",
    out_date: "",
    out_time: "",
    status: "pending",
    remarks: "",
    ...overrides,
  };
}

const editSchema = z.object({
  vrn: z.string().min(1, "VRN is required"),
  model: z.string(),
  entry_date: z.string(),
  in_time: z.string(),
  out_date: z.string(),
  out_time: z.string(),
  status: z.enum(["work_done", "in_progress", "pending", "cancelled"]),
  remarks: z.string(),
});
type EditValues = z.infer<typeof editSchema>;

function toDraft(row: GridRow) {
  return {
    location_id: 0,
    sr_no: null,
    vrn: row.vrn,
    model: row.model,
    entry_date: row.entry_date,
    in_time: row.in_time,
    out_date: row.out_date,
    out_time: row.out_time,
    status: row.status,
    remarks: row.remarks,
  };
}

export function EntryPage() {
  const { canOperate, isAdmin } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  const { data: locations } = useLocations();
  const [locationId, setLocationId] = useState<number | null>(null);

  useEffect(() => {
    if (locationId != null || !locations?.length) return;
    const fromUrl = Number(searchParams.get("location_id"));
    if (fromUrl && locations.some((l) => l.id === fromUrl)) {
      setLocationId(fromUrl);
      return;
    }
    setLocationId(locations[0].id);
  }, [locations, locationId, searchParams]);

  const [rows, setRows] = useState<GridRow[]>(() => {
    const vrnParam = searchParams.get("vrn");
    return [makeRow(vrnParam ? { vrn: formatVrn(vrnParam) } : {})];
  });
  const firstCellRefs = useRef(new Map<string, HTMLInputElement>());

  const updateRow = useCallback((key: string, patch: Partial<GridRow>) => {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }, []);

  const appendRowAndFocus = useCallback(() => {
    setRows((prev) => {
      const next = [...prev, makeRow()];
      const created = next[next.length - 1];
      window.setTimeout(() => firstCellRefs.current.get(created.key)?.focus(), 0);
      return next;
    });
  }, []);

  const removeRow = useCallback((key: string) => {
    setRows((prev) => (prev.length === 1 ? [makeRow()] : prev.filter((r) => r.key !== key)));
  }, []);

  const bulkMutation = useMutation({
    mutationFn: (items: EntryCreate[]) =>
      api.post<{ created: number[] }>("/entries/bulk", { items }),
    onSuccess: (res) => {
      toast({
        title: `Saved ${res.created.length} ${res.created.length === 1 ? "entry" : "entries"}`,
        variant: "success",
      });
      setRows([makeRow()]);
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (err: Error) => toast({ title: "Save failed", description: err.message, variant: "destructive" }),
  });

  const onSaveAll = () => {
    if (locationId == null) {
      toast({ title: "Select a location first", variant: "destructive" });
      return;
    }
    const filled = rows.filter((r) => r.vrn.trim().length > 0);
    if (filled.length === 0) {
      toast({ title: "No rows with a VRN to save", variant: "destructive" });
      return;
    }
    const invalid: string[] = [];
    const items: EntryCreate[] = [];
    rows.forEach((row, index) => {
      if (!row.vrn.trim()) return;
      const draft = toDraft(row);
      const errors = validateEntryRow({ ...draft, location_id: locationId });
      if (Object.keys(errors).length > 0) {
        const first = Object.entries(errors)
          .map(([field, message]) => `row ${index + 1} · ${field}: ${message}`)
          .join("; ");
        invalid.push(first);
        return;
      }
      items.push(rowToEntryCreate({ ...draft, location_id: locationId }, locationId, index + 1));
    });
    if (invalid.length > 0) {
      toast({
        title: `${invalid.length} ${invalid.length === 1 ? "row has" : "rows have"} errors`,
        description: invalid.slice(0, 3).join(" | "),
        variant: "destructive",
      });
      return;
    }
    bulkMutation.mutate(items);
  };

  // ---- recent entries table ----
  const [page, setPage] = useState(1);
  const entriesQuery = useQuery({
    queryKey: ["entries", { locationId, page }],
    queryFn: () =>
      api.get<Page<Entry>>(`/entries${buildQuery({ location_id: locationId ?? undefined, page, page_size: PAGE_SIZE })}`),
    enabled: locationId != null,
  });

  const [editing, setEditing] = useState<Entry | null>(null);
  const [deleting, setDeleting] = useState<Entry | null>(null);

  const editForm = useForm<EditValues>({ resolver: zodResolver(editSchema) });

  const openEdit = (entry: Entry) => {
    setEditing(entry);
    editForm.reset({
      vrn: entry.vrn,
      model: entry.model ?? "",
      entry_date: entry.entry_date ?? "",
      in_time: entry.in_time ?? "",
      out_date: entry.out_date ?? "",
      out_time: entry.out_time ?? "",
      status: entry.status,
      remarks: entry.remarks ?? "",
    });
  };

  const patchMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<EntryCreate> }) =>
      api.patch<Entry>(`/entries/${id}`, payload),
    onSuccess: () => {
      toast({ title: "Entry updated", variant: "success" });
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError: (err: Error) =>
      toast({ title: "Update failed", description: err.message, variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del<{ ok: boolean }>(`/entries/${id}`),
    onSuccess: () => {
      toast({ title: "Entry deleted", variant: "success" });
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
    onError: (err: Error) =>
      toast({ title: "Delete failed", description: err.message, variant: "destructive" }),
  });

  const columns = useMemo<ColumnDef<Entry>[]>(
    () => [
      { header: "Sr", accessorKey: "sr_no", cell: (c) => (c.getValue<number | null>() ?? "—") },
      { header: "VRN", accessorKey: "vrn", cell: (c) => <span className="font-mono text-xs">{c.getValue<string>()}</span> },
      { header: "Model", accessorKey: "model", cell: (c) => (c.getValue<string | null>() ?? "—") },
      {
        header: "Entry",
        cell: (c) => {
          const e = c.row.original;
          return (
            <span className="whitespace-nowrap">
              {formatDate(e.entry_date)} {formatTime(e.in_time)}
            </span>
          );
        },
      },
      {
        header: "Exit",
        cell: (c) => {
          const e = c.row.original;
          return (
            <span className="whitespace-nowrap">
              {formatDate(e.out_date)} {formatTime(e.out_time)}
            </span>
          );
        },
      },
      {
        header: "Status",
        accessorKey: "status",
        cell: (c) => {
          const s = c.getValue<Status>();
          return <Badge className={STATUS_BADGE[s]}>{STATUS_LABELS[s]}</Badge>;
        },
      },
      { header: "Remarks", accessorKey: "remarks", cell: (c) => (
        <span className="line-clamp-1 max-w-40 text-muted-foreground">{c.getValue<string | null>() ?? ""}</span>
      ) },
      {
        id: "actions",
        header: "",
        cell: (c) => (
          <div className="flex justify-end gap-1">
            {canOperate && (
              <Button variant="ghost" size="icon" aria-label="Edit" onClick={() => openEdit(c.row.original)}>
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            {isAdmin && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete"
                className="text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                onClick={() => setDeleting(c.row.original)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        ),
      },
    ],
    [canOperate, isAdmin],
  );

  const table = useReactTable({
    data: entriesQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const totalPages = entriesQuery.data ? Math.max(1, Math.ceil(entriesQuery.data.total / PAGE_SIZE)) : 1;

  const gridInputClass =
    "h-8 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Entry</h1>
          <p className="text-sm text-muted-foreground">
            Spreadsheet-style entry sheet. Press Enter to add a row.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-52">
            <Label htmlFor="entry-location" className="mb-1 block">
              Location
            </Label>
            <Select
              id="entry-location"
              value={locationId ?? ""}
              onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Select location…</option>
              {locations?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
          </div>
          <Button variant="outline" onClick={appendRowAndFocus}>
            <Plus className="h-4 w-4" /> Add Row
          </Button>
          <Button onClick={onSaveAll} disabled={bulkMutation.isPending || !canOperate}>
            {bulkMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save All
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="w-12 px-3 py-2 font-semibold">Sr</th>
                  <th className="w-40 px-3 py-2 font-semibold">VRN *</th>
                  <th className="w-36 px-3 py-2 font-semibold">Model</th>
                  <th className="w-36 px-3 py-2 font-semibold">Entry date</th>
                  <th className="w-28 px-3 py-2 font-semibold">In time</th>
                  <th className="w-36 px-3 py-2 font-semibold">Out date</th>
                  <th className="w-28 px-3 py-2 font-semibold">Out time</th>
                  <th className="w-36 px-3 py-2 font-semibold">Status</th>
                  <th className="min-w-40 px-3 py-2 font-semibold">Remarks</th>
                  <th className="w-10 px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr
                    key={row.key}
                    className="border-b border-border last:border-0 hover:bg-muted/30"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !(e.target instanceof HTMLTextAreaElement) && !(e.target instanceof HTMLSelectElement)) {
                        e.preventDefault();
                        appendRowAndFocus();
                      }
                    }}
                  >
                    <td className="px-3 py-1.5 text-center text-muted-foreground">{index + 1}</td>
                    <td className="px-1.5 py-1.5">
                      <input
                        ref={(el) => {
                          if (el) firstCellRefs.current.set(row.key, el);
                          else firstCellRefs.current.delete(row.key);
                        }}
                        className={cn(gridInputClass, "font-mono")}
                        placeholder="AS-01-AB-1234"
                        value={row.vrn}
                        onChange={(e) => updateRow(row.key, { vrn: e.target.value })}
                        onBlur={(e) => updateRow(row.key, { vrn: formatVrn(e.target.value) })}
                        aria-label={`VRN row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        className={gridInputClass}
                        value={row.model}
                        onChange={(e) => updateRow(row.key, { model: e.target.value })}
                        aria-label={`Model row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        type="date"
                        className={gridInputClass}
                        value={row.entry_date}
                        onChange={(e) => updateRow(row.key, { entry_date: e.target.value })}
                        aria-label={`Entry date row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        type="time"
                        className={gridInputClass}
                        value={row.in_time}
                        onChange={(e) => updateRow(row.key, { in_time: e.target.value })}
                        aria-label={`In time row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        type="date"
                        className={gridInputClass}
                        value={row.out_date}
                        onChange={(e) => updateRow(row.key, { out_date: e.target.value })}
                        aria-label={`Out date row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        type="time"
                        className={gridInputClass}
                        value={row.out_time}
                        onChange={(e) => updateRow(row.key, { out_time: e.target.value })}
                        aria-label={`Out time row ${index + 1}`}
                      />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <select
                        className={cn(gridInputClass, "appearance-none pr-6")}
                        value={row.status}
                        onChange={(e) => updateRow(row.key, { status: e.target.value as Status })}
                        aria-label={`Status row ${index + 1}`}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {STATUS_LABELS[s]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-1.5 py-1.5">
                      <input
                        className={gridInputClass}
                        value={row.remarks}
                        onChange={(e) => updateRow(row.key, { remarks: e.target.value })}
                        aria-label={`Remarks row ${index + 1}`}
                      />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button
                        type="button"
                        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-red-600"
                        onClick={() => removeRow(row.key)}
                        aria-label={`Remove row ${index + 1}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent entries</CardTitle>
          <CardDescription>
            {locationId != null ? `Latest entries for the selected location` : "Select a location"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {entriesQuery.isPending && locationId != null && (
            <div className="space-y-2">
              <Skeleton className="h-9" />
              <Skeleton className="h-9" />
              <Skeleton className="h-9" />
            </div>
          )}
          {entriesQuery.data && entriesQuery.data.items.length === 0 && (
            <EmptyState title="No entries yet" description="Saved rows will appear here." />
          )}
          {entriesQuery.data && entriesQuery.data.items.length > 0 && (
            <>
              <Table>
                <TableHeader>
                  {table.getHeaderGroups().map((hg) => (
                    <TableRow key={hg.id}>
                      {hg.headers.map((h) => (
                        <TableHead key={h.id}>
                          {flexRender(h.column.columnDef.header, h.getContext())}
                        </TableHead>
                      ))}
                    </TableRow>
                  ))}
                </TableHeader>
                <TableBody>
                  {table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id}>
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Page {entriesQuery.data.page} of {totalPages} · {entriesQuery.data.total} total
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    <ChevronLeft className="h-4 w-4" /> Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Edit dialog */}
      <Dialog open={editing != null} onClose={() => setEditing(null)} className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Edit entry</DialogTitle>
          <DialogDescription>{editing?.vrn} · {editing?.location_name}</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={editForm.handleSubmit((values) => {
            if (editing == null) return;
            patchMutation.mutate({
              id: editing.id,
              payload: {
                vrn: formatVrn(values.vrn),
                model: values.model || null,
                entry_date: values.entry_date || null,
                in_time: values.in_time || null,
                out_date: values.out_date || null,
                out_time: values.out_time || null,
                status: values.status,
                remarks: values.remarks || null,
              },
            });
          })}
        >
          <DialogBody className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>VRN</Label>
              <Input
                className="font-mono"
                {...editForm.register("vrn", {
                  onBlur: (e) => editForm.setValue("vrn", formatVrn(e.target.value)),
                })}
                aria-invalid={!!editForm.formState.errors.vrn}
              />
              {editForm.formState.errors.vrn && (
                <p className="text-xs text-red-600">{editForm.formState.errors.vrn.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Model</Label>
              <Input {...editForm.register("model")} />
            </div>
            <div className="space-y-1.5">
              <Label>Entry date</Label>
              <Input type="date" {...editForm.register("entry_date")} />
            </div>
            <div className="space-y-1.5">
              <Label>In time</Label>
              <Input type="time" {...editForm.register("in_time")} />
            </div>
            <div className="space-y-1.5">
              <Label>Out date</Label>
              <Input type="date" {...editForm.register("out_date")} />
            </div>
            <div className="space-y-1.5">
              <Label>Out time</Label>
              <Input type="time" {...editForm.register("out_time")} />
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select {...editForm.register("status")}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Remarks</Label>
              <Input {...editForm.register("remarks")} />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={patchMutation.isPending}>
              {patchMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete dialog (admin only) */}
      <Dialog open={deleting != null} onClose={() => setDeleting(null)} className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete entry?</DialogTitle>
          <DialogDescription>
            {deleting?.vrn} at {deleting?.location_name}. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleting(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleting && deleteMutation.mutate(deleting.id)}
          >
            {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Delete
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
