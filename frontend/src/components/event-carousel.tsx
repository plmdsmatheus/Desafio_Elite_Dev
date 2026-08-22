import { EventCard } from "@/components/event-card"
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel"
import type { Event } from "@/types"

export function EventCarousel({ events }: { events: Event[] }) {
  return (
    <div className="px-10">
      <Carousel opts={{ align: "start" }}>
        {/* CarouselContent's own viewport div has a hardcoded overflow-hidden
         * (needed so off-screen slides stay hidden) — without this padding,
         * a card sitting flush against that edge gets its hover glow/lift
         * clipped into a flat line right at the boundary. */}
        <CarouselContent className="py-4">
          {events.map((event) => (
            <CarouselItem key={event.id} className="basis-full sm:basis-1/2 lg:basis-1/3">
              <EventCard event={event} />
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>
    </div>
  )
}
