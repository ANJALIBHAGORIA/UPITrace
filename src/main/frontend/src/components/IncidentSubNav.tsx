import { NavLink } from "react-router-dom"

export function IncidentSubNav({ id }: { id: string }) {
  const tabs = [
    { to: `/incidents/${id}`, label: "Overview", end: true },
    { to: `/incidents/${id}/timeline`, label: "Timeline" },
    { to: `/incidents/${id}/evidence`, label: "Evidence" },
    { to: `/incidents/${id}/similar`, label: "Similar & Runbooks" },
    { to: `/incidents/${id}/investigation`, label: "AI Investigation" },
    { to: `/incidents/${id}/actions`, label: "Actions" },
  ]
  return (
    <div className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
              isActive
                ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  )
}
