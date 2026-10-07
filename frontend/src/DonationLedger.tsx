import React, { useEffect, useState } from 'react'
import { getBulkDownloadUrl, getCertificateUrl, getJobRecipients, getJobStatus } from './api'
import { JobStatus, Recipient } from './types'

interface DonationLedgerProps {
  jobId: string
}

export const DonationLedger: React.FC<DonationLedgerProps> = ({ jobId }) => {
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [recipients, setRecipients] = useState<Recipient[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    const poll = async () => {
      try {
        const [jobStatus, recipientList] = await Promise.all([
          getJobStatus(jobId),
          getJobRecipients(jobId),
        ])

        if (!isMounted) return

        setStatus(jobStatus)
        setRecipients(recipientList)

        // Stop polling if job reached terminal status
        if (
          jobStatus.overall_status !== 'PENDING' &&
          jobStatus.overall_status !== 'PROCESSING'
        ) {
          if (intervalId) clearInterval(intervalId)
        }
      } catch (err: unknown) {
        if (!isMounted) return
        const message = err instanceof Error ? err.message : 'Error polling status'
        setError(message)
      }
    }

    // Initial fetch immediately
    poll()

    // Poll every 2 seconds
    const intervalId = setInterval(poll, 2000)

    return () => {
      isMounted = false
      clearInterval(intervalId)
    }
  }, [jobId])

  const total = status?.total_count || 0
  const processed = (status?.success_count || 0) + (status?.failure_count || 0)
  const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0
  const isDone =
    status?.overall_status === 'COMPLETED' ||
    status?.overall_status === 'COMPLETED_WITH_ERRORS' ||
    status?.overall_status === 'FAILED'

  const hasSuccess = (status?.success_count || 0) > 0

  return (
    <div className="pt-8">
      {/* The single live visual element: thin progress line */}
      <div className="space-y-2">
        <div className="h-[2px] w-full bg-line overflow-hidden">
          <div
            className="h-full bg-blood-bright"
            style={{
              width: `${percent}%`,
              transition: 'width 0.4s ease-out',
            }}
          />
        </div>

        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            {processed} of {total} processed
          </span>
          {isDone && (
            <span className="text-ink">
              {status?.overall_status === 'COMPLETED'
                ? 'Complete'
                : status?.overall_status === 'COMPLETED_WITH_ERRORS'
                ? 'Completed with errors'
                : 'Failed'}
            </span>
          )}
        </div>
      </div>

      {error && (
        <p className="mt-3 text-xs text-blood">
          {error}
        </p>
      )}

      {/* Recipient list & Download All */}
      <div className="mt-8 border-t border-line pt-4">
        <div className="flex items-baseline justify-between mb-4">
          <span className="font-serif text-ink text-base">
            Recipient register
          </span>

          {isDone && hasSuccess && (
            <a
              href={getBulkDownloadUrl(jobId)}
              download
              className="text-xs text-ink border border-line px-2.5 py-1 hover:border-blood hover:text-blood"
            >
              Download all certificates (.zip)
            </a>
          )}
        </div>

        <div className="divide-y divide-line">
          {recipients.length === 0 ? (
            <p className="py-4 text-xs text-muted">
              Waiting for recipient records...
            </p>
          ) : (
            recipients.map((recipient) => (
              <div
                key={recipient.id}
                className="py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="font-serif text-ink text-sm truncate">
                    {recipient.name}
                  </div>
                  <div className="text-xs text-muted truncate">
                    {recipient.email}
                  </div>
                  {recipient.status === 'FAILED' && recipient.error_message && (
                    <div className="text-xs text-blood mt-0.5">
                      {recipient.error_message}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="flex items-center gap-1.5 text-xs">
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full ${
                        recipient.status === 'SUCCESS'
                          ? 'bg-success'
                          : recipient.status === 'FAILED'
                          ? 'bg-blood'
                          : 'bg-muted'
                      }`}
                    />
                    <span
                      className={
                        recipient.status === 'SUCCESS'
                          ? 'text-success'
                          : recipient.status === 'FAILED'
                          ? 'text-blood'
                          : 'text-muted'
                      }
                    >
                      {recipient.status === 'SUCCESS'
                        ? 'Ready'
                        : recipient.status === 'FAILED'
                        ? 'Failed'
                        : 'Pending'}
                    </span>
                  </div>

                  {recipient.status === 'SUCCESS' && (
                    <a
                      href={getCertificateUrl(recipient.id)}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blood hover:underline"
                    >
                      Download
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
