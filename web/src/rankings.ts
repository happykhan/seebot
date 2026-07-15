import type { AwardRanking } from './types'

export type RankingSort = 'score' | 'name' | 'testing' | 'automation' | 'documentation'

export function filterAndSortRankings(
  rankings: AwardRanking[],
  query: string,
  category: string,
  sort: RankingSort,
): AwardRanking[] {
  const normalized = query.trim().toLowerCase()
  return rankings
    .filter((item) =>
      (category === 'all' || item.category === category)
      && (!normalized || `${item.name} ${item.description} ${item.category}`.toLowerCase().includes(normalized)),
    )
    .sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name)
      if (sort !== 'score') return b.breakdown[sort] - a.breakdown[sort] || a.name.localeCompare(b.name)
      return b.score - a.score || a.name.localeCompare(b.name)
    })
}

export function rankingPage(rankings: AwardRanking[], page: number, pageSize: number) {
  const pages = Math.max(1, Math.ceil(rankings.length / pageSize))
  const currentPage = Math.max(1, Math.min(page, pages))
  return {
    currentPage,
    pages,
    items: rankings.slice((currentPage - 1) * pageSize, currentPage * pageSize),
  }
}
