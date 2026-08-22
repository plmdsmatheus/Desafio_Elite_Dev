import { useQuery } from "@tanstack/react-query"
import { useRef, useState } from "react"
import { getEventCities } from "@/api/events"
import { Input } from "@/components/ui/input"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

const MAX_SUGGESTIONS = 8

interface CityComboboxProps {
  id?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

/** City filter: a plain text input (so free typing always works — the
 * filter's value IS whatever's in the field, never locked to a selection)
 * with a suggestions dropdown fed by the real cities that have a published
 * event. Built on Popover + Anchor instead of shadcn's Command/cmdk
 * combobox — no new dependency, and the "value is just text" model fits
 * "allow free text" more directly than a picker built around committing to
 * one list item. */
export function CityCombobox({ id, value, onChange, placeholder, className }: CityComboboxProps) {
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { data: cities } = useQuery({
    queryKey: ["event-cities"],
    queryFn: getEventCities,
    staleTime: 5 * 60 * 1000,
  })

  const normalized = value.trim().toLowerCase()
  const suggestions = (cities ?? [])
    .filter((city) => !normalized || city.toLowerCase().includes(normalized))
    .filter((city) => city.toLowerCase() !== normalized)
    .slice(0, MAX_SUGGESTIONS)

  return (
    <Popover open={open && suggestions.length > 0} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <Input
          ref={inputRef}
          id={id}
          value={value}
          placeholder={placeholder}
          autoComplete="off"
          className={className}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
        />
      </PopoverAnchor>
      <PopoverContent
        align="start"
        sideOffset={4}
        className="w-(--radix-popover-trigger-width) p-1"
        onOpenAutoFocus={(e) => e.preventDefault()}
        // PopoverAnchor (unlike PopoverTrigger) doesn't get Radix's usual
        // "ignore the element that opened me" exclusion — without this, the
        // very focus event that opens the popover gets read by Radix's
        // DismissableLayer as a focus landing "outside" the content, and it
        // immediately closes again. Telling it to ignore focus specifically
        // landing back on our own input fixes that.
        onFocusOutside={(e) => {
          if (e.target === inputRef.current) e.preventDefault()
        }}
      >
        <div className="flex flex-col">
          {suggestions.map((city) => (
            <button
              key={city}
              type="button"
              // mousedown (not click) + preventDefault: fires before the
              // input's onBlur, so the click lands instead of the popover
              // closing itself out from under the cursor first.
              onMouseDown={(e) => {
                e.preventDefault()
                onChange(city)
                setOpen(false)
              }}
              className={cn(
                "rounded-md px-2 py-1.5 text-left text-sm outline-none",
                "hover:bg-accent hover:text-accent-foreground",
              )}
            >
              {city}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
