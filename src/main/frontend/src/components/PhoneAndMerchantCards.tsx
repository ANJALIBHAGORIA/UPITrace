import type { ReactNode } from "react"

// Shared visual building blocks for the "user side (UPI app) vs business
// side (merchant portal)" story — used by both the interactive LiveDemo and
// the read-only per-incident DemoWalkthrough so the two always look the same.

export function PhoneCard({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-[300px] flex-col overflow-hidden rounded-[2.5rem] border-[10px] border-slate-900 bg-white shadow-xl dark:bg-slate-950" style={{ height: 600 }}>
      {/* Status bar */}
      <div className="flex items-center justify-between px-5 pt-2 pb-1 text-[11px] font-semibold text-slate-900 dark:text-white">
        <span>9:41</span>
        <div className="h-4 w-20 rounded-full bg-slate-900 dark:bg-white" /> {/* notch */}
        <span>📶 🔋</span>
      </div>
      {/* App header */}
      <div className="flex items-center gap-2 bg-indigo-600 px-4 py-3 text-white">
        <span>←</span>
        <span className="text-sm font-semibold">UPI Pay</span>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-6">{children}</div>
      {/* Home indicator */}
      <div className="flex justify-center pb-2">
        <div className="h-1 w-24 rounded-full bg-slate-300 dark:bg-slate-700" />
      </div>
    </div>
  )
}

export function PhoneSuccessState({ amount, merchant, utr, time }: { amount: string; merchant: string; utr: string; time: string }) {
  return (
    <>
      <div className="flex flex-col items-center gap-2 pt-4 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl dark:bg-emerald-900/40">✓</div>
        <p className="font-semibold text-emerald-600">Payment Successful</p>
        <p className="text-3xl font-bold text-slate-900 dark:text-white">₹{amount}</p>
        <p className="text-sm text-slate-500">Paid to {merchant}</p>
      </div>
      <div className="mt-8 space-y-3 rounded-xl border border-slate-100 bg-slate-50 p-4 text-xs dark:border-slate-800 dark:bg-slate-900">
        <Row label="UTR" value={utr} />
        <Row label="Date & Time" value={time} />
        <Row label="Payment method" value="UPI" />
        <Row label="Status" value="Payment Successful" />
      </div>
      <div className="mt-6 flex justify-center gap-6 text-center text-[11px] text-slate-500">
        <span>📄<br />View Details</span>
        <span>📤<br />Share Receipt</span>
        <span>🆘<br />Get Help</span>
      </div>
    </>
  )
}

export function MerchantCard({
  merchant, rows, orderConfirmed,
}: {
  merchant: string
  orderConfirmed: boolean
  rows: { amount: string; paymentId: string; statusLabel: string; highlight?: boolean }[]
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <p className="mb-3 text-xs font-semibold text-slate-400">{merchant} — Merchant dashboard</p>
      {!orderConfirmed ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
          <strong>Order not confirmed</strong> — no booking found for this payment. Status: Pending.
        </div>
      ) : (
        <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
          Order confirmed and matched to this payment.
        </div>
      )}
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-slate-400">
            <th className="pb-1 font-medium">Amount</th>
            <th className="pb-1 font-medium">Payment ID</th>
            <th className="pb-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={`border-t border-slate-100 dark:border-slate-800 ${r.highlight ? "bg-amber-50 dark:bg-amber-950/20" : ""}`}>
              <td className="py-2 font-medium">₹{r.amount}</td>
              <td className="py-2 font-mono">{r.paymentId}</td>
              <td className="py-2">
                <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {r.statusLabel}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-700 dark:text-slate-300">{value}</span>
    </div>
  )
}
