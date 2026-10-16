import { Navigate, Route, Routes } from "react-router-dom"
import { Nav } from "./components/Nav"
import { ActionsAndVerification } from "./pages/ActionsAndVerification"
import { CustomerSimulator } from "./pages/CustomerSimulator"
import { EvidenceDetails } from "./pages/EvidenceDetails"
import { EventTimeline } from "./pages/EventTimeline"
import { IncidentList } from "./pages/IncidentList"
import { IncidentOverview } from "./pages/IncidentOverview"
import { Investigation } from "./pages/Investigation"
import { MerchantPortal } from "./pages/MerchantPortal"
import { NewIncident } from "./pages/NewIncident"
import { SimilarCasesAndRunbooks } from "./pages/SimilarCasesAndRunbooks"

export default function App() {
  return (
    <div className="min-h-svh bg-slate-50 dark:bg-slate-950">
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<IncidentList />} />
          <Route path="/simulator" element={<CustomerSimulator />} />
          <Route path="/merchant" element={<MerchantPortal />} />
          <Route path="/incidents/new" element={<NewIncident />} />
          <Route path="/incidents/:id" element={<IncidentOverview />} />
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
