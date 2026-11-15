import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, Loader2, Mail } from "lucide-react";
import { api, apiUrl, buildQuery } from "@/lib/api";
import type { MessageResponse, Status } from "@/lib/types";
import { useAuth } from "@/context/auth";
import { useLocations } from "@/hooks/useLocations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toaster";
import { STATUS_LABELS, STATUSES } from "@/lib/constants";

interface Filters {
  date_from: string;
  date_to: string;
  location_id: string;
  status: string;
}

const emptyFilters: Filters = { date_from: "", date_to: "", location_id: "", status: "" };

export function ReportsPage() {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const { data: locations } = useLocations();
  const [filters, setFilters] = useState<Filters>(emptyFilters);

  const set = (patch: Partial<Filters>) => setFilters((prev) => ({ ...prev, ...patch }));

  const downloadUrl = apiUrl(
    `/exports/entries.xlsx${buildQuery({
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      location_id: filters.location_id ? Number(filters.location_id) : undefined,
      status: (filters.status || undefined) as Status | undefined,
    })}`,
  );

  const emailMutation = useMutation({
    mutationFn: () =>
      api.post<MessageResponse>("/exports/email-report", {
        date: filters.date_from || undefined,
      }),
    onSuccess: (res) =>
      toast({ title: "Report sent", description: res.message, variant: "success" }),
    onError: (err: Error) =>
      toast({ title: "Email failed", description: err.message, variant: "destructive" }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Filter entries and export to Excel, or email the daily report.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Applied to both the Excel download and the email report.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
            onSubmit={(e) => e.preventDefault()}
          >
            <div className="space-y-1.5">
              <Label htmlFor="date-from">From</Label>
              <Input
                id="date-from"
                type="date"
                value={filters.date_from}
                onChange={(e) => set({ date_from: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date-to">To</Label>
              <Input
                id="date-to"
                type="date"
                value={filters.date_to}
                onChange={(e) => set({ date_to: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="report-location">Location</Label>
              <Select
                id="report-location"
                value={filters.location_id}
                onChange={(e) => set({ location_id: e.target.value })}
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
              <Label htmlFor="report-status">Status</Label>
              <Select
                id="report-status"
                value={filters.status}
                onChange={(e) => set({ status: e.target.value })}
              >
                <option value="">All statuses</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </Select>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Export</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <a href={downloadUrl} download>
            <Button>
              <Download className="h-4 w-4" /> Download Excel
            </Button>
          </a>
          {isAdmin && (
            <Button
              variant="secondary"
              disabled={emailMutation.isPending}
              onClick={() => emailMutation.mutate()}
            >
              {emailMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Mail className="h-4 w-4" />
              )}
              Email report now
            </Button>
          )}
          <span className="text-xs text-muted-foreground">
            Excel uses current filters; email defaults to today.
          </span>
        </CardContent>
      </Card>
    </div>
  );
}
