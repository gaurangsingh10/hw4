import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './theme.css'
import App from './App.tsx'
import { AuthProvider } from './auth.tsx'
import { ShowcaseProvider } from './showcase.tsx'
import { CartProvider } from './cart.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ShowcaseProvider>
          <CartProvider>
            <App />
          </CartProvider>
        </ShowcaseProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
