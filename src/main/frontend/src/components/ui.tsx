import type { ReactNode } from "react"

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {children}
    </div>
  )
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{children}</h2>
}

const STATUS_COLORS: Record<string, string> = {
  CONFIRMED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  RESOLVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  AWAITING_EVIDENCE: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  OPEN: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  INVESTIGATING: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  STATUS_MISMATCH: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  MERCHANT_CONFIRMATION_MISSING: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  INSUFFICIENT_EVIDENCE: "bg-slate-200 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300",
  POSSIBLE_DUPLICATE: "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900/40 dark:text-fuchsia-300",
  REVERSAL_UNVERIFIED: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  UNRESOLVED: "bg-slate-200 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300",
  VERIFIED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  UNVERIFIED: "bg-slate-200 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300",
  CONFLICTED: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  SIMULATED: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  LIVE: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  UNAVAILABLE: "bg-slate-200 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300",
}

export function Badge({ value }: { value: string }) {
  const classes = STATUS_COLORS[value] ?? "bg-slate-200 text-slate-700 dark:bg-slate-700/60 dark:text-slate-300"
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>{value.replaceAll("_", " ")}</span>
}

export function Button({
  children, onClick, variant = "primary", disabled, type = "button",
}: {
  children: ReactNode
  onClick?: () => void
  variant?: "primary" | "secondary" | "danger"
  disabled?: boolean
  type?: "button" | "submit"
}) {
  const base = "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50"
  const variants = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-500",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700",
    danger: "bg-rose-600 text-white hover:bg-rose-500",
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${variants[variant]}`}>
      {children}
    </button>
  )
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
      {message}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <p className="text-sm italic text-slate-400 dark:text-slate-500">{message}</p>
}

export function List({ items }: { items: string[] }) {
  if (items.length === 0) return <EmptyState message="None" />
  return (
    <ul className="list-inside list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
      {items.map((item, i) => <li key={i}>{item.replaceAll("_", " ")}</li>)}
    </ul>
  )
}
