import { JobCreateResponse, JobStatus, Recipient, RecipientInput } from './types'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '')

export async function createJob(
  recipients: RecipientInput[],
  templateName: string = 'blood_donation'
): Promise<JobCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipients,
      template_name: templateName,
    }),
  })

  if (!response.ok) {
    let errorDetail = 'Failed to create certificate job'
    try {
      const errorJson = await response.json()
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string'
          ? errorJson.detail
          : JSON.stringify(errorJson.detail)
      }
    } catch {
      // fallback to generic message
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch job status (${response.status})`)
  }

  return response.json()
}

export async function getJobRecipients(jobId: string): Promise<Recipient[]> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/recipients`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch job recipients (${response.status})`)
  }

  return response.json()
}

export function getCertificateUrl(recipientId: string): string {
  return `${API_BASE_URL}/api/certificates/${recipientId}/`
}

export function getBulkDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${jobId}/certificates/download`
}
