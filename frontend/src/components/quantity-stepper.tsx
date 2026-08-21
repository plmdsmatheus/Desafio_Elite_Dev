import { Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"

interface QuantityStepperProps {
  value: number
  max: number
  onChange: (value: number) => void
  /** Tighter buttons/spacing for cramped layouts (the mobile bottom bar). */
  compact?: boolean
}

export function QuantityStepper({ value, max, onChange, compact = false }: QuantityStepperProps) {
  const buttonSize = compact ? "icon-xs" : "icon-sm"

  return (
    <div className={compact ? "inline-flex items-center gap-0.5 rounded-lg border px-0.5" : "inline-flex items-center gap-1 rounded-lg border px-1"}>
      <Button
        type="button"
        variant="ghost"
        size={buttonSize}
        disabled={value <= 1}
        onClick={() => onChange(value - 1)}
        aria-label="Diminuir quantidade"
      >
        <Minus />
      </Button>
      <span className={compact ? "w-4 text-center text-xs font-medium tabular-nums" : "w-6 text-center text-sm font-medium tabular-nums"}>
        {value}
      </span>
      <Button
        type="button"
        variant="ghost"
        size={buttonSize}
        disabled={value >= max}
        onClick={() => onChange(value + 1)}
        aria-label="Aumentar quantidade"
      >
        <Plus />
      </Button>
    </div>
  )
}
