import { chartMarkdown, chartOptions, ChartSpec, chronologicalChart } from './chart-evidence';

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

  it('puts ISO month labels and their values in chronological order', () => {
    const ordered = chronologicalChart({
      ...chart,
      x: ['2026-07', '2026-08', '2026-04', '2026-06', '2026-05'],
      series: [{ name: 'revenue', values: [10, 20, 30, 40, 50] }],
    });

    expect(ordered.x).toEqual(['2026-04', '2026-05', '2026-06', '2026-07', '2026-08']);
    expect(ordered.series[0].values).toEqual([30, 50, 40, 10, 20]);
  });
});
