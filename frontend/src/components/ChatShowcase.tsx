import { useEffect, useRef, useState } from 'react'
import { useMatch } from 'react-router-dom'
import { formatPrice } from '../api'
import { useShowcase } from '../showcase'
import type { SearchFilters } from '../types'
import ProductCard from './ProductCard'

const INITIAL_VISIBLE = 8

function filterChips(f: SearchFilters): string[] {
  return [
    f.category,
    f.query && `“${f.query}”`,
    f.color && `Color: ${f.color}`,
    f.max_price != null && `Under ${formatPrice(f.max_price)}`,
    f.size && `Size ${f.size} in stock`,
  ].filter((c): c is string => Boolean(c))
}

/** The panel where the chat assistant's search results land on the page. */
export default function ChatShowcase() {
  const { showcase, clear } = useShowcase()
  const onDetailPage = useMatch('/products/:productId')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const ref = useRef<HTMLElement>(null)

  // Bring fresh results into view as soon as the chat delivers them.
  useEffect(() => {
    if (showcase && !onDetailPage) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showcase?.id])

  // Hidden on the detail page so the large image is front and center; it's back when you return.
  if (!showcase || onDetailPage) return null

  const expanded = expandedId === showcase.id
  const visible = expanded ? showcase.products : showcase.products.slice(0, INITIAL_VISIBLE)
  const hidden = showcase.products.length - visible.length

  return (
    <section ref={ref} className="showcase" aria-label="Results from the shopping assistant" key={showcase.id}>
      <div className="showcase-glow" aria-hidden />
      <header className="showcase-head">
        <div>
          <p className="showcase-eyebrow">
            <span className="spark">✦</span> Picked by your Campus Customs assistant
          </p>
          <h2>{showcase.title}</h2>
          <div className="showcase-meta">
            <span className="count-pill">
              {showcase.total_matches} {showcase.total_matches === 1 ? 'match' : 'matches'}
            </span>
            {filterChips(showcase.filters).map((c) => (
              <span key={c} className="filter-chip">{c}</span>
            ))}
          </div>
        </div>
        <button className="showcase-close" onClick={clear} aria-label="Clear assistant results">
          ×
        </button>
      </header>

      <div className="grid showcase-grid">
        {visible.map((p, i) => (
          <ProductCard key={p.product_id} product={p} index={i} />
        ))}
      </div>

      {hidden > 0 && (
        <div className="showcase-more">
          <button className="btn light" onClick={() => setExpandedId(showcase.id)}>
            Show all {showcase.products.length}
          </button>
        </div>
      )}
    </section>
  )
}
