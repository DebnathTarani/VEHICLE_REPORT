import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";
import { api } from "@/lib/api";
import type { EmailSettings } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toaster";

export function EmailTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data, isPending } = useQuery({
    queryKey: ["settings-email"],
    queryFn: () => api.get<EmailSettings>("/settings/email"),
  });

  const [enabled, setEnabled] = useState(false);
  const [recipients, setRecipients] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("587");
  const [username, setUsername] = useState("");
  const [useTls, setUseTls] = useState(true);
  const [fromAddress, setFromAddress] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!data) return;
    setEnabled(data.enabled);
    setRecipients(data.recipients.join("\n"));
    setScheduleTime(data.schedule_time ?? "");
    setHost(data.smtp.host ?? "");
    setPort(String(data.smtp.port));
    setUsername(data.smtp.username ?? "");
    setUseTls(data.smtp.use_tls);
    setFromAddress(data.smtp.from_address ?? "");
    setPassword("");
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsedRecipients = recipients
        .split(/[\n,]/)
        .map((r) => r.trim())
        .filter(Boolean);
      return api.put<EmailSettings>("/settings/email", {
        enabled,
        recipients: parsedRecipients,
        schedule_time: scheduleTime || null,
        smtp: {
          host: host || null,
          port: Number(port) || 587,
          username: username || null,
          use_tls: useTls,
          from_address: fromAddress || null,
          ...(password ? { password } : {}),
        },
      });
    },
    onSuccess: () => {
      setPassword("");
      toast({ title: "Email settings saved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["settings-email"] });
    },
    onError: (err: Error) =>
      toast({ title: "Save failed", description: err.message, variant: "destructive" }),
  });

  const testMutation = useMutation({
    mutationFn: () => api.post<{ ok: boolean; message: string }>("/settings/email/test"),
    onSuccess: (res) =>
      toast({
        title: res.ok ? "Test email sent" : "Test failed",
        description: res.message,
        variant: res.ok ? "success" : "destructive",
      }),
    onError: (err: Error) =>
      toast({ title: "Test failed", description: err.message, variant: "destructive" }),
  });

  if (isPending) return <Skeleton className="h-64" />;

  return (
    <div className="max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Daily report email</CardTitle>
          <CardDescription>
            Configure SMTP and recipients. The report is emailed daily at the scheduled time
            (server timezone).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="email-enabled"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <Label htmlFor="email-enabled">Enable scheduled email reports</Label>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Recipients (one per line)</Label>
              <Textarea
                rows={3}
                placeholder={"reports@workshop.example\nmanager@workshop.example"}
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Daily schedule time</Label>
              <Input
                type="time"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>SMTP host</Label>
              <Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="smtp.example.com" />
            </div>
            <div className="space-y-1.5">
              <Label>SMTP port</Label>
              <Input type="number" value={port} onChange={(e) => setPort(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>SMTP username</Label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>SMTP password {data?.smtp.password_set ? "(stored)" : ""}</Label>
              <Input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={data?.smtp.password_set ? "•••••••• — leave blank to keep" : "Enter password"}
              />
            </div>
            <div className="space-y-1.5">
              <Label>From address</Label>
              <Input
                type="email"
                value={fromAddress}
                onChange={(e) => setFromAddress(e.target.value)}
                placeholder="vehicle-report@workshop.example"
              />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <Checkbox
                id="email-tls"
                checked={useTls}
                onChange={(e) => setUseTls(e.target.checked)}
              />
              <Label htmlFor="email-tls">Use TLS (STARTTLS)</Label>
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save settings
            </Button>
            <Button
              variant="secondary"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
            >
              {testMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send test email
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
