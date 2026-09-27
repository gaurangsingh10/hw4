import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, getProducts } from '../api'
import ProductCard from '../components/ProductCard'
import type { Product } from '../types'

const FEATURED_IDS = [
  '2025-yale-vs-harvard-t-shirt',
  'basic-hoodie-big-yale',
  'champion-reverse-weave-crewneck',
  'brooks-brothers-bomber-jacket-yale',
]

export default function Home() {
  const [featured, setFeatured] = useState<Product[]>([])

  useEffect(() => {
    getProducts()
      .then((all) => setFeatured(all.filter((p) => FEATURED_IDS.includes(p.product_id))))
      .catch(() => setFeatured([]))
  }, [])

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Stardate 2026 · Tailgate season</p>
        <h1>
          Bulldog tradition, <em>tailored for tomorrow.</em>
        </h1>
        <p>
          Campus Customs is where I'd send any friend looking for Yale gear that's comfortable enough
          for a 9 a.m. lecture and loud enough for The Game. Hoodies, crewnecks, tees, and
          residential college favorites, all in one place.
        </p>
        <div className="hero-actions">
          <Link to="/products" className="btn">Shop the collection</Link>
          <Link to="/about" className="btn ghost">Our story</Link>
        </div>
      </section>

      <section className="strip">
        <div>
          <h3>Back in Bulldog Blue 💙</h3>
          <p>Classic navy pieces you'll reach for every week.</p>
        </div>
        <div>
          <h3>Rep your college</h3>
          <p>From Branford to Saybrook, find your residential college crest.</p>
        </div>
        <div>
          <h3>Game-day ready</h3>
          <p>Harvard-Yale tees and team gear for every sport on campus.</p>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="leaderboard" aria-label="Leaderboard">
          <header className="leaderboard-head">
            <h2>The Leaderboard</h2>
            <span>Fan favorites · live stock</span>
          </header>
          <ol>
            {featured.map((p, i) => (
              <li key={p.product_id}>
                <Link to={`/products/${p.product_id}`}>
                  <span className="lb-rank">{i + 1}</span>
                  <img className="lb-img" src={p.image_url} alt="" />
                  <span className="lb-name">{p.name}</span>
                  <span className="lb-stock">{p.total_stock} in stock</span>
                  <span className="lb-price">{formatPrice(p.price)}</span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}

      {featured.length > 0 && (
        <section>
          <div className="section-head">
            <h2>Fan favorites</h2>
            <Link to="/products">See all →</Link>
          </div>
          <div className="grid">
            {featured.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
