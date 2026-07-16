import type { ReactNode, SelectHTMLAttributes } from 'react'

export function SeebotIcon() {
  return <svg viewBox="0 0 32 32" role="img" aria-label="Seebot">
    <rect x="2" y="2" width="28" height="28" rx="8" fill="var(--gx-accent)" />
    <path d="M8 11.5 5.5 16 8 20.5M24 11.5l2.5 4.5-2.5 4.5" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="12" cy="15" r="3.25" fill="white" />
    <circle cx="20" cy="15" r="3.25" fill="white" />
    <circle cx="12" cy="15" r="1.25" fill="#143c34" />
    <circle cx="20" cy="15" r="1.25" fill="#143c34" />
    <path d="M12 23h8" stroke="white" strokeWidth="2" strokeLinecap="round" />
  </svg>
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  children: ReactNode
}

export function SelectField({ label, children, className = '', ...props }: SelectFieldProps) {
  return <label className={`select-field ${className}`}>
    <span>{label}</span>
    <span className="select-control">
      <select {...props}>{children}</select>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </span>
  </label>
}

export function InfoTip({ children }: { children: ReactNode }) {
  return <span className="info-tip" tabIndex={0} aria-label={`Information: ${String(children)}`}>
    <span aria-hidden="true">i</span>
    <span className="info-tip-content" role="tooltip">{children}</span>
  </span>
}
