import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, patch, type Plan, type Trip } from '../api'
import { useAuth } from '../auth'
import { Head } from '../components/Layout'
import { m3, num, plural } from '../format'

const TRIP_STATUS: Record<string, [string, string]> = {
  planned: ['Запланирован', 'info'], en_route: ['В пути', 'sand'], delivered: ['Доставлен', 'ok'], cancelled: ['Отменён', 'err'],
}
const SHIFT_H = 12, SPEED = 45, LOAD_H = 0.5
const hours = (t: Trip) => Number(t.distance_km ?? 0) / SPEED + LOAD_H   // distance_km — пробег туда и обратно

function tomorrow() { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10) }

export default function Trips() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [day, setDay] = useState(tomorrow())
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [unplanned, setUnplanned] = useState<Plan['unplanned']>([])
  const canEdit = user?.role === 'manager'
  const plan = useQuery({ queryKey: ['plan', day], queryFn: () => api.get<Plan | null>('/api/route-plans', { plan_date: day }) })
  const p = plan.data

  const run = async (fn: () => Promise<Plan>) => {
    setErr(''); setBusy(true)
    try { const r = await fn(); qc.setQueryData(['plan', day], r); return r } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const calc = async () => { const r = await run(() => api.post<Plan>('/api/route-plans', { plan_date: day })); setUnplanned(r?.unplanned ?? []) }
  const approve = () => run(() => api.post<Plan>(`/api/route-plans/${p!.id}/approve`))
  const move = (t: Trip, vehicle_id: number) => run(() => patch<Plan>(`/api/route-plans/${p!.id}/trips/${t.id}`, { vehicle_id }))

  const draft = p?.status === 'draft'
  const delivered = p?.trips.filter(t => t.status === 'delivered').length ?? 0

  return (
    <>
      <Head sub={`План на ${new Date(day).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}`} title="Рейсы">
        <input className="input" type="date" style={{ width: 170 }} value={day} onChange={e => { setDay(e.target.value); setUnplanned([]) }} />
        {canEdit && (!p || draft) && <button className="btn btn-main" disabled={busy} onClick={calc}>{busy ? 'Считаем…' : p ? 'Пересчитать план' : 'Рассчитать план →'}</button>}
      </Head>
      {err && <div className="alert err">{err}</div>}

      {p ? <>
        <div className="banner">
          <div className="grow">
            <h2 style={{ color: '#fff' }}>{draft ? 'Черновик плана' : 'План утверждён'}</h2>
            <div style={{ color: 'var(--text-dark)', marginTop: 6 }}>
              {plural(p.orders_count, 'заказ', 'заказа', 'заказов')} · {plural(new Set(p.trips.map(t => t.vehicle_id)).size, 'самосвал', 'самосвала', 'самосвалов')} · {plural(p.trips.length, 'рейс', 'рейса', 'рейсов')}
            </div>
          </div>
          <div><div className="lbl">Пробег по плану</div><div className="big">{num(p.total_km)} км</div><div className="lbl">туда и обратно</div></div>
          <div><div className="lbl">Вывезет</div><div className="big">{num(p.trips.reduce((a, t) => a + Number(t.planned_m3), 0))} м³</div><div className="lbl">&nbsp;</div></div>
          {!draft && <div><div className="lbl">Выполнено</div><div className="big">{delivered} / {p.trips.length}</div><div className="lbl">рейсов доставлено</div></div>}
          {canEdit && draft && <button className="btn btn-main" disabled={busy || !p.trips.length} onClick={approve}>Утвердить план</button>}
        </div>
        {unplanned.length > 0 && (
          <div className="alert warn">
            Не поместилось в смену — перейдёт в план следующего дня:
            {unplanned.map(u => <div key={u.order_id} style={{ fontWeight: 500, marginTop: 4 }}>
              {u.order_number} · {u.client_name} — {m3(u.volume_m3)}, {plural(u.trips, 'рейс', 'рейса', 'рейсов')}</div>)}
          </div>
        )}
        <div className="trucks">
          {p.trucks.map(truck => {
            const list = p.trips.filter(t => t.vehicle_id === truck.id)
            const h = list.reduce((a, t) => a + hours(t), 0)
            const off = truck.status !== 'on_line'
            return (
              <div key={truck.id} className={`card truck ${off ? 'off' : ''}`}>
                <div className="head">
                  <div className="t"><h3>{truck.name}</h3><div className="muted small">{truck.driver_name ?? 'водитель не закреплён'}</div></div>
                  {off ? <span className="chip warn">{truck.status === 'repair' ? 'Ремонт' : 'ТО'}</span>
                    : <span className="muted small">{list.length} рейс. · {num(list.reduce((a, t) => a + Number(t.distance_km ?? 0), 0))} км</span>}
                </div>
                {!off && <div className="bar" title={`${h.toFixed(1)} ч из ${SHIFT_H}`}><div style={{ width: `${Math.min(100, h / SHIFT_H * 100)}%` }} /></div>}
                {list.map(t => (
                  <div key={t.id} className="trip">
                    <div className="n">{t.seq}</div>
                    <div className="grow">
                      <b>{t.client_name}</b> <span className="muted small">{t.order_number}</span>
                      <div className="muted small">{t.quarry_name} → {t.address} · {num(t.distance_km)} км · {m3(t.planned_m3)}{t.heavy_restricted ? ' · ограничение массы' : ''}</div>
                    </div>
                    {draft && canEdit ? (
                      <select className="input mini" value={truck.id} onChange={e => move(t, Number(e.target.value))}>
                        {p.trucks.filter(x => x.status === 'on_line').map(x => <option key={x.id} value={x.id}>{x.name.replace('Самосвал ', '')}</option>)}
                      </select>
                    ) : <span className={`chip ${TRIP_STATUS[t.status][1]}`}>{TRIP_STATUS[t.status][0]}</span>}
                  </div>
                ))}
                {!off && !list.length && <div className="muted small">Рейсов нет</div>}
              </div>
            )
          })}
        </div>
      </> : (
        <div className="card">
          {plan.isLoading ? 'Загрузка…' : <>Плана на эту дату ещё нет.{canEdit && ' Нажмите «Рассчитать план»: система возьмёт подтверждённые заказы с доставкой и разложит их на рейсы по 30 м³ между самосвалами на линии.'}</>}
        </div>
      )}
    </>
  )
}
