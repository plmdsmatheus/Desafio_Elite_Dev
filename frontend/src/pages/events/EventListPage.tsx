import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { type EventListParams, listEvents } from "@/api/events"
import { EventCard } from "@/components/event-card"
import { EventCarousel } from "@/components/event-carousel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

const CATEGORY_FILTER_ALL = "all"

export function EventListPage() {
  const [draft, setDraft] = useState({ q: "", city: "", category: CATEGORY_FILTER_ALL, date: "" })
  const [filters, setFilters] = useState<EventListParams>({})
  const [page, setPage] = useState(1)

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["events", filters, page],
    queryFn: () => listEvents({ ...filters, page }),
    placeholderData: keepPreviousData,
  })

  function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    setPage(1)
    setFilters({
      q: draft.q,
      city: draft.city,
      category: draft.category === CATEGORY_FILTER_ALL ? "" : (draft.category as EventListParams["category"]),
      date: draft.date,
    })
  }

  function handleClear() {
    setDraft({ q: "", city: "", category: CATEGORY_FILTER_ALL, date: "" })
    setFilters({})
    setPage(1)
  }

  const hasActiveFilters = Object.values(filters).some(Boolean)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Encontre seu próximo evento!</h1>
        <p className="text-muted-foreground">Shows e sessões de filme com ingressos disponíveis.</p>
      </div>

      <form
        onSubmit={handleSearch}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4"
      >
        <div className="flex min-w-48 flex-1 flex-col gap-1.5">
          <label htmlFor="q" className="text-sm font-medium">
            Buscar
          </label>
          <Input
            id="q"
            placeholder="Nome do evento ou local"
            value={draft.q}
            onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))}
          />
        </div>

        <div className="flex w-40 flex-col gap-1.5">
          <label htmlFor="city" className="text-sm font-medium">
            Cidade
          </label>
          <Input
            id="city"
            value={draft.city}
            onChange={(e) => setDraft((d) => ({ ...d, city: e.target.value }))}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Categoria</span>
          <Select
            value={draft.category}
            onValueChange={(value) => setDraft((d) => ({ ...d, category: value }))}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={CATEGORY_FILTER_ALL}>Todas</SelectItem>
              <SelectItem value="show">Show</SelectItem>
              <SelectItem value="movie">Filme</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="date" className="text-sm font-medium">
            Data
          </label>
          <Input
            id="date"
            type="date"
            value={draft.date}
            onChange={(e) => setDraft((d) => ({ ...d, date: e.target.value }))}
          />
        </div>

        <Button type="submit">Buscar</Button>
        {hasActiveFilters && (
          <Button type="button" variant="ghost" onClick={handleClear}>
            Limpar
          </Button>
        )}
      </form>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      ) : !data || data.results.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          Nenhum evento encontrado com esses filtros.
        </p>
      ) : (
        <>
          {page === 1 ? (
            <EventCarousel events={data.results} />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.results.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{data.count} evento(s) encontrado(s)</p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!data.previous || isPlaceholderData}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Anterior
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!data.next || isPlaceholderData}
                onClick={() => setPage((p) => p + 1)}
              >
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
