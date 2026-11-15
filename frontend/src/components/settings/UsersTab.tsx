import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Role, User } from "@/lib/types";
import { useLocations } from "@/hooks/useLocations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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

interface UserFormState {
  username: string;
  display_name: string;
  role: Role;
  location_id: string;
  password: string;
  is_active: boolean;
}

const emptyUser: UserFormState = {
  username: "",
  display_name: "",
  role: "operator",
  location_id: "",
  password: "",
  is_active: true,
};

export function UsersTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: users, isPending } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<User[]>("/users"),
  });
  const { data: locations } = useLocations();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyUser);
  const [formError, setFormError] = useState<string | null>(null);

  const locationName = (id: number | null) =>
    locations?.find((l) => l.id === id)?.name ?? "—";

  const openCreate = () => {
    setEditing(null);
    setForm(emptyUser);
    setFormError(null);
    setOpen(true);
  };

  const openEdit = (u: User) => {
    setEditing(u);
    setForm({
      username: u.username,
      display_name: u.display_name,
      role: u.role,
      location_id: u.location_id != null ? String(u.location_id) : "",
      password: "",
      is_active: u.is_active,
    });
    setFormError(null);
    setOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: (values: UserFormState) => {
      const location_id = values.location_id ? Number(values.location_id) : null;
      if (editing) {
        return api.patch<User>(`/users/${editing.id}`, {
          display_name: values.display_name,
          role: values.role,
          location_id,
          is_active: values.is_active,
          ...(values.password ? { password: values.password } : {}),
        });
      }
      return api.post<User>("/users", {
        username: values.username,
        display_name: values.display_name,
        password: values.password,
        role: values.role,
        location_id,
      });
    },
    onSuccess: () => {
      toast({ title: editing ? "User updated" : "User created", variant: "success" });
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const submit = () => {
    if (!form.username.trim()) return setFormError("Username is required");
    if (!form.display_name.trim()) return setFormError("Display name is required");
    if (!editing && !form.password) return setFormError("Password is required for new users");
    setFormError(null);
    saveMutation.mutate(form);
  };

  if (isPending) return <Skeleton className="h-48" />;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> New user
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Username</TableHead>
            <TableHead>Display name</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Active</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users?.map((u) => (
            <TableRow key={u.id}>
              <TableCell className="font-medium">{u.username}</TableCell>
              <TableCell>{u.display_name}</TableCell>
              <TableCell>
                <Badge variant={u.role === "admin" ? "default" : "secondary"} className="capitalize">
                  {u.role}
                </Badge>
              </TableCell>
              <TableCell>{locationName(u.location_id)}</TableCell>
              <TableCell>
                {u.is_active ? (
                  <Badge variant="success">active</Badge>
                ) : (
                  <Badge variant="destructive">disabled</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(u)}>
                  <Pencil className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={open} onClose={() => setOpen(false)} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit user · ${editing.username}` : "New user"}</DialogTitle>
          <DialogDescription>
            {editing ? "Update details. Leave password blank to keep the current one." : "Operators enter data; viewers are read-only."}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="grid grid-cols-2 gap-4">
          {formError && (
            <p className="col-span-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
              {formError}
            </p>
          )}
          <div className="space-y-1.5">
            <Label>Username *</Label>
            <Input
              value={form.username}
              disabled={!!editing}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Display name *</Label>
            <Input
              value={form.display_name}
              onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <Select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as Role }))}
            >
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Location</Label>
            <Select
              value={form.location_id}
              onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))}
            >
              <option value="">All locations</option>
              {locations?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Password {editing ? "(blank = keep)" : "*"}</Label>
            <Input
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
          </div>
          <div className="flex items-center gap-2 pt-6">
            <Checkbox
              id="user-active"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            />
            <Label htmlFor="user-active">Active</Label>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={saveMutation.isPending}>
            {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {editing ? "Save changes" : "Create user"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
