import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type ProductionRow, type Quarry, type Site } from '../api'
import { useAuth } from '../auth'
import { Head } from '../components/Layout'
import { dateRu, m3, num } from '../format'

export function SiteCards() {
  const sites = useQuery({ queryKey: ['stock'], queryFn: () => api.get<Site[]>('/api/stock') })
  return (
    <div className="row">
      {sites.data?.map(s => (
        <div key={s.id} className="card grow" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="muted">Остаток «{s.product_name}»</div>
          <div className="num-l">{m3(s.volume_m3)}</div>
          <div className="bar"><div style={{ width: `${Math.min(100, s.fill_pct)}%`, background: s.fill_pct > 85 ? 'var(--err)' : undefined }} /></div>
          <div className="muted small">{num(s.fill_pct)} % площадки · вместимость {m3(s.capacity_m3)}</div>
        </div>
      ))}
    </div>
  )
}

export default function Stock() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const quarries = useQuery({ queryKey: ['quarries'], queryFn: () => api.get<Quarry[]>('/api/quarries') })
  const journal = useQuery({ queryKey: ['production'], queryFn: () => api.get<ProductionRow[]>('/api/production') })
  const today = new Date().toISOString().slice(0, 10)
  const [f, setF] = useState({ quarry_id: 0, shift_date: today, volume_m3: '' })
  const [msg, setMsg] = useState<[string, string] | null>(null)
  const canEdit = user?.role === 'manager'

  const save = async () => {
    setMsg(null)
    try {
      await api.post('/api/production', { ...f, quarry_id: f.quarry_id || quarries.data?.[0].id, volume_m3: Number(f.volume_m3) })
      setMsg(['ok', 'Добыча сохранена, остаток обновлён']); setF({ ...f, volume_m3: '' })
      qc.invalidateQueries({ queryKey: ['production'] }); qc.invalidateQueries({ queryKey: ['stock'] })
    } catch (e) { setMsg(['err', (e as Error).message]) }
  }

  return (
    <>
      <Head sub="4 карьера · 2 площадки хранения" title="Добыча и остатки" />
      <SiteCards />
      <div className="row">
        <div className="card grow" style={{ padding: '18px 12px' }}>
          <h2 style={{ padding: '0 12px 8px' }}>Журнал добычи</h2>
          {journal.data?.length ? (
            <table className="t">
              <thead><tr><th>Дата смены</th><th>Карьер</th><th>Вид песка</th><th>Объём</th><th>Внёс</th></tr></thead>
              <tbody>{journal.data.map(r => (
                <tr key={r.id}><td>{dateRu(r.shift_date)}</td><td>{r.quarry_name}</td><td>{r.product_name}</td><td>{m3(r.volume_m3)}</td><td>{r.author ?? '—'}</td></tr>
              ))}</tbody>
            </table>
          ) : <div className="spinner">Записей о добыче пока нет</div>}
        </div>
        {canEdit && (
          <div className="card" style={{ width: 340, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <h2>Внести добычу за смену</h2>
            <div className="field"><label>Карьер</label>
              <select className="input" value={f.quarry_id} onChange={e => setF({ ...f, quarry_id: Number(e.target.value) })}>
                {quarries.data?.map(q => <option key={q.id} value={q.id}>{q.name}</option>)}
              </select></div>
            <div className="field"><label>Дата смены</label><input className="input" type="date" value={f.shift_date} onChange={e => setF({ ...f, shift_date: e.target.value })} /></div>
            <div className="field"><label>Объём, м³</label><input className="input" type="number" value={f.volume_m3} onChange={e => setF({ ...f, volume_m3: e.target.value })} /></div>
            {msg && <div className={`alert ${msg[0]}`}>{msg[1]}</div>}
            <button className="btn btn-main" disabled={!f.volume_m3} onClick={save}>Сохранить</button>
          </div>
        )}
      </div>
    </>
  )
}
