import { chartMarkdown, chartOptions, ChartSpec } from './chart-evidence';

describe('Chart evidence', () => {
  const chart: ChartSpec = {
    type: 'line', title: 'Выручка по месяцам', x: ['2026-05', '2026-06'],
    series: [{ name: 'revenue', values: [120, 150] }], source_rows: 40, truncated: false,
  };

  it('creates an accessible ECharts option from verified values', () => {
    const option = chartOptions(chart);
    expect(option.aria).toEqual({ enabled: true });
    expect(option.xAxis).toMatchObject({ data: ['2026-05', '2026-06'] });
    expect(option.series).toMatchObject([{ type: 'line', data: [120, 150] }]);
  });

  it('exports chart data as Markdown', () => {
    expect(chartMarkdown(chart)).toContain('| 2026-06 | 150 |');
  });
});
