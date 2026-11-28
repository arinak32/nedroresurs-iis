import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, patch, type DriverShort, type Vehicle } from '../api'
import { useAuth } from '../auth'
import { Head } from '../components/Layout'
import { dateRu, num, plural } from '../format'

const KINDS: [string, string][] = [['', 'Все'], ['dump_truck', 'Самосвалы'], ['excavator', 'Экскаваторы'], ['loader', 'Погрузчики']]
const ICON: Record<Vehicle['kind'], string> = { dump_truck: '▣', excavator: '◢', loader: '◣' }

function statusChip(v: Vehicle) {
  if (v.status === 'repair') return <span className="chip err">Ремонт</span>
  if (v.status === 'maintenance') return <span className="chip warn">На ТО</span>
  if (v.service_left < 0) return <span className="chip err">ТО просрочено</span>
  if (v.service_soon) return <span className="chip warn">Скоро ТО</span>
  return <span className="chip ok">{v.kind === 'dump_truck' ? 'На линии' : 'Работает'}</span>
}
const counter = (v: Vehicle) => v.kind === 'dump_truck' ? v.odometer_km : v.engine_hours
const serviceText = (v: Vehicle) => v.status !== 'on_line' && v.current?.planned_end ? `до ${dateRu(v.current.planned_end)}`
  : v.service_left < 0 ? `просрочено на ${num(-v.service_left)} ${v.counter_unit}` : `через ${num(v.service_left)} ${v.counter_unit}`

export default function Fleet() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const canEdit = user?.role === 'mechanic' || user?.role === 'admin'
  const [kind, setKind] = useState('')
  const [selId, setSelId] = useState<number | null>(null)
  const list = useQuery({ queryKey: ['vehicles'], queryFn: () => api.get<Vehicle[]>('/api/vehicles'), refetchInterval: 60000 })
  const all = list.data ?? []
  const shown = all.filter(v => !kind || v.kind === kind)
  const off = all.filter(v => v.status !== 'on_line').length

  return (
    <>
      <Head sub={`${plural(all.length, 'единица', 'единицы', 'единиц')} · ${off ? `${off} в ремонте или на ТО` : 'вся техника в работе'}`} title="Техника" />
      <div className="tabs">
        {KINDS.map(([k, l]) => <button key={k} className={`tab ${kind === k ? 'on' : ''}`} onClick={() => setKind(k)}>{l}<small>{k ? all.filter(v => v.kind === k).length : all.length}</small></button>)}
      </div>
      <div className="row">
        <div className="fleet grow">
          {shown.map(v => (
            <button key={v.id} className={`card vcard ${selId === v.id ? 'sel' : ''}`} onClick={() => setSelId(v.id)}>
              <div className="head">
                <div className="vico">{ICON[v.kind]}</div>
                <div className="t"><h3>{v.name}</h3><div className="muted small">{v.model} · {v.kind === 'dump_truck' ? `${num(v.capacity_m3)} м³` : `ковш ${v.capacity_m3.replace('.', ',').replace(/,?0+$/, '')} м³`}</div></div>
              </div>
              <div>{statusChip(v)}</div>
              <div className="kv"><span>{v.kind === 'dump_truck' ? 'Пробег' : 'Наработка'}</span><span>{num(counter(v))} {v.counter_unit}</span></div>
              <div className="kv"><span>{v.status === 'on_line' ? 'ТО' : 'Вернётся'}</span><span className={v.service_soon && v.status === 'on_line' ? 'warn-t' : ''}>{serviceText(v)}</span></div>
              {v.kind === 'dump_truck' && <div className="muted small">{v.driver_name ?? 'водитель не закреплён'}</div>}
            </button>
          ))}
        </div>
        {selId && <Card id={selId} canEdit={canEdit} onChange={() => qc.invalidateQueries({ queryKey: ['vehicles'] })} />}
      </div>
    </>
  )
}

function Card({ id, canEdit, onChange }: { id: number; canEdit: boolean; onChange: () => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['vehicle', id], queryFn: () => api.get<Vehicle>(`/api/vehicles/${id}`) })
  const drivers = useQuery({ queryKey: ['drivers'], queryFn: () => api.get<DriverShort[]>('/api/drivers'), enabled: canEdit })
  const [form, setForm] = useState<null | 'start' | 'finish' | 'edit'>(null)
  const [f, setF] = useState({ kind: 'ремонт', description: '', planned_end: '', counter: '', interval: '' })
  const [err, setErr] = useState('')
  useEffect(() => { setForm(null); setErr('') }, [id])
  const v = q.data
  if (!v) return <div className="card side-card">Загрузка…</div>

  const save = async (fn: () => Promise<Vehicle>) => {
    setErr('')
    try { const r = await fn(); qc.setQueryData(['vehicle', id], r); qc.invalidateQueries({ queryKey: ['drivers'] }); onChange(); setForm(null) }
    catch (e) { setErr((e as Error).message) }
  }
  const unit = v.counter_unit

  return (
    <div className="card side-card">
      <div className="head"><h2 className="t">{v.name}</h2>{statusChip(v)}</div>
      <div className="muted small">{v.model}{v.reg_number ? ` · ${v.reg_number}` : ''}{v.driver_name ? ` · водитель ${v.driver_name}` : ''}</div>
      {v.current && (
        <div className={`alert ${v.status === 'repair' ? 'err' : 'warn'}`}>
          <div>{v.current.kind === 'ТО' ? 'Техническое обслуживание' : 'Текущий ремонт'}</div>
          <div style={{ fontWeight: 500, marginTop: 4 }}>{v.current.description || 'без описания'}. Начат {dateRu(v.current.started_at)}{v.current.planned_end ? `, плановое окончание ${dateRu(v.current.planned_end)}` : ''}</div>
        </div>
      )}
      {v.current && v.kind === 'dump_truck' && <div className="muted small">Исключён из планирования рейсов до окончания работ</div>}
      <div className="kv"><span>{v.kind === 'dump_truck' ? 'Пробег' : 'Наработка'}</span><span>{num(counter(v))} {unit}</span></div>
      <div className="kv"><span>Интервал ТО</span><span>{num(v.service_interval)} {unit}</span></div>
      <div className="kv"><span>До следующего ТО</span><span>{serviceText(v)}</span></div>

      {canEdit && !form && (
        <div className="grid2" style={{ marginTop: 6 }}>
          {v.status === 'on_line'
            ? <><button className="btn btn-light" onClick={() => { setF({ ...f, kind: 'ТО' }); setForm('start') }}>Начать ТО</button>
              <button className="btn btn-main" onClick={() => { setF({ ...f, kind: 'ремонт' }); setForm('start') }}>В ремонт</button></>
            : <><button className="btn btn-light" onClick={() => { setF({ ...f, counter: String(counter(v)), interval: String(v.service_interval) }); setForm('edit') }}>Изменить</button>
              <button className="btn btn-main" onClick={() => { setF({ ...f, counter: String(counter(v)) }); setForm('finish') }}>Завершить {v.current?.kind === 'ТО' ? 'ТО' : 'ремонт'}</button></>}
          {v.status === 'on_line' && <button className="btn btn-text" style={{ gridColumn: 'span 2' }} onClick={() => { setF({ ...f, counter: String(counter(v)), interval: String(v.service_interval) }); setForm('edit') }}>Изменить пробег, интервал ТО или водителя</button>}
        </div>
      )}

      {form === 'start' && (
        <div className="subform">
          <h3>{f.kind === 'ТО' ? 'Техническое обслуживание' : 'Ремонт'}</h3>
          <div className="field"><label>Что делаем</label><textarea className="input" rows={2} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
          <div className="field"><label>Плановое окончание</label><input className="input" type="date" value={f.planned_end} onChange={e => setF({ ...f, planned_end: e.target.value })} /></div>
          <div className="grid2"><button className="btn btn-light" onClick={() => setForm(null)}>Отмена</button>
            <button className="btn btn-main" onClick={() => save(() => api.post(`/api/vehicles/${id}/maintenance`, { kind: f.kind, description: f.description || null, planned_end: f.planned_end || null }))}>Сохранить</button></div>
        </div>
      )}
      {form === 'finish' && (
        <div className="subform">
          <h3>Завершить {v.current?.kind === 'ТО' ? 'ТО' : 'ремонт'}</h3>
          <div className="field"><label>{v.kind === 'dump_truck' ? 'Пробег по одометру, км' : 'Моточасы'}</label><input className="input" type="number" value={f.counter} onChange={e => setF({ ...f, counter: e.target.value })} /></div>
          {v.current?.kind === 'ТО' && <div className="muted small">Отсчёт до следующего ТО начнётся с этого значения</div>}
          <div className="grid2"><button className="btn btn-light" onClick={() => setForm(null)}>Отмена</button>
            <button className="btn btn-main" onClick={() => save(() => api.post(`/api/vehicles/${id}/maintenance/finish`, { counter: Number(f.counter) || null }))}>Машина в строю</button></div>
        </div>
      )}
      {form === 'edit' && (
        <div className="subform">
          <div className="grid2">
            <div className="field"><label>{v.kind === 'dump_truck' ? 'Пробег, км' : 'Моточасы'}</label><input className="input" type="number" value={f.counter} onChange={e => setF({ ...f, counter: e.target.value })} /></div>
            <div className="field"><label>Интервал ТО, {unit}</label><input className="input" type="number" value={f.interval} onChange={e => setF({ ...f, interval: e.target.value })} /></div>
          </div>
          {v.kind === 'dump_truck' && (
            <div className="field"><label>Закреплённый водитель</label>
              <select className="input" value={v.driver_id ?? 0} onChange={e => save(() => patch(`/api/vehicles/${id}`, { driver_id: Number(e.target.value) || null }))}>
                <option value={0}>не закреплён</option>
                {drivers.data?.map(d => <option key={d.id} value={d.id}>{d.full_name}{d.vehicle_name && d.id !== v.driver_id ? ` (сейчас ${d.vehicle_name})` : ''}</option>)}
              </select></div>
          )}
          <div className="grid2"><button className="btn btn-light" onClick={() => setForm(null)}>Закрыть</button>
            <button className="btn btn-main" onClick={() => save(() => patch(`/api/vehicles/${id}`, { counter: Number(f.counter), service_interval: Number(f.interval) }))}>Сохранить</button></div>
        </div>
      )}
      {err && <div className="alert err">{err}</div>}

      <h3 style={{ marginTop: 10 }}>История обслуживания</h3>
      {v.history.length ? v.history.map(h => (
        <div key={h.id} className="hist">
          <span className={`dot ${h.finished_at ? (h.kind === 'ТО' ? 'ok' : 'err') : 'warn'}`} />
          <div><b>{h.kind === 'ТО' ? 'ТО' : 'Ремонт'}{h.description ? `: ${h.description}` : ''}</b>
            <div className="muted small">{dateRu(h.started_at)}{h.finished_at ? ` — ${dateRu(h.finished_at)}` : ' — идёт сейчас'}{h.mechanic ? ` · ${h.mechanic}` : ''}</div></div>
        </div>
      )) : <div className="muted small">Записей пока нет</div>}
    </div>
  )
}
