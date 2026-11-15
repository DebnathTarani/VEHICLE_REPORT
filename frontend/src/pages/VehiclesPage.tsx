import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, buildQuery } from "@/lib/api";
import type { VehicleSearchResult } from "@/lib/types";
import { useDebounce } from "@/hooks/useDebounce";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDate } from "@/lib/dates";

export function VehiclesPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const debounced = useDebounce(query.trim(), 300);

  const { data, isPending } = useQuery({
    queryKey: ["vehicles", debounced],
    queryFn: () => api.get<VehicleSearchResult>(`/vehicles${buildQuery({ q: debounced, limit: 20 })}`),
    enabled: debounced.length >= 2,
  });

  const rows = data?.items ?? [];
  const showEmpty = debounced.length >= 2 && data != null && rows.length === 0;

  const subtitle = useMemo(() => {
    if (debounced.length < 2) return "Type at least 2 characters of a VRN (e.g. AS01 or AS-01-AB).";
    return `Exact prefix or substring matches on normalized VRN.`;
  }, [debounced]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Vehicles</h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search VRN…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      {debounced.length >= 2 && isPending && (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      )}
      {showEmpty && (
        <EmptyState title="No vehicles found" description={`Nothing matches "${debounced}".`} />
      )}
      {rows.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <Table className="border-0">
              <TableHeader>
                <TableRow>
                  <TableHead>VRN</TableHead>
                  <TableHead>Last model</TableHead>
                  <TableHead className="text-right">Visits</TableHead>
                  <TableHead>First seen</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((v) => (
                  <TableRow
                    key={v.vrn_normalized}
                    className="cursor-pointer"
                    onClick={() => navigate(`/vehicles/${v.vrn_normalized}`)}
                  >
                    <TableCell className="font-mono text-sm font-medium text-primary">
                      {v.display_vrn}
                    </TableCell>
                    <TableCell>{v.model_last ?? "—"}</TableCell>
                    <TableCell className="text-right">{v.visits}</TableCell>
                    <TableCell>{formatDate(v.first_seen)}</TableCell>
                    <TableCell>{formatDate(v.last_seen)}</TableCell>
                    <TableCell className="text-right">
                      {v.open_entries > 0 ? (
                        <Badge variant="warning">{v.open_entries} open</Badge>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
