interface PagePlaceholderProps {
  title: string
}

/** Temporary stub — real screens land in the next checkpoint. */
export function PagePlaceholder({ title }: PagePlaceholderProps) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">Em construção.</p>
    </div>
  )
}
