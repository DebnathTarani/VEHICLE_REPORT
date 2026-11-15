import { useState } from "react";
import { Building2, KeyRound, Mail, Settings2, Users } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProvidersTab } from "@/components/settings/ProvidersTab";
import { EmailTab } from "@/components/settings/EmailTab";
import { GeneralTab } from "@/components/settings/GeneralTab";
import { UsersTab } from "@/components/settings/UsersTab";
import { LocationsTab } from "@/components/settings/LocationsTab";

export function SettingsPage() {
  const [tab, setTab] = useState("providers");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Administrative configuration.</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="providers">
            <KeyRound className="h-3.5 w-3.5" /> Providers
          </TabsTrigger>
          <TabsTrigger value="email">
            <Mail className="h-3.5 w-3.5" /> Email
          </TabsTrigger>
          <TabsTrigger value="general">
            <Settings2 className="h-3.5 w-3.5" /> General
          </TabsTrigger>
          <TabsTrigger value="users">
            <Users className="h-3.5 w-3.5" /> Users
          </TabsTrigger>
          <TabsTrigger value="locations">
            <Building2 className="h-3.5 w-3.5" /> Locations
          </TabsTrigger>
        </TabsList>
        <div className="pt-6">
          <TabsContent value="providers">
            <ProvidersTab />
          </TabsContent>
          <TabsContent value="email">
            <EmailTab />
          </TabsContent>
          <TabsContent value="general">
            <GeneralTab />
          </TabsContent>
          <TabsContent value="users">
            <UsersTab />
          </TabsContent>
          <TabsContent value="locations">
            <LocationsTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
