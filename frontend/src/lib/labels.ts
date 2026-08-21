export const CATEGORY_LABEL: Record<string, string> = {
  show: "Show",
  movie: "Filme",
}

/** Two treatments within the brand teal family — kept on-brand instead of
 * introducing an unrelated hue just to tell the two categories apart. */
export const CATEGORY_BADGE_CLASS: Record<string, string> = {
  show: "border-primary/20 bg-primary/10 text-primary",
  movie: "border-transparent bg-accent text-accent-foreground",
}

export const EVENT_STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  published: "Publicado",
  canceled: "Cancelado",
}

export const EVENT_STATUS_BADGE_CLASS: Record<string, string> = {
  draft: "border-border bg-muted text-muted-foreground",
  published: "border-success/20 bg-success/10 text-success",
  canceled: "border-destructive/20 bg-destructive/10 text-destructive",
}
