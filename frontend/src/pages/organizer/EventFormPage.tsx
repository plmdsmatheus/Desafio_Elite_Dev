import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { useState } from "react"
import { Link, Navigate, useNavigate, useParams } from "react-router-dom"
import { searchCatalog } from "@/api/catalog"
import { createEvent, type EventFormInput, getEvent, updateEvent } from "@/api/events"
import { CancelEventDialog } from "@/components/cancel-event-dialog"
import { EventThumbnail } from "@/components/event-thumbnail"
import { PublishEventDialog } from "@/components/publish-event-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { DateTimePicker } from "@/components/ui/datetime-picker"
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
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/hooks/use-auth"
import { getApiErrorMessage, getApiFieldErrors } from "@/lib/api-error"
import { toDatetimeLocalValue } from "@/lib/format"
import type { CatalogItem, Event, EventCategory, EventSourceProvider } from "@/types"

export function EventFormPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const { user } = useAuth()
  const isEditMode = !!eventId

  const { data: event, isLoading, isError } = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: isEditMode,
    retry: false,
  })

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "organizer") return <Navigate to="/" replace />

  if (isEditMode) {
    if (isLoading) {
      return (
        <Card className="mx-auto w-full max-w-2xl">
          <CardHeader>
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      )
    }

    if (isError || !event) {
      return (
        <Card className="mx-auto w-full max-w-2xl">
          <CardHeader>
            <CardTitle>Evento não encontrado</CardTitle>
            <CardDescription>O link pode estar incorreto ou o evento foi removido.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/organizador">Voltar pros meus eventos</Link>
            </Button>
          </CardContent>
        </Card>
      )
    }

    if (event.organizer !== user.id) {
      return <Navigate to="/organizador" replace />
    }
  }

  return <EventForm key={eventId ?? "new"} initialEvent={isEditMode ? (event ?? null) : null} />
}

const CATEGORY_OPTIONS: { value: EventCategory; label: string }[] = [
  { value: "show", label: "Show" },
  { value: "movie", label: "Filme" },
]

function EventForm({ initialEvent }: { initialEvent: Event | null }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isEditMode = !!initialEvent
  const isPublished = isEditMode && initialEvent.status === "published"
  const isCanceled = isEditMode && initialEvent.status === "canceled"

  const [title, setTitle] = useState(initialEvent?.title ?? "")
  const [description, setDescription] = useState(initialEvent?.description ?? "")
  const [imageUrl, setImageUrl] = useState(initialEvent?.image_url ?? "")
  const [category, setCategory] = useState<EventCategory>(initialEvent?.category ?? "show")
  const [venueName, setVenueName] = useState(initialEvent?.venue_name ?? "")
  const [address, setAddress] = useState(initialEvent?.address ?? "")
  const [city, setCity] = useState(initialEvent?.city ?? "")
  const [dateTime, setDateTime] = useState(
    initialEvent ? toDatetimeLocalValue(initialEvent.date_time) : "",
  )
  const [capacity, setCapacity] = useState(initialEvent ? String(initialEvent.capacity) : "")
  const [price, setPrice] = useState(initialEvent ? String(initialEvent.price) : "")
  const [hasSeatMap, setHasSeatMap] = useState(initialEvent?.has_seat_map ?? false)
  const [sourceProvider, setSourceProvider] = useState<EventSourceProvider>(
    initialEvent?.source_provider ?? "manual",
  )
  const [sourceId, setSourceId] = useState(initialEvent?.source_id ?? "")

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [catalogProvider, setCatalogProvider] = useState<"ticketmaster" | "tmdb">("ticketmaster")
  const [catalogQuery, setCatalogQuery] = useState("")
  const [catalogResults, setCatalogResults] = useState<CatalogItem[] | null>(null)
  const [isSearchingCatalog, setIsSearchingCatalog] = useState(false)
  const [catalogError, setCatalogError] = useState("")

  // Once published, the backend only accepts date/time and location changes
  // (see EventWriteSerializer) — everything else, seat map included, is
  // locked in for good at that point, not just while seats are already sold.
  const seatMapLocked = isPublished

  async function handleCatalogSearch(formEvent: React.FormEvent) {
    formEvent.preventDefault()
    if (!catalogQuery.trim()) return
    setCatalogError("")
    setIsSearchingCatalog(true)
    try {
      setCatalogResults(await searchCatalog(catalogProvider, catalogQuery.trim()))
    } catch (err) {
      setCatalogError(getApiErrorMessage(err, "Não foi possível buscar no catálogo."))
    } finally {
      setIsSearchingCatalog(false)
    }
  }

  function applyCatalogItem(item: CatalogItem) {
    setTitle(item.title)
    setDescription(item.description)
    setImageUrl(item.image_url)
    setCategory(item.category)
    setVenueName(item.suggested_venue_name)
    setAddress(item.suggested_address)
    setCity(item.suggested_city)
    if (item.suggested_date_time) {
      setDateTime(toDatetimeLocalValue(item.suggested_date_time))
    }
    setSourceProvider(item.provider)
    setSourceId(item.external_id)
    setCatalogResults(null)
    setCatalogQuery("")
  }

  async function handleSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault()
    setFieldErrors({})
    setFormError("")

    // The picker replaced a native `<input required>`, which used to block
    // submission by itself — `new Date(dateTime)` below would otherwise
    // throw on an empty string instead of showing a normal field error.
    if (!dateTime) {
      setFieldErrors({ date_time: "Selecione a data e hora do evento." })
      return
    }

    setIsSubmitting(true)

    const fullPayload: EventFormInput = {
      source_provider: sourceProvider,
      source_id: sourceId,
      title,
      description,
      image_url: imageUrl,
      category,
      venue_name: venueName,
      address,
      city,
      date_time: new Date(dateTime).toISOString(),
      capacity: Number(capacity),
      price,
      has_seat_map: hasSeatMap,
    }

    // Once published, the backend rejects anything outside date/time and
    // location — send exactly that subset instead of the full form. The
    // rest of the fields are disabled in the UI already, but this keeps the
    // request itself honest about what's actually changing.
    const payload: Partial<EventFormInput> = isPublished
      ? {
          date_time: fullPayload.date_time,
          venue_name: fullPayload.venue_name,
          address: fullPayload.address,
          city: fullPayload.city,
        }
      : fullPayload

    try {
      if (isEditMode) {
        await updateEvent(initialEvent.id, payload)
      } else {
        await createEvent(fullPayload)
      }
      // Without this, the organizer panel (and the public/detail views of
      // this same event) keep showing the pre-edit cached data until a full
      // page reload — React Query has no way to know this event just changed.
      await queryClient.invalidateQueries({ queryKey: ["organizer-events"] })
      if (isEditMode) {
        await queryClient.invalidateQueries({ queryKey: ["event", String(initialEvent.id)] })
      }
      await queryClient.invalidateQueries({ queryKey: ["events"] })
      navigate("/organizador")
    } catch (err) {
      const errors = getApiFieldErrors(err)
      if (Object.keys(errors).length > 0) {
        setFieldErrors(errors)
      } else {
        setFormError(getApiErrorMessage(err, "Não foi possível salvar o evento."))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Canceled is a terminal state (see EventWriteSerializer) — nothing about
  // this event can change anymore, so there's no form to show at all.
  if (isCanceled) {
    return (
      <Card className="mx-auto w-full max-w-2xl">
        <CardHeader>
          <CardTitle>{initialEvent.title}</CardTitle>
          <CardDescription>
            Este evento foi cancelado e não pode mais ser alterado.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link to="/organizador">Voltar pros meus eventos</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{isEditMode ? "Editar evento" : "Criar evento"}</h1>
        <p className="text-muted-foreground">
          {isPublished
            ? "Evento publicado — só dá pra alterar data/hora e local, ou cancelar o evento."
            : isEditMode
              ? "É um rascunho: pode alterar qualquer coisa livremente antes de publicar."
              : "Preencha os dados do evento ou busque num catálogo externo pra preencher automaticamente. O evento nasce como rascunho — publicar é uma etapa separada."}
        </p>
      </div>

      {!isEditMode && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Buscar no catálogo (opcional)</CardTitle>
            <CardDescription>
              Escolha um show (Ticketmaster) ou filme (TMDb) real pra preencher o formulário — você
              ainda completa data, capacidade e preço depois.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <form onSubmit={handleCatalogSearch} className="flex flex-wrap gap-2">
              <Select
                value={catalogProvider}
                onValueChange={(value) => setCatalogProvider(value as "ticketmaster" | "tmdb")}
              >
                <SelectTrigger className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ticketmaster">Shows</SelectItem>
                  <SelectItem value="tmdb">Filmes</SelectItem>
                </SelectContent>
              </Select>
              <Input
                placeholder="Nome do show, artista ou filme"
                value={catalogQuery}
                onChange={(e) => setCatalogQuery(e.target.value)}
                className="min-w-48 flex-1"
              />
              <Button type="submit" disabled={isSearchingCatalog || !catalogQuery.trim()}>
                <Search />
                {isSearchingCatalog ? "Buscando..." : "Buscar"}
              </Button>
            </form>

            {catalogError && <p className="text-sm text-destructive">{catalogError}</p>}

            {catalogResults && catalogResults.length === 0 && (
              <p className="text-sm text-muted-foreground">Nada encontrado para essa busca.</p>
            )}

            {catalogResults && catalogResults.length > 0 && (
              <div className="flex flex-col gap-2">
                {catalogResults.map((item) => (
                  <button
                    key={`${item.provider}-${item.external_id}`}
                    type="button"
                    onClick={() => applyCatalogItem(item)}
                    className="flex items-center gap-3 rounded-lg border p-2 text-left transition-colors hover:border-primary"
                  >
                    <div className="size-14 shrink-0 overflow-hidden rounded">
                      <EventThumbnail
                        src={item.image_url}
                        category={item.category}
                        dateTime={item.suggested_date_time ?? ""}
                        className="h-full w-full"
                      />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{item.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{item.subtitle}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="title">Título</Label>
                <Input
                  id="title"
                  required
                  disabled={isPublished}
                  aria-invalid={!!fieldErrors.title}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                {fieldErrors.title && <p className="text-xs text-destructive">{fieldErrors.title}</p>}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Categoria</Label>
                <Select
                  value={category}
                  onValueChange={(value) => setCategory(value as EventCategory)}
                  disabled={isPublished}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description">Descrição</Label>
              <Textarea
                id="description"
                rows={4}
                disabled={isPublished}
                aria-invalid={!!fieldErrors.description}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              {fieldErrors.description && (
                <p className="text-xs text-destructive">{fieldErrors.description}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="image_url">URL da imagem</Label>
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <Input
                    id="image_url"
                    type="url"
                    placeholder="https://..."
                    disabled={isPublished}
                    aria-invalid={!!fieldErrors.image_url}
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                  />
                  {fieldErrors.image_url && (
                    <p className="mt-1 text-xs text-destructive">{fieldErrors.image_url}</p>
                  )}
                </div>
                <div className="size-16 shrink-0 overflow-hidden rounded-lg border">
                  <EventThumbnail
                    src={imageUrl}
                    category={category}
                    dateTime={dateTime}
                    className="h-full w-full"
                  />
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="venue_name">Local</Label>
                <Input
                  id="venue_name"
                  required
                  aria-invalid={!!fieldErrors.venue_name}
                  value={venueName}
                  onChange={(e) => setVenueName(e.target.value)}
                />
                {fieldErrors.venue_name && (
                  <p className="text-xs text-destructive">{fieldErrors.venue_name}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="city">Cidade</Label>
                <Input
                  id="city"
                  required
                  aria-invalid={!!fieldErrors.city}
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
                {fieldErrors.city && <p className="text-xs text-destructive">{fieldErrors.city}</p>}
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="address">Endereço (opcional)</Label>
              <Input
                id="address"
                aria-invalid={!!fieldErrors.address}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
              {fieldErrors.address && <p className="text-xs text-destructive">{fieldErrors.address}</p>}
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="date_time">Data e hora</Label>
                <DateTimePicker
                  id="date_time"
                  aria-invalid={!!fieldErrors.date_time}
                  value={dateTime}
                  onChange={setDateTime}
                />
                {fieldErrors.date_time && (
                  <p className="text-xs text-destructive">{fieldErrors.date_time}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="capacity">Capacidade</Label>
                <Input
                  id="capacity"
                  type="number"
                  min={1}
                  required
                  disabled={isPublished}
                  aria-invalid={!!fieldErrors.capacity}
                  value={capacity}
                  onChange={(e) => setCapacity(e.target.value)}
                />
                {fieldErrors.capacity && (
                  <p className="text-xs text-destructive">{fieldErrors.capacity}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="price">Preço (R$)</Label>
                <Input
                  id="price"
                  type="number"
                  min={0}
                  step="0.01"
                  required
                  disabled={isPublished}
                  aria-invalid={!!fieldErrors.price}
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                />
                {fieldErrors.price && <p className="text-xs text-destructive">{fieldErrors.price}</p>}
              </div>
            </div>

            <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Ingressos com assento marcado</p>
                <p className="text-xs text-muted-foreground">
                  {seatMapLocked
                    ? "Não dá pra mudar depois que o evento foi publicado."
                    : "Pra eventos em cinema/teatro — o cliente escolhe a poltrona em vez de só a quantidade."}
                </p>
              </div>
              <Switch checked={hasSeatMap} onCheckedChange={setHasSeatMap} disabled={seatMapLocked} />
            </div>

            {formError && <p className="text-sm text-destructive">{formError}</p>}

            <div className="flex flex-wrap items-center gap-3 border-t pt-4">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting
                  ? "Salvando..."
                  : isEditMode
                    ? "Salvar alterações"
                    : "Salvar rascunho"}
              </Button>
              {isEditMode && !isPublished && <PublishEventDialog event={initialEvent} />}
              {isPublished && <CancelEventDialog event={initialEvent} />}
              <Button asChild type="button" variant="ghost">
                <Link to="/organizador">Voltar</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
