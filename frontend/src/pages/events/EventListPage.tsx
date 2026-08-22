import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { CalendarDays, CalendarSearch, ChevronLeft, ChevronRight, MapPin, Search, Tag, X } from "lucide-react"
import { useEffect, useState } from "react"
import { type EventListParams, listEvents } from "@/api/events"
import { CityCombobox } from "@/components/city-combobox"
import { EventCard } from "@/components/event-card"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import type { EventCategory } from "@/types"

const CATEGORY_FILTER_ALL = "all"
const DEBOUNCE_MS = 400

export function EventListPage() {
  const [q, setQ] = useState("")
  const [city, setCity] = useState("")
  const [category, setCategory] = useState<EventCategory | typeof CATEGORY_FILTER_ALL>(
    CATEGORY_FILTER_ALL,
  )
  const [date, setDate] = useState("")
  const [showUnavailable, setShowUnavailable] = useState(false)
  const [page, setPage] = useState(1)

  const debouncedQ = useDebouncedValue(q, DEBOUNCE_MS)
  const debouncedCity = useDebouncedValue(city, DEBOUNCE_MS)

  const filters: EventListParams = {
    q: debouncedQ,
    city: debouncedCity,
    category: category === CATEGORY_FILTER_ALL ? "" : category,
    date,
    show_unavailable: showUnavailable,
  }

  // Every filter here is already the value the query itself uses (text
  // fields debounced, everything else instant) — a new search always starts
  // back on page 1, same as the old "Buscar" submit used to do.
  useEffect(() => {
    setPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, debouncedCity, category, date, showUnavailable])

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["events", filters, page],
    queryFn: () => listEvents({ ...filters, page }),
    placeholderData: keepPreviousData,
  })

  function handleClear() {
    setQ("")
    setCity("")
    setCategory(CATEGORY_FILTER_ALL)
    setDate("")
    setShowUnavailable(false)
  }

  const hasActiveFilters = !!(q || city || category !== CATEGORY_FILTER_ALL || date || showUnavailable)
  const upcomingEvents = data ? data.results.filter((event) => event.effective_status !== "completed") : []
  const completedEvents = data ? data.results.filter((event) => event.effective_status === "completed") : []
  const availableEvents = upcomingEvents.filter((event) => event.tickets_available > 0)
  const soldOutEvents = upcomingEvents.filter((event) => event.tickets_available === 0)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Encontre seu próximo evento!</h1>
        <p className="text-muted-foreground">Shows e sessões de filme com ingressos disponíveis.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">
        <div className="flex min-w-48 flex-1 flex-col gap-1.5">
          <Label htmlFor="q">
            <Search className="size-3.5 text-muted-foreground" />
            Buscar
          </Label>
          <Input
            id="q"
            placeholder="Nome do evento ou local"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <div className="flex w-44 flex-col gap-1.5">
          <Label htmlFor="city">
            <MapPin className="size-3.5 text-muted-foreground" />
            Cidade
          </Label>
          <CityCombobox id="city" value={city} onChange={setCity} placeholder="Qualquer cidade" />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>
            <Tag className="size-3.5 text-muted-foreground" />
            Categoria
          </Label>
          <Select
            value={category}
            onValueChange={(value) => setCategory(value as EventCategory | typeof CATEGORY_FILTER_ALL)}
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

        <div className="flex w-44 flex-col gap-1.5">
          <Label htmlFor="date">
            <CalendarDays className="size-3.5 text-muted-foreground" />
            Data
          </Label>
          <DatePicker id="date" value={date} onChange={setDate} />
        </div>

        <div className="flex items-center gap-2 pb-2">
          <Switch id="show_unavailable" checked={showUnavailable} onCheckedChange={setShowUnavailable} />
          <Label htmlFor="show_unavailable" className="font-normal text-muted-foreground">
            Mostrar esgotados/realizados
          </Label>
        </div>

        {hasActiveFilters && (
          <Button type="button" variant="ghost" onClick={handleClear}>
            <X />
            Limpar
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      ) : !data || data.results.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
          <CalendarSearch className="size-8" />
          <p>Nenhum evento encontrado com esses filtros.</p>
        </div>
      ) : (
        <>
          {availableEvents.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {availableEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          ) : soldOutEvents.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum ingresso disponível nesta página — veja os esgotados abaixo.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Todos os eventos desta página já foram realizados — veja abaixo.
            </p>
          )}

          {soldOutEvents.length > 0 && (
            <div className="flex flex-col gap-3 border-t pt-6">
              <h2 className="text-sm font-medium text-muted-foreground">
                Esgotados ({soldOutEvents.length})
              </h2>
              <div className="grid grid-cols-2 gap-3 opacity-60 sm:grid-cols-3 lg:grid-cols-4">
                {soldOutEvents.map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
            </div>
          )}

          {completedEvents.length > 0 && (
            <div className="flex flex-col gap-3 border-t pt-6">
              <h2 className="text-sm font-medium text-muted-foreground">
                Realizados ({completedEvents.length})
              </h2>
              <div className="grid grid-cols-2 gap-3 opacity-60 sm:grid-cols-3 lg:grid-cols-4">
                {completedEvents.map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
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
                <ChevronLeft />
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
                <ChevronRight />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
