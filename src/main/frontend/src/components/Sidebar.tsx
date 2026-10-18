import { NavLink, useLocation } from "react-router-dom"

const globalLinks = [
  { to: "/", label: "Cases", icon: "📁" },
  { to: "/incidents/new", label: "New Incident", icon: "➕" },
  { to: "/demo", label: "Live Demo", icon: "📱" },
]

export function Sidebar() {
  const { pathname } = useLocation()
  const match = pathname.match(/^\/incidents\/([^/]+)/)
  const incidentId = match && match[1] !== "new" ? match[1] : null

  const incidentTabs = incidentId
    ? [
        { to: `/incidents/${incidentId}/demo`, label: "Demo" },
        { to: `/incidents/${incidentId}`, label: "Incident Overview", end: true },
        { to: `/incidents/${incidentId}/timeline`, label: "Event Timeline" },
        { to: `/incidents/${incidentId}/evidence`, label: "Evidence Details" },
        { to: `/incidents/${incidentId}/similar`, label: "Similar Incidents" },
        { to: `/incidents/${incidentId}/investigation`, label: "AI Analysis" },
        { to: `/incidents/${incidentId}/actions`, label: "Recommended Actions" },
      ]
    : []

  return (
    <aside className="flex w-60 shrink-0 flex-col bg-slate-900 px-3 py-6 text-slate-300">
      <div className="mb-6 px-2 text-lg font-bold text-white">UPITrace</div>
      <nav className="flex flex-col gap-1">
        {globalLinks.map((l) => (
          <SidebarLink key={l.to} to={l.to} end={l.to === "/"}>
            <span>{l.icon}</span>{l.label}
          </SidebarLink>
        ))}
      </nav>

      {incidentId && (
        <>
          <div className="mt-6 mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {incidentId}
          </div>
          <nav className="flex flex-col gap-1">
            {incidentTabs.map((t) => (
              <SidebarLink key={t.to} to={t.to} end={t.end}>{t.label}</SidebarLink>
            ))}
          </nav>
        </>
      )}
    </aside>
  )
}

function SidebarLink({ to, end, children }: { to: string; end?: boolean; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
          isActive ? "bg-indigo-600 text-white" : "hover:bg-slate-800 hover:text-white"
        }`
      }
    >
      {children}
    </NavLink>
  )
}
