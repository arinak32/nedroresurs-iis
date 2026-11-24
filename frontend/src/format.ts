import type { OrderStatus, Role } from './api'

const nf = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const nf2 = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })

export const num = (v: string | number | null | undefined) => v === null || v === undefined ? '—' : nf.format(Number(v))
export const m3 = (v: string | number | null | undefined) => `${num(v)} м³`
export const rub = (v: string | number | null | undefined) => v === null || v === undefined ? '—' : `${nf2.format(Number(v))} ₽`
export const dateRu = (s: string | null) => s ? new Date(s).toLocaleDateString('ru-RU') : '—'

export const ROLE_RU: Record<Role, string> = {
  director: 'Директор', manager: 'Менеджер', accountant: 'Бухгалтер', lawyer: 'Юрист',
  mechanic: 'Механик', driver: 'Водитель', admin: 'Администратор',
}

// статус → подпись и цвет метки (дизайн-система, компонент «Статус»)
export const STATUS: Record<OrderStatus, [string, string]> = {
  new: ['Новый', 'info'], awaiting_payment: ['Ждёт оплаты', 'warn'], planning: ['Планирование', 'sand'],
  in_delivery: ['В доставке', 'sand'], shipped: ['Отгружен', 'ok'], done: ['Выполнен', 'ok'], cancelled: ['Отменён', 'err'],
}

export const initials = (name: string) => name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()

export function plural(n: number, one: string, few: string, many: string) {
  const a = n % 10, b = n % 100
  const w = a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many
  return `${n} ${w}`
}
