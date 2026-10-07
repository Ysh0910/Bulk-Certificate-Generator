import React, { useState } from 'react'
import { createJob } from './api'
import { RecipientInput } from './types'

interface DonorFormProps {
  onJobCreated: (jobId: string) => void
  disabled?: boolean
}

interface FormRow {
  id: string
  name: string
  email: string
  bloodGroup: string
  donationDate: string
  campName: string
  organization: string
  unitsDonated: string
}

const createInitialRow = (): FormRow => ({
  id: Math.random().toString(36).substring(2, 9),
  name: '',
  email: '',
  bloodGroup: 'O+',
  donationDate: new Date().toISOString().split('T')[0],
  campName: '',
  organization: '',
  unitsDonated: '1',
})

export const DonorForm: React.FC<DonorFormProps> = ({ onJobCreated, disabled = false }) => {
  const [rows, setRows] = useState<FormRow[]>([createInitialRow()])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFieldChange = (id: string, field: keyof FormRow, value: string) => {
    setRows((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [field]: value } : row))
    )
  }

  const handleAddRow = (e: React.MouseEvent) => {
    e.preventDefault()
    setRows((prev) => [...prev, createInitialRow()])
  }

  const handleRemoveRow = (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    if (rows.length <= 1) return
    setRows((prev) => prev.filter((r) => r.id !== id))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validate rows
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i]
      if (!row.name.trim()) {
        setError(`Please enter a name for donor #${i + 1}`)
        return
      }
      if (!row.email.trim() || !row.email.includes('@')) {
        setError(`Please enter a valid email for donor #${i + 1}`)
        return
      }
    }

    const payload: RecipientInput[] = rows.map((row) => ({
      name: row.name.trim(),
      email: row.email.trim(),
      extra_fields: {
        blood_group: row.bloodGroup.trim(),
        donation_date: row.donationDate.trim(),
        camp_name: row.campName.trim(),
        organization: row.organization.trim(),
        units_donated: row.unitsDonated.trim(),
      },
    }))

    setSubmitting(true)
    try {
      const result = await createJob(payload, 'blood_donation')
      onJobCreated(result.id)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create job'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="pt-6">
      <div className="space-y-6">
        {rows.map((row, index) => (
          <div
            key={row.id}
            className={index > 0 ? 'pt-6 border-t border-line' : ''}
          >
            <div className="flex items-baseline justify-between mb-3">
              <span className="font-serif text-ink text-base">
                Donor {rows.length > 1 ? `#${index + 1}` : 'details'}
              </span>
              {rows.length > 1 && (
                <button
                  type="button"
                  onClick={(e) => handleRemoveRow(row.id, e)}
                  disabled={submitting || disabled}
                  className="text-xs text-muted hover:text-blood cursor-pointer"
                >
                  remove
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Full name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Eleanor Vance"
                  value={row.name}
                  onChange={(e) => handleFieldChange(row.id, 'name', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink placeholder:text-muted/60 text-sm focus:outline-none focus:border-blood"
                />
              </div>

              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Email address
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. eleanor@example.com"
                  value={row.email}
                  onChange={(e) => handleFieldChange(row.id, 'email', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink placeholder:text-muted/60 text-sm focus:outline-none focus:border-blood"
                />
              </div>

              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Blood group
                </label>
                <select
                  value={row.bloodGroup}
                  onChange={(e) => handleFieldChange(row.id, 'bloodGroup', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-paper border border-line px-2.5 py-1.5 text-ink text-sm focus:outline-none focus:border-blood"
                >
                  <option value="O+">O+</option>
                  <option value="O-">O-</option>
                  <option value="A+">A+</option>
                  <option value="A-">A-</option>
                  <option value="B+">B+</option>
                  <option value="B-">B-</option>
                  <option value="AB+">AB+</option>
                  <option value="AB-">AB-</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Units donated
                </label>
                <input
                  type="text"
                  placeholder="1"
                  value={row.unitsDonated}
                  onChange={(e) => handleFieldChange(row.id, 'unitsDonated', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink placeholder:text-muted/60 text-sm focus:outline-none focus:border-blood"
                />
              </div>

              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Donation date
                </label>
                <input
                  type="date"
                  value={row.donationDate}
                  onChange={(e) => handleFieldChange(row.id, 'donationDate', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink text-sm focus:outline-none focus:border-blood"
                />
              </div>

              <div>
                <label className="block text-xs text-muted mb-1 font-normal">
                  Camp or hospital name
                </label>
                <input
                  type="text"
                  placeholder="e.g. City Blood Drive"
                  value={row.campName}
                  onChange={(e) => handleFieldChange(row.id, 'campName', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink placeholder:text-muted/60 text-sm focus:outline-none focus:border-blood"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs text-muted mb-1 font-normal">
                  Issuing organization
                </label>
                <input
                  type="text"
                  placeholder="e.g. Red Cross Blood Services"
                  value={row.organization}
                  onChange={(e) => handleFieldChange(row.id, 'organization', e.target.value)}
                  disabled={submitting || disabled}
                  className="w-full bg-transparent border border-line px-2.5 py-1.5 text-ink placeholder:text-muted/60 text-sm focus:outline-none focus:border-blood"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="pt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={handleAddRow}
          disabled={submitting || disabled}
          className="text-sm text-blood hover:underline cursor-pointer disabled:opacity-50"
        >
          + Add another donor
        </button>

        <button
          type="submit"
          disabled={submitting || disabled}
          className="border border-line bg-ink text-paper px-4 py-1.5 text-sm font-normal hover:bg-blood hover:border-blood disabled:opacity-50 cursor-pointer"
        >
          {submitting ? 'Creating job...' : 'Record & Generate'}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-xs text-blood">
          {error}
        </p>
      )}
    </form>
  )
}
