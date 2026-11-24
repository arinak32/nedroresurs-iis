import '@fontsource/manrope/400.css'
import '@fontsource/manrope/500.css'
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import '@fontsource/manrope/800.css'
import './styles.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Layout, { Head, MENU } from './components/Layout'
import Login from './pages/Login'
import Orders from './pages/Orders'
import Stock, { SiteCards } from './pages/Stock'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function Guard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="spinner">Загрузка…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

// разделы, которые будут сделаны на следующих этапах
function Soon() {
  const { pathname } = useLocation()
  const item = MENU.find(m => m.to === pathname)
  return <><Head title={item?.label ?? 'Раздел'} /><div className="card">Раздел в разработке — появится на следующих этапах.</div></>
}

function Overview() {
  const { user } = useAuth()
  return <><Head sub="Панель управления" title="Обзор предприятия" /><div className="muted">Здравствуйте, {user?.full_name}. Полная панель показателей появится после модулей рейсов и прогноза.</div><SiteCards /></>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Guard><Layout /></Guard>}>
              <Route index element={<Overview />} />
              <Route path="orders" element={<Orders />} />
              <Route path="stock" element={<Stock />} />
              <Route path="*" element={<Soon />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
