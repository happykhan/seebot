import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import './styles.css'

const savedTheme = localStorage.getItem('gx-theme')
document.documentElement.setAttribute('data-theme', savedTheme === 'dark' ? 'dark' : 'light')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
)
