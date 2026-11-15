import { useQuery } from "@tanstack/react-query";
import { Activity, CalendarDays, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatTime } from "@/lib/dates";
import { STATUS_BADGE, STATUS_LABELS } from "@/lib/constants";

function ageBadgeClass(ageDays: number): string {
  if (ageDays > 7) return "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  if (ageDays > 3) return "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300";
}

function WeekChart({ series }: { series: DashboardSummary["week_series"] }) {
  const max = Math.max(1, ...series.map((p) => p.count));
  return (
    <div className="flex h-44 items-end gap-2 pt-4">
      {series.map((point) => (
        <div key={point.date} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          <span className="text-[11px] font-medium text-muted-foreground">{point.count}</span>
          <div
            className="w-full max-w-10 rounded-t-md bg-primary/80 transition-all hover:bg-primary"
            style={{ height: `${Math.max(2, Math.round((point.count / max) * 100))}%` }}
            title={`${point.date}: ${point.count}`}
          />
          <span className="text-[11px] text-muted-foreground">{point.date.slice(8)}</span>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary"),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {data ? `Live snapshot for ${formatDate(data.date)}` : "Live workshop snapshot"}
        </p>
      </div>

      {isPending && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}
      {isError && (
        <EmptyState title="Could not load dashboard" description={(error as Error)?.message} />
      )}

      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.per_location.map((loc) => (
              <Card key={loc.location_id}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-primary" />
                    {loc.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-2xl font-bold">{loc.entries_today}</div>
                    <div className="text-xs text-muted-foreground">Entries today</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                      {loc.open_wip}
                    </div>
                    <div className="text-xs text-muted-foreground">Open WIP</div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {data.per_location.length === 0 && (
              <EmptyState className="sm:col-span-2 lg:col-span-3" title="No locations configured" />
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4 text-primary" /> Entries — last 7 days
                </CardTitle>
                <CardDescription>Total entries created per day</CardDescription>
              </CardHeader>
              <CardContent>
                <WeekChart series={data.week_series} />
              </CardContent>
            </Card>

            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" /> Open work in progress
                </CardTitle>
                <CardDescription>In-progress jobs, oldest first</CardDescription>
              </CardHeader>
              <CardContent>
                {data.open_wip.length === 0 ? (
                  <EmptyState title="Nothing pending" description="All work items are closed." />
                ) : (
                  <div className="max-h-96 overflow-auto rounded-lg border border-border">
                    <Table className="border-0">
                      <TableHeader>
                        <TableRow>
                          <TableHead>VRN</TableHead>
                          <TableHead>Model</TableHead>
                          <TableHead>Location</TableHead>
                          <TableHead>Entry</TableHead>
                          <TableHead>In</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Age</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.open_wip.map((entry) => (
                          <TableRow key={entry.id}>
                            <TableCell className="font-mono text-xs font-medium">{entry.vrn}</TableCell>
                            <TableCell>{entry.model ?? "—"}</TableCell>
                            <TableCell>{entry.location_name}</TableCell>
                            <TableCell>{formatDate(entry.entry_date)}</TableCell>
                            <TableCell>{formatTime(entry.in_time)}</TableCell>
                            <TableCell>
                              <Badge className={STATUS_BADGE[entry.status]}>
                                {STATUS_LABELS[entry.status]}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <Badge className={ageBadgeClass(entry.age_days)}>{entry.age_days}d</Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
