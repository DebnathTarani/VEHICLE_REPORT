import { Navigate, Route, Routes } from "react-router-dom";
import { AuthGuard, AdminGuard } from "@/components/AuthGuard";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { EntryPage } from "@/pages/EntryPage";
import { ImportsPage } from "@/pages/ImportsPage";
import { ImportJobPage } from "@/pages/ImportJobPage";
import { VehiclesPage } from "@/pages/VehiclesPage";
import { VehicleTimelinePage } from "@/pages/VehicleTimelinePage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AuthGuard />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="entry" element={<EntryPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="imports/:jobId" element={<ImportJobPage />} />
          <Route path="vehicles" element={<VehiclesPage />} />
          <Route path="vehicles/:vrnNormalized" element={<VehicleTimelinePage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route element={<AdminGuard />}>
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
