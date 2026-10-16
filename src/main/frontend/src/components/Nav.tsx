import { NavLink } from "react-router-dom"

const links = [
  { to: "/", label: "Incidents" },
  { to: "/simulator", label: "UPI Simulator" },
  { to: "/merchant", label: "Merchant Portal" },
  { to: "/incidents/new", label: "New Incident" },
]

export function Nav() {
  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
        <span className="text-lg font-bold text-slate-900 dark:text-white">UPITrace</span>
        <nav className="flex gap-4">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? "text-indigo-600 dark:text-indigo-400" : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
