import { ROUTE_COLOURS } from '../data.js'

export default function RouteBadge({ route }) {
  const key = (route || '').split(' ')[0]
  const colour = route?.includes('fallback') ? 'var(--fallback)' : ROUTE_COLOURS[key] ?? 'var(--accent)'
  return <span className="badge" style={{ background: colour }}>route: {route || '?'}</span>
}
