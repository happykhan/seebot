import type { Dataset } from './types'

export async function loadPublishedDataset(): Promise<Dataset> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/dataset.json`, {
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`Dataset returned ${response.status}`)
  return response.json() as Promise<Dataset>
}
