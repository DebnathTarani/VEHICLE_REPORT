import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ClipboardList } from "lucide-react";
import { api } from "@/lib/api";
import type { VehicleTimeline } from "@/lib/types";
import { useAuth } from "@/context/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatDate, formatTime } from "@/lib/dates";
import { STATUS_BADGE, STATUS_LABELS } from "@/lib/constants";

function FlagBadges({ flags, durationHours }: { flags?: string[]; durationHours: number | null }) {
  const items: { key: string; label: string; className: string }[] = [];
  const effectiveFlags = new Set(flags ?? []);
  if (durationHours != null && durationHours < 0) effectiveFlags.add("negative_duration");
  for (const flag of effectiveFlags) {
    if (flag === "negative_duration") {
      items.push({ key: flag, label: "negative duration", className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" });
    } else if (flag === "open_record") {
      items.push({ key: flag, label: "open record", className: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300" });
    } else {
      items.push({ key: flag, label: flag.replace(/_/g, " "), className: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300" });
    }
  }
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((i) => (
        <span key={i.key} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${i.className}`}>
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function VehicleTimelinePage() {
  const { vrnNormalized } = useParams<{ vrnNormalized: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data, isPending, isError } = useQuery({
    queryKey: ["vehicle-timeline", vrnNormalized],
    queryFn: () => api.get<VehicleTimeline>(`/vehicles/${vrnNormalized}/timeline`),
    enabled: !!vrnNormalized,
  });

  const openInEntry = () => {
    const params = new URLSearchParams({ vrn: data?.display_vrn ?? vrnNormalized ?? "" });
    if (user?.location_id) params.set("location_id", String(user.location_id));
    navigate(`/entry?${params.toString()}`);
  };

  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Vehicle not found"
        description="No timeline available for this VRN."
        action={
          <Button variant="outline" onClick={() => navigate("/vehicles")}>
            Back to search
          </Button>
        }
      />
    );
  }

  const openCount = data.entries.filter(
    (e) => (e.flags ?? []).includes("open_record") || (!e.out_date && !e.out_time && e.status !== "cancelled"),
  ).length;
  const firstSeen = data.entries[data.entries.length - 1]?.entry_date ?? null;
  const lastSeen = data.entries[0]?.entry_date ?? null;
  const lastModel = data.entries.find((e) => e.model)?.model ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/vehicles")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="font-mono text-2xl font-bold tracking-tight">{data.display_vrn}</h1>
          <p className="text-sm text-muted-foreground">Visit timeline</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Vehicle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="text-lg font-semibold">{lastModel ?? "Unknown model"}</div>
            <div className="font-mono text-xs text-muted-foreground">{data.vrn_normalized}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Activity</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-xl font-bold">{data.entries.length}</div>
              <div className="text-xs text-muted-foreground">Visits</div>
            </div>
            <div>
              <div className="text-xl font-bold text-amber-600 dark:text-amber-400">{openCount}</div>
              <div className="text-xs text-muted-foreground">Open records</div>
            </div>
            <div className="col-span-2 flex gap-4 text-xs text-muted-foreground">
              <span>First: <span className="text-foreground">{formatDate(firstSeen) || "—"}</span></span>
              <span>Last: <span className="text-foreground">{formatDate(lastSeen) || "—"}</span></span>
            </div>
          </CardContent>
        </Card>
        <Card className="md:col-span-2 xl:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={openInEntry} className="w-full">
              <ClipboardList className="h-4 w-4" /> New entry with this VRN
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Entries (newest first)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.entries.length === 0 && <EmptyState title="No visits recorded" />}
          {data.entries.map((entry) => (
            <div
              key={entry.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border p-4"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">
                    {formatDate(entry.entry_date)} <span className="text-muted-foreground">from {formatTime(entry.in_time) || "—"}</span>
                  </span>
                  {entry.out_date && (
                    <span className="text-sm text-muted-foreground">
                      → {formatDate(entry.out_date)} {formatTime(entry.out_time) || ""}
                    </span>
                  )}
                  <Badge className={STATUS_BADGE[entry.status]}>{STATUS_LABELS[entry.status]}</Badge>
                  {entry.duration_hours != null && (
                    <Badge variant="secondary" className={entry.duration_hours < 0 ? "text-red-600" : ""}>
                      {entry.duration_hours.toFixed(1)} h
                    </Badge>
                  )}
                  {entry.source === "ai_import" && <Badge variant="outline">AI import</Badge>}
                </div>
                <div className="text-sm text-muted-foreground">
                  {entry.location_name}
                  {entry.model ? ` · ${entry.model}` : ""}
                  {entry.remarks ? ` · ${entry.remarks}` : ""}
                </div>
              </div>
              <FlagBadges flags={entry.flags} durationHours={entry.duration_hours} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
