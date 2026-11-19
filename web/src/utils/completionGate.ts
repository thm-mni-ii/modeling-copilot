import type { EvaluationFeedback } from '@/services/api/types/evaluation'
import type { CompletionGate } from '@/services/learningPaths'
import { adaptRecognition, analysisCategories, categoryLabels, type RecognitionCount } from '@/utils/analysisFeedback'

export interface GateRow { key: string; label: string; percent: number; required: number | null; met: boolean }
/** `gated` is false without a minimum score; then `passed` carries no meaning and rows have no thresholds. */
export interface GateResult { gated: boolean; passed: boolean; overall: GateRow; categories: GateRow[] }

const share = (row: RecognitionCount) => (row.expected ? (100 * (row.recognized ?? 0)) / row.expected : 0)

/** Display copy of meets_completion_gate (api/src/modeling_api/services/learning_paths.py); the API decides. */
export function completionGate(gate: CompletionGate | null, feedback: EvaluationFeedback): GateResult | null {
  const minimum = gate?.minimumScorePercent ?? null
  const each = gate?.scoreScope === 'eachCategory'
  const named = new Map((minimum == null ? [] : gate?.categoryMinimums ?? []).map((row) => [row.label, row.minimumPercent]))
  const results = feedback.recognitions.map(({ recognition }) => {
    const report = adaptRecognition(recognition)
    const overallPercent = share(report.overall)
    const overallRequired = minimum == null || each ? null : minimum
    const overall: GateRow = { key: 'overall', label: 'Gesamt', percent: overallPercent, required: overallRequired, met: Boolean(report.overall.expected) && (overallRequired == null || overallPercent >= overallRequired) }
    const rows = report.buckets?.map((row) => ({ key: row.id, match: row.label, label: row.label, row })) ?? analysisCategories.map((key) => ({ key, match: key, label: categoryLabels[key], row: report.categories![key] }))
    const categories = rows.filter(({ row }) => row.expected).map(({ key, match, label, row }): GateRow => {
      const required = named.get(match) ?? (each ? minimum : null)
      const percent = share(row)
      return { key, label, percent, required, met: required == null || percent >= required }
    })
    return { gated: minimum != null, passed: overall.met && categories.every((row) => row.met), overall, categories }
  })
  // The API accepts the completion if any sample solution passes; otherwise show the closest one.
  return results.find((result) => result.gated && result.passed) ?? results.sort((a, b) => b.overall.percent - a.overall.percent)[0] ?? null
}
