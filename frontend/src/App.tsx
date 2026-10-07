import { useState } from 'react'
import { DonorForm } from './DonorForm'
import { DonationLedger } from './DonationLedger'

export default function App() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)

  return (
    <main className="min-h-screen bg-paper text-ink px-4 py-16 md:py-24">
      <div className="max-w-[680px] mx-auto">
        {/* Header / Hero */}
        <header className="pb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <svg
                className="w-5 h-5 text-blood inline-block shrink-0"
                viewBox="0 0 24 24"
                fill="currentColor"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
              </svg>
              <h1 className="font-serif text-2xl text-ink font-normal">
                Donor Certificates
              </h1>
            </div>

            {currentJobId && (
              <button
                type="button"
                onClick={() => setCurrentJobId(null)}
                className="text-xs text-muted hover:text-ink cursor-pointer"
              >
                New entry
              </button>
            )}
          </div>
          <p className="text-sm text-muted mt-1.5 font-normal">
            Official blood donation record and certificate generation ledger.
          </p>
        </header>

        {/* Section Divider */}
        <div className="border-t border-line" />

        {/* Active Ledger (if job created) */}
        {currentJobId ? (
          <DonationLedger jobId={currentJobId} />
        ) : (
          /* Donor Entry Form */
          <DonorForm onJobCreated={(id) => setCurrentJobId(id)} />
        )}
      </div>
    </main>
  )
}
