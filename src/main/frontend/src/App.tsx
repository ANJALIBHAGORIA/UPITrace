import { Navigate, Route, Routes } from "react-router-dom"
import { Sidebar } from "./components/Sidebar"
import { ActionsAndVerification } from "./pages/ActionsAndVerification"
import { DemoWalkthrough } from "./pages/DemoWalkthrough"
import { EvidenceDetails } from "./pages/EvidenceDetails"
import { EventTimeline } from "./pages/EventTimeline"
import { IncidentList } from "./pages/IncidentList"
import { IncidentOverview } from "./pages/IncidentOverview"
import { Investigation } from "./pages/Investigation"
import { LiveDemo } from "./pages/LiveDemo"
import { NewIncident } from "./pages/NewIncident"
import { SimilarCasesAndRunbooks } from "./pages/SimilarCasesAndRunbooks"

export default function App() {
  return (
    <div className="flex min-h-svh bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <main className="mx-auto w-full max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<IncidentList />} />
          <Route path="/demo" element={<LiveDemo />} />
          <Route path="/incidents/new" element={<NewIncident />} />
          <Route path="/incidents/:id" element={<IncidentOverview />} />
          <Route path="/incidents/:id/demo" element={<DemoWalkthrough />} />
          <Route path="/incidents/:id/timeline" element={<EventTimeline />} />
          <Route path="/incidents/:id/evidence" element={<EvidenceDetails />} />
          <Route path="/incidents/:id/similar" element={<SimilarCasesAndRunbooks />} />
          <Route path="/incidents/:id/investigation" element={<Investigation />} />
          <Route path="/incidents/:id/actions" element={<ActionsAndVerification />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
