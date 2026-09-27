import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { formatPrice, getProducts } from '../api'
import ProductCard from '../components/ProductCard'
import type { Product } from '../types'

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
const SORTS = {
  featured: 'Featured',
  'price-asc': 'Price: low to high',
  'price-desc': 'Price: high to low',
  name: 'Name: A–Z',
  stock: 'Most in stock',
} as const
type SortKey = keyof typeof SORTS

// Every filter lives in the URL (?cat=Hoodies&size=M&max=70&sort=price-asc), so
// results survive Back from a product page and can be shared as a link.
export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [params, setParams] = useSearchParams()

  const category = params.get('cat') ?? 'All'
  const query = params.get('q') ?? ''
  const size = params.get('size')
  const sort = (params.get('sort') as SortKey) in SORTS ? (params.get('sort') as SortKey) : 'featured'
  const maxParam = params.get('max')

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const priceCeiling = useMemo(() => Math.ceil(Math.max(0, ...products.map((p) => p.price))), [products])
  const maxPrice = maxParam ? Number(maxParam) : priceCeiling

  function update(key: string, value: string | null) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value === null || value === '') next.delete(key)
        else next.set(key, value)
        return next
      },
      { replace: true },
    )
  }

  const categories = useMemo(
    () => ['All', ...Array.from(new Set(products.map((p) => p.category))).sort()],
    [products],
  )

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = products.filter(
      (p) =>
        (category === 'All' || p.category === category) &&
        (!size || p.inventory.some((s) => s.size === size && s.quantity > 0)) &&
        p.price <= maxPrice &&
        (!q || p.name.toLowerCase().includes(q) || p.search_tags.some((t) => t.toLowerCase().includes(q))),
    )
    const sorted = [...list]
    if (sort === 'price-asc') sorted.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    if (sort === 'price-desc') sorted.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    if (sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name))
    if (sort === 'stock') sorted.sort((a, b) => b.total_stock - a.total_stock)
    return sorted
  }, [products, category, query, size, maxPrice, sort])

  const activeCount = [category !== 'All', !!query, !!size, !!maxParam].filter(Boolean).length

  function askAssistant() {
    window.dispatchEvent(
      new CustomEvent('cc:open-chat', {
        detail: `I'm looking for ${[size && `size ${size}`, category !== 'All' && category.toLowerCase(), query && `"${query}"`, maxParam && `under ${formatPrice(maxPrice)}`].filter(Boolean).join(', ') || 'something'} — what do you recommend?`,
      }),
    )
  }

  if (loading) return <p className="status">Loading products…</p>
  if (error) return <p className="status error">Couldn't load products ({error}). Is the backend running?</p>

  return (
    <>
      <div className="products-head">
        <h1>Shop Campus Customs</h1>
        <p className="muted">{products.length} styles · hoodies, crewnecks, quarter-zips, fleece and tees</p>
      </div>

      <div className="toolbar">
        <div className="toolbar-row">
          <input
            type="search"
            className="search"
            placeholder="Search hoodies, colleges, sports…"
            value={query}
            onChange={(e) => update('q', e.target.value)}
          />
          <label className="sort">
            Sort
            <select value={sort} onChange={(e) => update('sort', e.target.value === 'featured' ? null : e.target.value)}>
              {Object.entries(SORTS).map(([k, label]) => (
                <option key={k} value={k}>{label}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="chips">
          {categories.map((c) => (
            <button
              key={c}
              className={`chip${c === category ? ' active' : ''}`}
              onClick={() => update('cat', c === 'All' ? null : c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="toolbar-row">
          <div className="size-filter" role="group" aria-label="In stock in size">
            <span className="toolbar-label">In stock in</span>
            {SIZES.map((s) => (
              <button
                key={s}
                className={`size-chip${size === s ? ' active' : ''}`}
                onClick={() => update('size', size === s ? null : s)}
                aria-pressed={size === s}
              >
                {s}
              </button>
            ))}
          </div>
          <label className="price-filter">
            <span className="toolbar-label">Up to <strong>{formatPrice(maxPrice)}</strong></span>
            <input
              type="range"
              min={30}
              max={priceCeiling}
              step={1}
              value={maxPrice}
              onChange={(e) => update('max', Number(e.target.value) >= priceCeiling ? null : e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="results-bar">
        <p className="count">
          <strong>{visible.length}</strong> of {products.length} items
          {sort !== 'featured' && <> · sorted by {SORTS[sort].toLowerCase()}</>}
        </p>
        {activeCount > 0 && (
          <button className="link-btn" onClick={() => setParams({}, { replace: true })}>
            Clear {activeCount} filter{activeCount > 1 ? 's' : ''}
          </button>
        )}
      </div>

      {visible.length === 0 ? (
        <div className="empty-results">
          <p><strong>No matches.</strong> Try a different size or a higher price, or let the assistant help.</p>
          <div className="empty-actions">
            <button className="btn" onClick={() => setParams({}, { replace: true })}>Clear filters</button>
            <button className="btn ghost-dark" onClick={askAssistant}>💬 Ask the assistant</button>
          </div>
        </div>
      ) : (
        <div className="grid">
          {visible.map((p) => (
            <ProductCard key={p.product_id} product={p} />
          ))}
        </div>
      )}
    </>
  )
}
