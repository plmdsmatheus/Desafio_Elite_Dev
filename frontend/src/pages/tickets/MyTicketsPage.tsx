import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, Ticket as TicketIcon } from "lucide-react"
import { useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { getMyTickets } from "@/api/tickets"
import { TicketCard } from "@/components/ticket-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/use-auth"

export function MyTicketsPage() {
  const { user } = useAuth()
  const [page, setPage] = useState(1)

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["my-tickets", page],
    queryFn: () => getMyTickets(page),
    enabled: !!user && user.role === "customer",
    placeholderData: keepPreviousData,
  })

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "customer") return <Navigate to="/" replace />

  const validTickets = data ? data.results.filter((t) => t.status === "valid") : []
  const historyTickets = data ? data.results.filter((t) => t.status !== "valid") : []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Meus ingressos</h1>
        <p className="text-muted-foreground">Seus ingressos com QR, prontos pra apresentar na portaria.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-80 w-full" />
          ))}
        </div>
      ) : !data || data.count === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <TicketIcon className="size-8 text-muted-foreground" />
          <p className="text-muted-foreground">Você ainda não tem ingressos.</p>
          <Button asChild>
            <Link to="/eventos">Encontrar eventos</Link>
          </Button>
        </div>
      ) : (
        <>
          {validTickets.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {validTickets.map((ticket) => (
                <TicketCard key={ticket.id} ticket={ticket} />
              ))}
            </div>
          )}

          {historyTickets.length > 0 && (
            <div className="flex flex-col gap-3 border-t pt-6">
              <h2 className="text-sm font-medium text-muted-foreground">
                Histórico ({historyTickets.length})
              </h2>
              <div className="grid grid-cols-1 gap-4 opacity-60 sm:grid-cols-2 lg:grid-cols-3">
                {historyTickets.map((ticket) => (
                  <TicketCard key={ticket.id} ticket={ticket} />
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{data.count} ingresso(s) encontrado(s)</p>
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
