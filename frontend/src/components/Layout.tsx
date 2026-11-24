import { NavLink, Outlet } from 'react-router-dom'
import type { Role } from '../api'
import { useAuth } from '../auth'
import { initials, ROLE_RU } from '../format'

// пункты меню и роли, которым они доступны (таблица 2.1)
export const MENU: { to: string; label: string; ico: string; roles: Role[] }[] = [
  { to: '/', label: 'Обзор', ico: '⌂', roles: ['director', 'manager', 'accountant', 'admin'] },
  { to: '/orders', label: 'Заказы', ico: '≡', roles: ['director', 'manager', 'accountant', 'lawyer', 'admin'] },
  { to: '/clients', label: 'Клиенты', ico: '◎', roles: ['director', 'manager', 'accountant', 'lawyer', 'admin'] },
  { to: '/stock', label: 'Добыча и остатки', ico: '▲', roles: ['director', 'manager', 'accountant', 'admin'] },
  { to: '/trips', label: 'Рейсы', ico: '➜', roles: ['director', 'manager', 'mechanic', 'admin'] },
  { to: '/fleet', label: 'Техника', ico: '▣', roles: ['director', 'manager', 'mechanic', 'admin'] },
  { to: '/contracts', label: 'Договоры', ico: '§', roles: ['director', 'manager', 'accountant', 'lawyer', 'admin'] },
  { to: '/documents', label: 'Документы', ico: '▤', roles: ['director', 'manager', 'accountant', 'lawyer', 'admin'] },
  { to: '/forecast', label: 'Прогноз', ico: '∿', roles: ['director', 'manager', 'admin'] },
  { to: '/settings', label: 'Настройки', ico: '⚑', roles: ['admin'] },
]

export function Logo() {
  return (
    <div className="logo">
      <img src="/logo.svg" width={40} height={40} alt="" />
      <div><b>Недроресурс</b><span>ПЕСОК · КАРЬЕРЫ · ДОСТАВКА</span></div>
    </div>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <div className="shell">
      <aside className="side">
        <Logo />
        <div className="me">
          <div className="avatar">{initials(user.full_name)}</div>
          <div className="role">{ROLE_RU[user.role]}</div>
          <div className="name">{user.full_name}</div>
        </div>
        <nav className="menu">
          {MENU.filter(m => m.roles.includes(user.role)).map(m => (
            <NavLink key={m.to} to={m.to} end={m.to === '/'}><span className="ico">{m.ico}</span>{m.label}</NavLink>
          ))}
        </nav>
        <button className="logout" onClick={logout}>Выйти</button>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  )
}

export function Head({ sub, title, children }: { sub?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="head">
      <div className="t">{sub && <div className="sub">{sub}</div>}<h1>{title}</h1></div>
      {children}
    </div>
  )
}
