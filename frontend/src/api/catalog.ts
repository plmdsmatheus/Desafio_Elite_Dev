import { apiClient } from "@/api/client"
import type { CatalogItem } from "@/types"

export function searchCatalog(provider: "ticketmaster" | "tmdb", q: string) {
  return apiClient
    .get<CatalogItem[]>("/catalog/search", { params: { provider, q } })
    .then((res) => res.data)
}
