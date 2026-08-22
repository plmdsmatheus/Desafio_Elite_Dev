import { keepPreviousData, useQuery } from "@tanstack/react-query"
import {
  AlertTriangle,
  ArrowLeftRight,
  Calendar,
  CalendarX2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  MapPin,
  QrCode,
  XCircle,
} from "lucide-react"
import { useState } from "react"
import { Navigate } from "react-router-dom"
import { getGateEvents, validateTicket } from "@/api/gate"
import { EventThumbnail } from "@/components/event-thumbnail"
import { QrScanner } from "@/components/qr-scanner"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/use-auth"
import { getApiErrorMessage } from "@/lib/api-error"
import { formatDateTime } from "@/lib/format"
import { CATEGORY_LABEL } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { Event, GateValidateResponse, GateValidateResult } from "@/types"

export function GatePage() {
  const { user } = useAuth()

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "gate") return <Navigate to="/" replace />

  return <GateFlow />
}

function GateFlow() {
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null)

  if (!selectedEvent) {
    return <GateEventPicker onSelect={setSelectedEvent} />
  }

  return (
    <GateValidationScreen
      key={selectedEvent.id}
      event={selectedEvent}
      onChangeEvent={() => setSelectedEvent(null)}
    />
  )
}

function GateEventPicker({ onSelect }: { onSelect: (event: Event) => void }) {
  const [page, setPage] = useState(1)

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["gate-events", page],
    queryFn: () => getGateEvents(page),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Portaria</h1>
        <p className="text-muted-foreground">Escolha o evento pra validar os ingressos.</p>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : !data || data.count === 0 ? (
        <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
          <CalendarX2 className="size-8" />
          <p>Nenhum evento publicado no momento.</p>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {data.results.map((event) => (
              <button
                key={event.id}
                type="button"
                onClick={() => onSelect(event)}
                className="flex items-center gap-4 rounded-xl border bg-card p-3 text-left transition-colors hover:border-primary"
              >
                <div className="h-16 w-24 shrink-0 overflow-hidden rounded-lg">
                  <EventThumbnail
                    src={event.image_url}
                    category={event.category}
                    dateTime={event.date_time}
                    className="h-full w-full"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{event.title}</p>
                  <p className="flex items-center gap-1.5 truncate text-sm text-muted-foreground">
                    <MapPin className="size-3.5 shrink-0" />
                    {event.venue_name}, {event.city}
                  </p>
                  <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Calendar className="size-3.5 shrink-0" />
                    {formatDateTime(event.date_time)}
                  </p>
                </div>
                <div className="shrink-0 text-right text-sm text-muted-foreground">
                  {event.tickets_sold}/{event.capacity}
                  <p className="text-xs">vendidos</p>
                </div>
              </button>
            ))}
          </div>

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

const RESULT_CONFIG: Record<
  GateValidateResult,
  { label: string; icon: typeof CheckCircle2; className: string }
> = {
  valido: { label: "Ingresso válido", icon: CheckCircle2, className: "border-success/30 bg-success/10 text-success" },
  invalido: { label: "Ingresso inválido", icon: XCircle, className: "border-destructive/30 bg-destructive/10 text-destructive" },
  ja_utilizado: { label: "Já utilizado", icon: AlertTriangle, className: "border-warning/30 bg-warning/10 text-warning" },
  evento_errado: { label: "Evento errado", icon: ArrowLeftRight, className: "border-warning/30 bg-warning/10 text-warning" },
}

interface HistoryEntry {
  id: number
  time: string
  code: string
  response: GateValidateResponse
}

let historyIdCounter = 0

function GateValidationScreen({ event, onChangeEvent }: { event: Event; onChangeEvent: () => void }) {
  const [manualCode, setManualCode] = useState("")
  const [isValidating, setIsValidating] = useState(false)
  const [result, setResult] = useState<GateValidateResponse | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [validCount, setValidCount] = useState(0)

  async function handleValidate(rawCode: string) {
    const code = rawCode.trim()
    if (!code || isValidating) return

    setIsValidating(true)
    try {
      const response = await validateTicket({ code, event_id: event.id })
      setResult(response)
      setHistory((h) =>
        [{ id: historyIdCounter++, time: formatDateTime(new Date().toISOString()), code, response }, ...h].slice(0, 15),
      )
      if (response.result === "valido") setValidCount((c) => c + 1)
    } catch (err) {
      setResult({
        result: "invalido",
        detail: getApiErrorMessage(err, "Não foi possível validar — tente de novo."),
      })
    } finally {
      setIsValidating(false)
    }
  }

  function handleManualSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault()
    handleValidate(manualCode)
    setManualCode("")
  }

  /** The backend only echoes back the full `ticket` object for a "valido"
   * result — for the other outcomes we fall back to what was actually typed
   * or scanned, truncated because a camera scan submits the full signed QR
   * payload (much longer than a public_code) rather than a short code. */
  function displayCode(entry: HistoryEntry): string {
    const publicCode = entry.response.ticket?.public_code
    if (publicCode) return publicCode
    return entry.code.length > 14 ? `${entry.code.slice(0, 14)}…` : entry.code
  }

  const resultConfig = result ? RESULT_CONFIG[result.result] : null
  const ResultIcon = resultConfig?.icon

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {CATEGORY_LABEL[event.category] ?? event.category} · Sessão de validação
          </p>
          <h1 className="text-2xl font-semibold">{event.title}</h1>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Calendar className="size-3.5 shrink-0" />
            {formatDateTime(event.date_time)} · {event.venue_name}, {event.city}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right text-sm">
            <span className="font-mono text-lg font-semibold text-primary">{validCount}</span>
            <p className="text-xs text-muted-foreground">validados nesta sessão</p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onChangeEvent}>
            Trocar evento
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
        <Card>
          <CardContent className="flex flex-col gap-3">
            <p className="flex items-center gap-2 text-sm font-medium">
              <QrCode className="size-4" />
              Ler QR pela câmera
            </p>
            <QrScanner onScan={handleValidate} />
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm font-medium">Ou digite o código manualmente</p>
              <form onSubmit={handleManualSubmit} className="flex gap-2">
                <Label htmlFor="manual_code" className="sr-only">
                  Código do ingresso
                </Label>
                <Input
                  id="manual_code"
                  autoFocus
                  placeholder="Ex: WRFFJ5JH4C"
                  value={manualCode}
                  onChange={(e) => setManualCode(e.target.value)}
                  className="font-mono uppercase"
                />
                <Button type="submit" disabled={isValidating || !manualCode.trim()}>
                  {isValidating ? "Validando..." : "Validar"}
                </Button>
              </form>
            </CardContent>
          </Card>

          {result && resultConfig && ResultIcon && (
            <div className={cn("flex items-start gap-3 rounded-xl border p-4", resultConfig.className)}>
              <ResultIcon className="size-6 shrink-0" />
              <div className="min-w-0">
                <p className="font-medium">{resultConfig.label}</p>
                <p className="text-sm opacity-90">{result.detail}</p>
                {result.ticket && (
                  <p className="mt-1 font-mono text-xs opacity-75">
                    {result.ticket.public_code}
                    {result.ticket.seat_label ? ` · Assento ${result.ticket.seat_label}` : ""}
                  </p>
                )}
              </div>
            </div>
          )}

          {history.length > 0 && (
            <Card>
              <CardContent className="flex flex-col gap-2">
                <p className="text-sm font-medium text-muted-foreground">Histórico da sessão</p>
                <div className="flex flex-col divide-y">
                  {history.map((entry) => {
                    const config = RESULT_CONFIG[entry.response.result]
                    return (
                      <div key={entry.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <span className="truncate font-mono text-xs text-muted-foreground">
                          {displayCode(entry)}
                        </span>
                        <span className={cn("shrink-0 text-xs font-medium", config.className.split(" ").find((c) => c.startsWith("text-")))}>
                          {config.label}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
