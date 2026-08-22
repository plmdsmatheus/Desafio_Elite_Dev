import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Search } from "lucide-react"
import { Link } from "react-router-dom"
import { listEvents } from "@/api/events"
import { EventCarousel } from "@/components/event-carousel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

/** Landing page: a hero banner plus a carousel of upcoming, still-buyable
 * events — the full search/filter experience lives at /eventos. Featured
 * here just means "first page of published events, still available", the
 * same set the old single-page listing already put in its carousel — no new
 * "featured" concept on the backend. */
export function HomePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["events", "home"],
    queryFn: () => listEvents({}),
  })

  const featuredEvents = data
    ? data.results.filter((event) => event.effective_status !== "completed" && event.tickets_available > 0)
    : []

  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col items-center gap-5 py-10 text-center sm:py-16">
        <h1 className="max-w-2xl text-4xl font-bold text-balance sm:text-5xl">
          Seu próximo show ou sessão está <span className="text-primary">aqui</span>.
        </h1>
        <p className="max-w-xl text-muted-foreground sm:text-lg">
          Shows e sessões de filme com ingresso digital, QR na hora e validação rápida na entrada.
        </p>
        <Button asChild size="lg" className="mt-2">
          <Link to="/eventos">
            <Search className="size-4" />
            Ver todos os eventos
          </Link>
        </Button>
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Em destaque</h2>
            <p className="text-sm text-muted-foreground">Eventos com ingressos disponíveis, saindo do forno.</p>
          </div>
          <Link
            to="/eventos"
            className="hidden shrink-0 items-center gap-1 text-sm font-medium text-primary hover:underline sm:flex"
          >
            Ver tudo
            <ArrowRight className="size-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-72 w-full" />
            ))}
          </div>
        ) : featuredEvents.length > 0 ? (
          <EventCarousel events={featuredEvents} />
        ) : (
          <p className="py-8 text-center text-muted-foreground">
            Nenhum evento disponível no momento — volte em breve.
          </p>
        )}
      </section>
    </div>
  )
}
