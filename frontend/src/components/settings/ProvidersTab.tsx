import { Fragment, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import type { Provider, ProviderCreate, ProviderTestResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { VISION_BADGE, VISION_LABELS } from "@/lib/constants";

const providerSchema = z.object({
  name: z.string().min(1, "Name is required"),
  kind: z.enum(["openai", "gemini"]),
  base_url: z.string(),
  api_key: z.string(),
  default_model: z.string().min(1, "Default model is required"),
  enabled: z.boolean(),
  supports_guided_json: z.boolean(),
  disable_thinking: z.boolean(),
});
type ProviderForm = z.infer<typeof providerSchema>;

const emptyForm: ProviderForm = {
  name: "",
  kind: "openai",
  base_url: "",
  api_key: "",
  default_model: "",
  enabled: true,
  supports_guided_json: false,
  disable_thinking: false,
};

function ProviderDialog({
  open,
  onClose,
  editing,
}: {
  open: boolean;
  onClose: () => void;
  editing: Provider | null;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const form = useForm<ProviderForm>({
    resolver: zodResolver(providerSchema),
    defaultValues: emptyForm,
  });

  useEffect(() => {
    if (!open) return;
    form.reset(
      editing
        ? {
            name: editing.name,
            kind: editing.kind,
            base_url: editing.base_url ?? "",
            api_key: "",
            default_model: editing.default_model,
            enabled: editing.enabled,
            supports_guided_json: editing.supports_guided_json,
            disable_thinking: editing.disable_thinking,
          }
        : emptyForm,
    );
  }, [open, editing, form]);

  const saveMutation = useMutation({
    mutationFn: (values: ProviderForm) => {
      const base = {
        name: values.name,
        kind: values.kind,
        base_url: values.base_url || null,
        default_model: values.default_model,
        enabled: values.enabled,
        supports_guided_json: values.supports_guided_json,
        disable_thinking: values.disable_thinking,
      };
      if (editing) {
        return api.patch<Provider>(`/settings/providers/${editing.id}`, {
          ...base,
          ...(values.api_key ? { api_key: values.api_key } : {}),
        });
      }
      const create: ProviderCreate = {
        name: values.name,
        kind: values.kind,
        base_url: values.base_url || null,
        default_model: values.default_model,
        ...(values.api_key ? { api_key: values.api_key } : {}),
      };
      return api.post<Provider>("/settings/providers", create);
    },
    onSuccess: () => {
      toast({ title: editing ? "Provider updated" : "Provider created", variant: "success" });
      onClose();
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
    onError: (err: Error) =>
      toast({ title: "Save failed", description: err.message, variant: "destructive" }),
  });

  return (
    <Dialog open={open} onClose={onClose} className="max-w-lg">
      <DialogHeader>
        <DialogTitle>{editing ? `Edit provider · ${editing.name}` : "New provider"}</DialogTitle>
        <DialogDescription>
          {editing
            ? "Leave API key blank to keep the stored key."
            : "Register an OpenAI-compatible or Gemini provider."}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={form.handleSubmit((v) => saveMutation.mutate(v))}>
        <DialogBody className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Name *</Label>
            <Input {...form.register("name")} aria-invalid={!!form.formState.errors.name} />
            {form.formState.errors.name && (
              <p className="text-xs text-red-600">{form.formState.errors.name.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label>Kind</Label>
            <Select {...form.register("kind")}>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
            </Select>
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label>Base URL</Label>
            <Input
              placeholder="https://api.openai.com/v1"
              {...form.register("base_url")}
            />
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label>API key {editing ? "(write-only)" : "*"}</Label>
            <Input
              type="password"
              autoComplete="new-password"
              placeholder={
                editing ? `${editing.api_key_masked ?? "stored key"} — leave blank to keep` : "sk-…"
              }
              {...form.register("api_key")}
            />
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label>Default model *</Label>
            <Input placeholder="gpt-4o-mini" {...form.register("default_model")} />
            {form.formState.errors.default_model && (
              <p className="text-xs text-red-600">
                {form.formState.errors.default_model.message}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="p-enabled" {...form.register("enabled")} />
            <Label htmlFor="p-enabled">Enabled</Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="p-guided" {...form.register("supports_guided_json")} />
            <Label htmlFor="p-guided">Supports guided JSON</Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="p-thinking" {...form.register("disable_thinking")} />
            <Label htmlFor="p-thinking">Disable thinking</Label>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={saveMutation.isPending}>
            {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {editing ? "Save changes" : "Create provider"}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

export function ProvidersTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Provider | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Provider | null>(null);
  const [testResults, setTestResults] = useState<Record<number, ProviderTestResult>>({});
  const [testingId, setTestingId] = useState<number | null>(null);

  const { data: providers, isPending } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.get<Provider[]>("/settings/providers"),
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["providers"] });

  const testMutation = useMutation({
    mutationFn: (id: number) => api.post<ProviderTestResult>(`/settings/providers/${id}/test`),
    onMutate: (id) => setTestingId(id),
    onSuccess: (result, id) => {
      setTestResults((prev) => ({ ...prev, [id]: result }));
      invalidate();
    },
    onError: (err: Error, id) => {
      setTestResults((prev) => ({
        ...prev,
        [id]: { ok: false, message: err.message, models: [], vision: "unknown" },
      }));
    },
    onSettled: () => setTestingId(null),
  });

  const defaultMutation = useMutation({
    mutationFn: (id: number) => api.post<{ ok: boolean }>(`/settings/providers/${id}/default`),
    onSuccess: () => {
      toast({ title: "Default provider set", variant: "success" });
      invalidate();
    },
    onError: (err: Error) =>
      toast({ title: "Could not set default", description: err.message, variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del<{ ok: boolean }>(`/settings/providers/${id}`),
    onSuccess: () => {
      toast({ title: "Provider deleted", variant: "success" });
      setDeleteTarget(null);
      invalidate();
    },
    onError: (err: Error) =>
      toast({ title: "Delete failed", description: err.message, variant: "destructive" }),
  });

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (p: Provider) => {
    setEditing(p);
    setDialogOpen(true);
  };

  if (isPending) return <Skeleton className="h-48" />;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> New provider
        </Button>
      </div>

      {!providers?.length && (
        <EmptyState title="No providers" description="Add an OpenAI or Gemini provider to enable AI imports." />
      )}

      {providers && providers.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Default</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Kind</TableHead>
              <TableHead>Base URL</TableHead>
              <TableHead>API key</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Vision</TableHead>
              <TableHead>Flags</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {providers.map((p) => {
              const result = testResults[p.id];
              return (
                <Fragment key={p.id}>
                  <TableRow>
                    <TableCell>
                      <input
                        type="radio"
                        name="default-provider"
                        checked={p.is_default}
                        disabled={defaultMutation.isPending}
                        onChange={() => defaultMutation.mutate(p.id)}
                        aria-label={`Set ${p.name} as default`}
                        className="h-4 w-4 cursor-pointer accent-primary"
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      {p.name}
                      {!p.enabled && <span className="ml-2 text-xs text-muted-foreground">(disabled)</span>}
                    </TableCell>
                    <TableCell className="uppercase">{p.kind}</TableCell>
                    <TableCell className="max-w-44 truncate text-muted-foreground">
                      {p.base_url ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {p.api_key_masked ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{p.default_model}</TableCell>
                    <TableCell>
                      <Badge className={VISION_BADGE[p.vision_status]}>{VISION_LABELS[p.vision_status]}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 text-[10px]">
                        {p.supports_guided_json && <Badge variant="outline">guided</Badge>}
                        {p.disable_thinking && <Badge variant="outline">no-think</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Test"
                          disabled={testMutation.isPending}
                          onClick={() => testMutation.mutate(p.id)}
                        >
                          {testingId === p.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8" title="Edit" onClick={() => openEdit(p)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600"
                          title="Delete"
                          onClick={() => setDeleteTarget(p)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {result && (
                    <tr className="border-b border-border bg-muted/40">
                      <td colSpan={9} className="px-3 py-3">
                        <Alert variant={result.ok ? "info" : "destructive"}>
                          <AlertTitle>
                            Test {result.ok ? "passed" : "failed"} — {result.message}
                          </AlertTitle>
                          <AlertDescription className="flex flex-wrap items-center gap-1.5 pt-1">
                            {result.models.map((m) => (
                              <Badge key={m} variant="secondary" className="font-mono text-[10px]">
                                {m}
                              </Badge>
                            ))}
                            <Badge className={VISION_BADGE[result.vision]}>{VISION_LABELS[result.vision]}</Badge>
                          </AlertDescription>
                        </Alert>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      )}

      <ProviderDialog key={editing?.id ?? "new"} open={dialogOpen} onClose={() => setDialogOpen(false)} editing={editing} />

      <Dialog open={deleteTarget != null} onClose={() => setDeleteTarget(null)} className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete provider?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.name} will be removed. Imports can still use the default provider.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Delete
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
