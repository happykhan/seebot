import { useMemo, useState } from 'react'
import { describeRule, severityClass } from './catalogue'
import type { AggregateRule } from './types'
import { InfoTip, SelectField } from './ui'

type SortKey = 'language' | 'analyzer' | 'rule' | 'native_severity' | 'project_count' | 'count'

export function FindingsTable({ rows }: { rows: AggregateRule[] }) {
  const [kind, setKind] = useState<'lint' | 'security'>('lint')
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('count')
  const [descending, setDescending] = useState(true)
  const [page, setPage] = useState(1)
  const pageSize = 15
  const visible = useMemo(() => rows.filter((row) => {
    const description = describeRule(row.analyzer, row.rule)
    return row.kind === kind && `${row.language} ${row.analyzer} ${row.rule} ${row.native_severity ?? ''} ${description}`.toLowerCase().includes(query.toLowerCase())
  }).sort((a, b) => {
    const left = a[sortKey] ?? ''
    const right = b[sortKey] ?? ''
    const comparison = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right))
    return descending ? -comparison : comparison
  }), [descending, kind, query, rows, sortKey])
  const pages = Math.max(1, Math.ceil(visible.length / pageSize))
  const currentPage = Math.min(page, pages)
  const paged = visible.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const sort = (key: SortKey) => {
    if (sortKey === key) setDescending((value) => !value)
    else { setSortKey(key); setDescending(false) }
    setPage(1)
  }
  const heading = (label: string, key: SortKey) => <button type="button" onClick={() => sort(key)}>{label}<span>{sortKey === key ? (descending ? '↓' : '↑') : '↕'}</span></button>

  return <>
    <div className="table-controls">
      <label className="search-field"><span>Search findings</span><input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Rule, analyzer, language or description" /></label>
      <SelectField label="Finding type" value={kind} onChange={(event) => { setKind(event.target.value as 'lint' | 'security'); setPage(1) }}>
        <option value="lint">Code style and maintainability</option>
        <option value="security">Source security</option>
      </SelectField>
    </div>
    <div className="data-table-wrap"><table className="data-table"><thead><tr>
      <th>{heading('Language', 'language')}</th><th>{heading('Analyzer', 'analyzer')}</th><th>{heading('Rule', 'rule')}</th>
      <th>{heading('Severity', 'native_severity')}</th><th>{heading('Software', 'project_count')}</th><th>{heading('Findings', 'count')}</th>
    </tr></thead><tbody>{paged.map((row) => <tr key={`${row.kind}-${row.language}-${row.analyzer}-${row.rule}`}>
      <td>{row.language}</td><td>{row.analyzer}</td><td><code>{row.rule}</code> <InfoTip>{describeRule(row.analyzer, row.rule)}</InfoTip></td>
      <td><span className={`severity-badge ${severityClass(row.native_severity)}`}>{row.native_severity ?? 'Unspecified'}</span></td>
      <td>{row.project_count}</td><td>{row.count}</td>
    </tr>)}</tbody></table></div>
    <div className="pagination"><span>{visible.length} rules · page {currentPage} of {pages}</span><div><button disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Previous</button><button disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Next</button></div></div>
  </>
}
