import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { GeneralSettings } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toaster";

export function GeneralTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data, isPending } = useQuery({
    queryKey: ["settings-general"],
    queryFn: () => api.get<GeneralSettings>("/settings/general"),
  });

  const [dateFormat, setDateFormat] = useState("DD-MM-YYYY");
  const [rcLookup, setRcLookup] = useState(false);

  useEffect(() => {
    if (!data) return;
    setDateFormat(data.display_date_format);
    setRcLookup(data.rc_lookup_enabled);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put<GeneralSettings>("/settings/general", {
        display_date_format: dateFormat,
        rc_lookup_enabled: rcLookup,
      }),
    onSuccess: () => {
      toast({ title: "General settings saved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["settings-general"] });
    },
    onError: (err: Error) =>
      toast({ title: "Save failed", description: err.message, variant: "destructive" }),
  });

  if (isPending) return <Skeleton className="h-40" />;

  return (
    <div className="max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
          <CardDescription>Display and lookup options.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Display date format</Label>
            <Input
              value={dateFormat}
              onChange={(e) => setDateFormat(e.target.value)}
              placeholder="DD-MM-YYYY"
            />
            <p className="text-xs text-muted-foreground">Tokens: DD, MM, YYYY (e.g. DD/MM/YYYY)</p>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="rc-lookup"
              checked={rcLookup}
              onChange={(e) => setRcLookup(e.target.checked)}
            />
            <Label htmlFor="rc-lookup">Enable RC lookup (registration certificate enrichment)</Label>
          </div>
          <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Save settings
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
