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
        <CarouselContent>
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
