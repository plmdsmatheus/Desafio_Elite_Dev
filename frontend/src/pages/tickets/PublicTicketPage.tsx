import { useQuery } from "@tanstack/react-query"
import { QRCodeSVG } from "qrcode.react"
import { useParams } from "react-router-dom"
import { getPublicTicket } from "@/api/tickets"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/format"
import { CATEGORY_LABEL } from "@/lib/labels"
import type { TicketStatus } from "@/types"

const STATUS_LABEL: Record<TicketStatus, string> = {
  valid: "Válido",
  used: "Utilizado",
  canceled: "Cancelado",
}

const STATUS_VARIANT: Record<TicketStatus, "default" | "secondary" | "destructive"> = {
  valid: "default",
  used: "secondary",
  canceled: "destructive",
}

export function PublicTicketPage() {
  const { shareSlug } = useParams<{ shareSlug: string }>()

  const { data: ticket, isLoading, isError } = useQuery({
    queryKey: ["public-ticket", shareSlug],
    queryFn: () => getPublicTicket(shareSlug!),
    enabled: !!shareSlug,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center pt-4 sm:pt-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <Skeleton className="size-48" />
            <Skeleton className="h-4 w-32" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isError || !ticket) {
    return (
      <div className="flex justify-center pt-4 sm:pt-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Ingresso não encontrado</CardTitle>
            <CardDescription>
              O link pode estar incorreto ou o ingresso não existe mais.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  const { event } = ticket

  return (
    <div className="flex justify-center pt-4 sm:pt-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle>{event.title}</CardTitle>
              <CardDescription>
                {CATEGORY_LABEL[event.category] ?? event.category} · {event.venue_name},{" "}
                {event.city}
              </CardDescription>
            </div>
            <Badge variant={STATUS_VARIANT[ticket.status]} className="shrink-0">
              {STATUS_LABEL[ticket.status]}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <p className="self-start text-sm text-muted-foreground">
            {formatDateTime(event.date_time)}
          </p>

          <div className="rounded-lg border bg-white p-4">
            <QRCodeSVG value={ticket.qr_payload} size={192} />
          </div>

          <div className="text-center">
            <p className="text-xs text-muted-foreground">Código do ingresso</p>
            <p className="font-mono text-lg tracking-widest">{ticket.public_code}</p>
          </div>

          {ticket.status === "used" && ticket.used_at && (
            <p className="text-center text-sm text-muted-foreground">
              Validado em {formatDateTime(ticket.used_at)}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
