import { QRCodeSVG } from "qrcode.react"
import { Link } from "react-router-dom"
import { ShareButton } from "@/components/share-button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { formatDateTime } from "@/lib/format"
import { CATEGORY_LABEL } from "@/lib/labels"
import type { Ticket, TicketStatus } from "@/types"

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

export function TicketCard({ ticket }: { ticket: Ticket }) {
  const { event } = ticket

  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <Link
              to={`/eventos/${event.id}`}
              className="line-clamp-1 font-medium hover:underline"
            >
              {event.title}
            </Link>
            <p className="line-clamp-1 text-xs text-muted-foreground">
              {CATEGORY_LABEL[event.category] ?? event.category} · {event.venue_name}, {event.city}
            </p>
            <p className="text-xs text-muted-foreground">{formatDateTime(event.date_time)}</p>
          </div>
          <Badge variant={STATUS_VARIANT[ticket.status]} className="shrink-0">
            {STATUS_LABEL[ticket.status]}
          </Badge>
        </div>

        <div className="flex flex-col items-center gap-2 py-2">
          <div className="rounded-lg border bg-white p-3">
            <QRCodeSVG value={ticket.qr_payload} size={140} />
          </div>
          <p className="font-mono text-sm tracking-widest">{ticket.public_code}</p>
          {ticket.status === "used" && ticket.used_at && (
            <p className="text-xs text-muted-foreground">
              Validado em {formatDateTime(ticket.used_at)}
            </p>
          )}
        </div>

        <ShareButton title={event.title} url={ticket.share_url} />
      </CardContent>
    </Card>
  )
}
