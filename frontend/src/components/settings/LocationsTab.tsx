import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Location } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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

export function LocationsTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: locations, isPending } = useQuery({
    queryKey: ["locations"],
    queryFn: () => api.get<Location[]>("/locations"),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [name, setName] = useState("");
  const [active, setActive] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setActive(true);
    setFormError(null);
    setOpen(true);
  };

  const openEdit = (l: Location) => {
    setEditing(l);
    setName(l.name);
    setActive(l.is_active);
    setFormError(null);
    setOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      if (editing) {
        return api.patch<Location>(`/locations/${editing.id}`, { name, is_active: active });
      }
      return api.post<Location>("/locations", { name });
    },
    onSuccess: () => {
      toast({ title: editing ? "Location updated" : "Location created", variant: "success" });
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["locations"] });
    },
    onError: (err: Error) => setFormError(err.message),
  });

  if (isPending) return <Skeleton className="h-40" />;

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> New location
        </Button>
      </div>

      {!locations?.length && <EmptyState title="No locations yet" description="Create your first workshop location." />}

      {locations && locations.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {locations.map((l) => (
              <TableRow key={l.id}>
                <TableCell className="text-muted-foreground">{l.id}</TableCell>
                <TableCell className="font-medium">{l.name}</TableCell>
                <TableCell>
                  {l.is_active ? (
                    <Badge variant="success">active</Badge>
                  ) : (
                    <Badge variant="destructive">inactive</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(l)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} className="max-w-md">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit location · ${editing.name}` : "New location"}</DialogTitle>
          <DialogDescription>Locations group entries, users and reports.</DialogDescription>
        </DialogHeader>
        <DialogBody>
          {formError && (
            <p className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
              {formError}
            </p>
          )}
          <div className="space-y-1.5">
            <Label>Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          {editing && (
            <div className="flex items-center gap-2">
              <Checkbox id="loc-active" checked={active} onChange={(e) => setActive(e.target.checked)} />
              <Label htmlFor="loc-active">Active</Label>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (!name.trim()) return setFormError("Name is required");
              saveMutation.mutate();
            }}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {editing ? "Save changes" : "Create location"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
