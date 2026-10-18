import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button, Card } from "../components/ui"
import { MerchantCard, PhoneCard, PhoneSuccessState } from "../components/PhoneAndMerchantCards"

// Interactive, client-side only (nothing is written to the backend until you
// click "Create Incident") — enter an amount, pay, watch the merchant side
// fail to find the order, then carry that exact data into a real incident.
export function LiveDemo() {
  const navigate = useNavigate()
  const [amount, setAmount] = useState("2499")
  const [merchant, setMerchant] = useState("IRCTC")
  const [paid, setPaid] = useState(false)
  const [utr, setUtr] = useState("")

  function pay() {
    if (!amount.trim() || Number.isNaN(Number(amount)) || Number(amount) <= 0) return
    setUtr(`SIM-${Date.now().toString().slice(-10)}`)
    setPaid(true)
  }

  function reset() {
    setPaid(false)
    setUtr("")
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Live demo: simulate a payment</h1>
        <p className="text-sm text-slate-500">
          Nothing is saved yet — this is purely illustrative. Creating the incident afterward is what talks to the real backend.
        </p>
      </div>

      {!paid && (
        <Card className="max-w-md">
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Amount (₹)</span>
              <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Pay to</span>
              <select className="input" value={merchant} onChange={(e) => setMerchant(e.target.value)}>
                {["IRCTC", "BigBasket", "Zomato", "BookMyShow", "Flipkart"].map((m) => <option key={m}>{m}</option>)}
              </select>
            </label>
            <Button onClick={pay}>Pay now</Button>
          </div>
        </Card>
      )}

      {paid && (
        <>
          <div className="grid gap-6 md:grid-cols-2">
            <PhoneCard>
              <PhoneSuccessState amount={amount} merchant={merchant} utr={utr} time={new Date().toLocaleString()} />
            </PhoneCard>
            <MerchantCard
              merchant={merchant}
              orderConfirmed={false}
              rows={[{ amount, paymentId: utr, statusLabel: "PENDING", highlight: true }]}
            />
          </div>
          <div className="flex justify-center gap-3">
            <Button
              onClick={() =>
                navigate(
                  `/incidents/new?amount=${encodeURIComponent(amount)}&merchant_id=${encodeURIComponent(merchant)}&transaction_ref=${encodeURIComponent(utr)}`,
                )
              }
            >
              Create incident from this payment →
            </Button>
            <Button variant="secondary" onClick={reset}>Try a different amount</Button>
          </div>
        </>
      )}
    </div>
  )
}
