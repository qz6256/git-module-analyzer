export function formatTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(value?: string | null): string {
  if (!value) return '—'
  return value.length > 10 ? value.slice(0, 10) : value
}

export function shortSha(sha?: string): string {
  if (!sha) return '—'
  return sha.length > 8 ? sha.slice(0, 8) : sha
}

export function riskTone(risk?: string): 'danger' | 'warning' | 'info' {
  if (risk === '高') return 'danger'
  if (risk === '中') return 'warning'
  return 'info'
}
