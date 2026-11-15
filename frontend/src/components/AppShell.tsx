import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Car,
  ClipboardList,
  Gauge,
  ImageUp,
  LayoutDashboard,
  LogOut,
  Settings,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/context/auth";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/entry", label: "Entry", icon: ClipboardList, end: false },
  { to: "/imports", label: "Imports", icon: ImageUp, end: false },
  { to: "/vehicles", label: "Vehicles", icon: Car, end: false },
  { to: "/reports", label: "Reports", icon: Gauge, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false, adminOnly: true },
];

export function AppShell() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Car className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-bold leading-tight">Vehicle Report</div>
            <div className="text-[11px] text-muted-foreground">Workshop v2</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          {navItems
            .filter((item) => !item.adminOnly || isAdmin)
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            ))}
        </nav>
        <div className="border-t border-border p-4 text-[11px] text-muted-foreground">
          Signed in as{" "}
          <span className="font-medium text-foreground">{user?.display_name ?? "—"}</span>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur">
          <div className="text-sm text-muted-foreground">
            {user?.location_id ? null : "All locations"}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{user?.display_name}</span>
              <Badge variant="secondary" className="capitalize">
                {user?.role}
              </Badge>
            </div>
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Log out"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
