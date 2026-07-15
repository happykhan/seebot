import { describe, expect, it } from 'vitest'
import { activeLabelKeys, filterProjects } from './projects'
import type { ProjectSummary } from './types'

const projects: ProjectSummary[] = [
  {
    id: 'aligner',
    name: 'Example aligner',
    description: 'Aligns reads',
    category: 'sequence_alignment',
    tags: [],
    included: true,
    exclusion_code: null,
    repository_url: 'https://github.com/example/aligner',
    snapshot_date: '2026-07-01',
    languages: ['c'],
    primary_executable: 'aligner',
    valid_run_status: 'reviewed',
    curation_status: 'reviewed',
    labels: {
      usage_exemplar: true,
      repository_practice_exemplar: false,
      complete_assessment: true,
      practice_exemplar: false,
    },
  } as unknown as ProjectSummary,
  {
    id: 'trimmer',
    name: 'Read trimmer',
    description: 'Trims adapters',
    category: 'read_preprocessing',
    tags: [],
    included: true,
    exclusion_code: null,
    repository_url: 'https://github.com/example/trimmer',
    snapshot_date: '2026-07-01',
    languages: ['python', 'cython'],
    primary_executable: 'trimmer',
    valid_run_status: 'draft',
    curation_status: 'in_review',
    labels: {
      usage_exemplar: false,
      repository_practice_exemplar: false,
      complete_assessment: false,
      practice_exemplar: false,
    },
  } as unknown as ProjectSummary,
]

describe('filterProjects', () => {
  it('combines text, language, and category filters without ranking projects', () => {
    expect(filterProjects(projects, 'read', 'python', 'read_preprocessing').map(({ id }) => id)).toEqual(['trimmer'])
    expect(filterProjects(projects, 'alignment', 'all', 'all').map(({ id }) => id)).toEqual(['aligner'])
  })
})

describe('activeLabelKeys', () => {
  it('returns only factual labels whose conditions were met', () => {
    expect(activeLabelKeys(projects[0].labels)).toEqual(['usage_exemplar', 'complete_assessment'])
    expect(activeLabelKeys(projects[1].labels)).toEqual([])
  })
})
