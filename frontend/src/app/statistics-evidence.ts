import { Component, input } from '@angular/core';

export interface StatisticsResult {
  row_count: number;
  columns: Array<{
    column: string; count: number; missing_count: number; nonfinite_count: number;
    minimum: number | null; maximum: number | null; mean: number | null;
    median: number | null; q1: number | null; q3: number | null; sample_std: number | null;
    outlier_lower: number | null; outlier_upper: number | null; outlier_count: number | null;
    outliers_truncated: boolean; notes: string[];
    outlier_examples: Array<{data_row: number; value: number}>;
    histogram: Array<{lower: number; upper: number; count: number}>;
  }>;
  correlations: Array<{
    column_x: string; column_y: string; pair_count: number; pearson: number | null; note: string | null;
  }>;
  methods: string[];
}

export function statisticsMarkdown(stats: StatisticsResult): string {
  return ['\n### Числовые результаты', `Строк в файле: ${stats.row_count}`, ...stats.columns.flatMap(c => [
    `\n#### ${c.column}`, `- Значений: ${c.count}; пропусков: ${c.missing_count}; бесконечных: ${c.nonfinite_count}`,
    `- Минимум: ${c.minimum ?? '—'}; максимум: ${c.maximum ?? '—'}`,
    `- Среднее: ${c.mean ?? '—'}; медиана: ${c.median ?? '—'}; стандартное отклонение: ${c.sample_std ?? '—'}`,
    `- Q1: ${c.q1 ?? '—'}; Q3: ${c.q3 ?? '—'}`,
    `- Выбросов: ${c.outlier_count ?? 'не определено'}; границы: ${c.outlier_lower ?? '—'} … ${c.outlier_upper ?? '—'}`,
    ...c.outlier_examples.map(o => `  - Строка данных ${o.data_row}: ${o.value}`),
    ...(c.outliers_truncated ? ['- Показаны первые 10 выбросов.'] : []),
    '- Распределение:', ...c.histogram.map(b => `  - ${b.lower} … ${b.upper}: ${b.count}`),
    ...c.notes.map(n => `- ${n}`)
  ]), '\n#### Корреляции Пирсона', ...stats.correlations.map(c =>
    `- ${c.column_x} / ${c.column_y}: ${c.pearson ?? 'не определена'}; пар: ${c.pair_count}. ${c.note ?? ''}`),
    '\n#### Методика', ...stats.methods.map(m => `- ${m}`)].join('\n');
}

@Component({
  selector: 'app-statistics-evidence',
  template: `
    <details class="evidence"><summary>Числовые результаты · {{ stats().row_count }} строк</summary>
      @for (column of stats().columns; track column.column) {
        <article><h5>{{ column.column }}</h5>
          <p>Значений: {{ column.count }} · Пропусков: {{ column.missing_count }} · Бесконечных: {{ column.nonfinite_count }}</p>
          <dl>
            <div><dt>Среднее</dt><dd>{{ number(column.mean) }}</dd></div>
            <div><dt>Медиана</dt><dd>{{ number(column.median) }}</dd></div>
            <div><dt>Минимум / максимум</dt><dd>{{ number(column.minimum) }} / {{ number(column.maximum) }}</dd></div>
            <div><dt>Стандартное отклонение</dt><dd>{{ number(column.sample_std) }}</dd></div>
            <div><dt>Квартили Q1 / Q3</dt><dd>{{ number(column.q1) }} / {{ number(column.q3) }}</dd></div>
            <div><dt>Выбросы IQR</dt><dd>{{ column.outlier_count ?? 'Не определены' }}</dd></div>
          </dl>
          @if (column.outlier_count !== null) {
            <p>Границы IQR: {{ number(column.outlier_lower) }} … {{ number(column.outlier_upper) }}</p>
            @for (item of column.outlier_examples; track item.data_row) {
              <p>Строка данных {{ item.data_row }}: {{ number(item.value) }}</p>
            }
            @if (column.outliers_truncated) { <p>Показаны первые 10 выбросов.</p> }
          }
          @if (column.histogram.length) {
            <details><summary>Распределение значений</summary>
              @for (bin of column.histogram; track $index) { <p>{{ number(bin.lower) }} … {{ number(bin.upper) }}: <b>{{ bin.count }}</b></p> }
            </details>
          }
          @for (note of column.notes; track $index) { <p class="note">{{ note }}</p> }
        </article>
      }
      @if (stats().correlations.length) {
        <h5>Корреляции Пирсона</h5>
        @for (pair of stats().correlations; track $index) {
          <p>{{ pair.column_x }} / {{ pair.column_y }}: <b>{{ number(pair.pearson) }}</b> · {{ pair.pair_count }} пар</p>
          @if (pair.note) { <p class="note">{{ pair.note }}</p> }
        }
      }
      <details class="methods"><summary>Методика и ограничения</summary>
        @for (method of stats().methods; track $index) { <p>{{ method }}</p> }
      </details>
    </details>`,
  styles: `
    :host { display: block; grid-column: 1 / -1; min-width: 0; }
    .evidence { margin-top: 12px; padding: 14px; border: 1px solid #dde5ef; border-radius: 10px; background: #f8fafc; }
    summary { cursor: pointer; color: #405b95; font-weight: 600; }
    article { padding: 12px 0; border-bottom: 1px solid #e4e7ee; }
    h5 { font-size: 14px; margin: 12px 0 8px; overflow-wrap: anywhere; }
    p { font-size: 12px; line-height: 1.65; margin: 6px 0; overflow-wrap: anywhere; }
    dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 12px; }
    dt { font-size: 11px; color: #64748b; } dd { margin: 4px 0 0; font-size: 14px; overflow-wrap: anywhere; }
    .note { color: #8a6e47; } .methods { margin-top: 16px; }
  `
})
export class StatisticsEvidence {
  readonly stats = input.required<StatisticsResult>();
  protected number(value: number | null): string {
    if (value === null) return 'Не определено';
    return new Intl.NumberFormat('ru-RU', { maximumSignificantDigits: 6 }).format(value);
  }
}
