import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadPublishedDataset } from './dataset'

afterEach(() => vi.unstubAllGlobals())

describe('loadPublishedDataset', () => {
  it('bypasses stale deployment caches', async () => {
    const payload = { schema_version: 2, projects: [] }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(payload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadPublishedDataset()).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('data/dataset.json'), {
      cache: 'no-store',
    })
  })
})
