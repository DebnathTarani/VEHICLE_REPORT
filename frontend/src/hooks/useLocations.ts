import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Location } from "@/lib/types";

export function useLocations(enabled = true) {
  return useQuery({
    queryKey: ["locations"],
    queryFn: () => api.get<Location[]>("/locations"),
    enabled,
  });
}
