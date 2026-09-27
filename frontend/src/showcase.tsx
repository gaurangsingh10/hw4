import { createContext, useContext, useState, type ReactNode } from 'react'
import type { ShowcaseResult } from './types'

// The latest chat search results shown on the page. Kept in sessionStorage so the
// panel survives opening a product and coming back (or a page refresh).
const STORAGE_KEY = 'cc_showcase'

interface Showcase extends ShowcaseResult {
  id: number // changes on every new result so the cards re-animate
}

interface ShowcaseState {
  showcase: Showcase | null
  show: (result: ShowcaseResult) => void
  clear: () => void
}

const ShowcaseContext = createContext<ShowcaseState | null>(null)

function load(): Showcase | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Showcase) : null
  } catch {
    return null
  }
}

export function ShowcaseProvider({ children }: { children: ReactNode }) {
  const [showcase, setShowcase] = useState<Showcase | null>(load)

  const value: ShowcaseState = {
    showcase,
    show: (result) => {
      const next = { ...result, id: Date.now() }
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      setShowcase(next)
    },
    clear: () => {
      sessionStorage.removeItem(STORAGE_KEY)
      setShowcase(null)
    },
  }

  return <ShowcaseContext.Provider value={value}>{children}</ShowcaseContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useShowcase() {
  const ctx = useContext(ShowcaseContext)
  if (!ctx) throw new Error('useShowcase must be used inside <ShowcaseProvider>')
  return ctx
}
