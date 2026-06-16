interface StatusBadgeProps {
  ok: boolean
  label: string
}

export function StatusBadge({ ok, label }: StatusBadgeProps) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-raised px-2.5 py-1 text-xs">
      <span
        className={`h-2 w-2 rounded-full ${ok ? 'bg-success' : 'bg-danger'}`}
        aria-hidden
      />
      <span className="text-text-muted">{label}</span>
    </span>
  )
}
