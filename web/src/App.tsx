import { useEffect, useMemo, useState } from 'react'
import { NavBar } from '@genomicx/ui'
import { useLocation } from 'react-router-dom'
import type { Dataset, ExemplarLabels, ProjectSummary } from './types'
import { activeLabelKeys, filterProjects, labelNames } from './projects'

function pretty(value: string | null): string {
  return value ? value.replaceAll('_', ' ') : 'Not classified'
}

function assessmentState(project: ProjectSummary): string {
  if (!project.included) return `Excluded · ${pretty(project.exclusion_code)}`
  if (project.curation_status === 'reviewed') return 'Assessed'
  if (project.curation_status === 'adjudication_required') return 'Review required'
  return 'Not yet assessed'
}

function LabelList({ labels }: { labels: ExemplarLabels }) {
  const active = activeLabelKeys(labels)
  if (active.length === 0) return <span className="quiet-label">No exemplar label</span>
  return <div className="label-list">{active.map((key) => <span key={key}>{labelNames[key]}</span>)}</div>
}

function Overview({ dataset }: { dataset: Dataset }) {
  const included = dataset.projects.filter((project) => project.included)
  const measured = included.filter((project) => project.curation_status === 'reviewed').length
  const cards = [
    ['Repository health', 'Activity, verification CI, standard test patterns, documentation, licence and citation.'],
    ['Code health', 'Language-specific structural measurements and native analyzer findings from production source.'],
    ['Usage health', 'A real miniature run plus bounded probes for malformed and unexpected input.'],
  ]
  return <>
    <section className="hero">
      <div><p className="eyebrow">Scientific software observatory</p><h1>Evidence about code.<br /><em>Not a quality score.</em></h1><p>Seebot records how scientific tools are maintained, structured, documented and behaved when exercised with valid and deliberately awkward input.</p></div>
      <aside><span>Canonical snapshot</span><strong>{dataset.snapshot_date}</strong><p>{dataset.summary.included_projects} eligible projects catalogued · {measured} complete reports published</p></aside>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><p className="eyebrow">Assessment model</p><h2>Three independent views of each project</h2></div><p>Measurements remain separate. Seebot does not collapse different practices, languages, or analyzer findings into one number.</p></div>
      <div className="pillar-grid">{cards.map(([title, description]) => <article key={title}><span>0{cards.findIndex((card) => card[0] === title) + 1}</span><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><p className="eyebrow">Factual recognition</p><h2>Exemplars require complete evidence</h2></div><p>Code-health values never qualify or disqualify a project. Labels reflect observable practices, graceful executable behaviour, and assessment coverage.</p></div>
      <div className="summary-grid">
        <article><strong>{dataset.summary.labels.usage_exemplars}</strong><span>Usage exemplars</span></article>
        <article><strong>{dataset.summary.labels.repository_practice_exemplars}</strong><span>Repository-practice exemplars</span></article>
        <article><strong>{dataset.summary.labels.complete_assessments}</strong><span>Complete assessments</span></article>
        <article><strong>{dataset.summary.labels.practice_exemplars}</strong><span>Practice exemplars</span></article>
      </div>
    </section>
    <LanguagePanel dataset={dataset} />
  </>
}

function LanguagePanel({ dataset }: { dataset: Dataset }) {
  const rows = Object.entries(dataset.summary.language_counts).sort((a, b) => b[1] - a[1])
  const maximum = Math.max(...rows.map(([, count]) => count), 1)
  return <section className="section-block">
    <div className="section-heading"><div><p className="eyebrow">Language inventory</p><h2>Implementation languages in the catalogue</h2></div><p>Each mixed-language project contributes to every observed production language here. Historical primary-language charts use one project, one vote.</p></div>
    <div className="language-bars">{rows.map(([language, count]) => <div key={language}><span>{language}</span><i><b style={{ width: `${count * 100 / maximum}%` }} /></i><strong>{count}</strong></div>)}</div>
  </section>
}

function Explorer({ dataset }: { dataset: Dataset }) {
  const plotFamilies = [
    ['Activity', 'Commit recency and active months'],
    ['Source structure', 'File length, function length, complexity and duplication'],
    ['Native findings', 'Rule frequencies and findings per 1,000 production lines'],
    ['Documentation', 'Language-appropriate API documentation coverage'],
    ['Robustness', 'Graceful handling by invalid-input scenario'],
    ['History', 'Comparable source-derived measurements at each 1 July snapshot'],
  ]
  return <>
    <section className="page-intro"><p className="eyebrow">Dataset explorer</p><h1>Explore compatible measurements, not synthetic grades.</h1><p>Plots retain project points and only compare analyzer-derived values within compatible language, analyzer and configuration groups.</p></section>
    <LanguagePanel dataset={dataset} />
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Plot catalogue</p><h2>Aggregate views</h2></div><p>Each plot family activates when validated observations are published for enough compatible projects.</p></div><div className="plot-grid">{plotFamilies.map(([title, detail]) => <article key={title}><div className="plot-placeholder"><i /><i /><i /><i /><i /></div><h3>{title}</h3><p>{detail}</p><span>Individual points always visible</span></article>)}</div></section>
  </>
}

function ProjectDirectory({ projects }: { projects: ProjectSummary[] }) {
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('all')
  const [category, setCategory] = useState('all')
  const languages = [...new Set(projects.flatMap((project) => project.languages))].sort()
  const categories = [...new Set(projects.map((project) => project.category).filter(Boolean) as string[])].sort()
  const visible = useMemo(
    () => filterProjects(projects, query, language, category),
    [category, language, projects, query],
  )
  return <>
    <section className="page-intro"><p className="eyebrow">Project directory</p><h1>Find a scientific software report.</h1><p>Projects are listed alphabetically. There is no score-based ordering.</p></section>
    <section className="directory">
      <div className="directory-controls"><label>Search<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Project or category" /></label><label>Language<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</select></label><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((value) => <option key={value}>{pretty(value)}</option>)}</select></label></div>
      <div className="project-list">{visible.sort((a, b) => a.name.localeCompare(b.name)).map((project) => <a href={`#/projects/${project.id}`} key={project.id}><div><strong>{project.name}</strong><p>{project.description}</p><small>{pretty(project.category)} · {project.languages.join(' + ') || 'Language not classified'}</small></div><div><span className={`assessment-state ${project.included ? '' : 'excluded'}`}>{assessmentState(project)}</span><LabelList labels={project.labels} /></div><b>→</b></a>)}</div>
      <p className="result-count">{visible.length} project{visible.length === 1 ? '' : 's'}</p>
    </section>
  </>
}

function ProjectReport({ project }: { project: ProjectSummary }) {
  const sections = [
    ['Repository health', 'Activity, releases, verification CI, recognized test patterns, documentation, licence and citation.'],
    ['Code health', 'Production-source structure, duplication, documentation coverage, and native analyzer findings.'],
    ['Usage and robustness', 'CLI conventions, a curated valid run, stream behaviour, and seven invalid-input scenarios.'],
    ['Historical trends', 'Source-derived measurements at the 1 July snapshots from 2021 through 2026.'],
  ]
  return <article className="project-report">
    <header><div><p className="eyebrow">{pretty(project.category)}</p><h1>{project.name}</h1><p>{project.description}</p><div className="tag-row">{project.languages.map((language) => <span key={language}>{language}</span>)}{project.tags.map((tag) => <span key={tag}>{pretty(tag)}</span>)}</div></div><aside><span>{assessmentState(project)}</span><LabelList labels={project.labels} /><small>Snapshot {project.snapshot_date}</small>{project.repository_url && <a href={project.repository_url}>Open GitHub repository ↗</a>}</aside></header>
    <section className="report-facts"><div><span>Primary executable</span><strong>{project.primary_executable ?? 'Not identified'}</strong></div><div><span>Valid-run definition</span><strong>{pretty(project.valid_run_status)}</strong></div><div><span>Manifest review</span><strong>{pretty(project.curation_status)}</strong></div></section>
    <div className="report-sections">{sections.map(([title, description]) => <section key={title}><div><h2>{title}</h2><p>{description}</p></div><span>Could not assess</span></section>)}</div>
  </article>
}

function Methods() {
  return <section className="methods-page"><p className="eyebrow">Scope and methods</p><h1>Every claim is tied to a command, commit, fixture, and denominator.</h1><div className="methods-grid"><article><h2>Current snapshot</h2><p>The canonical repository snapshot is the default-branch commit at or before 1 July 2026. Repository and executable observations apply only to this snapshot.</p></article><article><h2>Historical source</h2><p>Source-derived measurements use commits at or before 1 July from 2021 onward, with one frozen analyzer configuration.</p></article><article><h2>No upstream tests</h2><p>Seebot detects recognized standard test patterns and whether verification CI appears to invoke them. It never executes upstream test suites.</p></article><article><h2>Bounded behaviour</h2><p>Usage probes run in an isolated Linux x86-64 environment with fixed CPU, memory, disk, network, and timeout limits.</p></article><article><h2>Native findings</h2><p>Linter and security rules remain native to their analyzer. Different tools and languages are not merged into one finding category.</p></article><article><h2>No quality score</h2><p>Measurements remain separate. Exemplar labels depend on observable practices, graceful behaviour, and complete evidence—not arbitrary code thresholds.</p></article></div></section>
}

function About() {
  return <section className="methods-page"><p className="eyebrow">About Seebot</p><h1>A transparent observatory for scientific software engineering.</h1><div className="methods-grid"><article><h2>What it records</h2><p>Seebot publishes reproducible observations about repositories, production source, command-line interfaces, and deliberately awkward input.</p></article><article><h2>What it does not claim</h2><p>It does not judge scientific validity, rank projects, or turn unrelated engineering measurements into an overall quality score.</p></article><article><h2>Who can rerun it</h2><p>Project manifests, shared fixtures, selectors, environment limits, and evidence rules live with the code so individual projects or measurement families can be regenerated.</p></article><article><h2>Why exemplars exist</h2><p>Exemplar labels identify projects that meet every applicable observable contract in a category. They are factual labels, not prizes or grades.</p></article></div></section>
}

export default function App() {
  const location = useLocation()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { fetch(`${import.meta.env.BASE_URL}data/dataset.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Dataset returned ${response.status}`))).then(setDataset).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error')) }, [])
  const parts = location.pathname.split('/').filter(Boolean)
  const view = parts[0] || 'overview'
  const project = view === 'projects' && parts[1] ? dataset?.projects.find((item) => item.id === parts[1]) : undefined
  return <><NavBar appName="SEEBOT" appSubtitle="Scientific software observatory" version="0.2.0" githubUrl="https://github.com/happykhan/seebot" actions={<><a className="seebot-nav-link" href="#/">Overview</a><a className="seebot-nav-link" href="#/explore">Explore</a><a className="seebot-nav-link" href="#/projects">Projects</a><a className="seebot-nav-link" href="#/methods">Methods</a></>} mobileActions={<><a className="gx-nav-dropdown-link" href="#/">Overview</a><a className="gx-nav-dropdown-link" href="#/explore">Explore</a><a className="gx-nav-dropdown-link" href="#/projects">Projects</a><a className="gx-nav-dropdown-link" href="#/methods">Methods</a></>} /><main>
    {error && <p className="load-error">Could not load the published dataset: {error}</p>}
    {!error && !dataset && <p className="loading">Loading software observations…</p>}
    {dataset && view === 'overview' && <Overview dataset={dataset} />}
    {dataset && view === 'explore' && <Explorer dataset={dataset} />}
    {dataset && view === 'projects' && !parts[1] && <ProjectDirectory projects={dataset.projects} />}
    {dataset && view === 'projects' && project && <ProjectReport project={project} />}
    {dataset && view === 'projects' && parts[1] && !project && <p className="load-error">Project not found.</p>}
    {view === 'methods' && <Methods />}
    {view === 'about' && <About />}
  </main><footer className="site-footer"><span>Seebot · snapshot 1 July 2026</span><span>Observable engineering evidence, not scientific validation or a quality score.</span></footer></>
}
