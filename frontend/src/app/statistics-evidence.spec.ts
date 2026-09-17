import { TestBed } from '@angular/core/testing';
import { StatisticsEvidence, StatisticsResult, statisticsMarkdown } from './statistics-evidence';

describe('Statistics evidence', () => {
  const stats: StatisticsResult = {
    row_count: 4,
    columns: [{
      column: 'revenue', count: 4, missing_count: 0, nonfinite_count: 0,
      minimum: 0, maximum: 0, mean: 0, median: 0, q1: 0, q3: 0, sample_std: 0,
      outlier_lower: 0, outlier_upper: 0, outlier_count: 0, outlier_examples: [],
      outliers_truncated: false, histogram: [{lower: 0, upper: 0, count: 4}], notes: []
    }],
    correlations: [{column_x: 'revenue', column_y: 'cost', pair_count: 4, pearson: null,
      note: 'Корреляция не определена для постоянной колонки.'}],
    methods: ['Корреляция не доказывает причину.']
  };

  it('keeps zero values distinct from undefined results and exports evidence', async () => {
    await TestBed.configureTestingModule({imports: [StatisticsEvidence]}).compileComponents();
    const fixture = TestBed.createComponent(StatisticsEvidence);
    fixture.componentRef.setInput('stats', stats);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Не определено');
    expect(text).toContain('Выбросы IQR0');
    const markdown = statisticsMarkdown(stats);
    expect(markdown).toContain('Среднее: 0; медиана: 0');
    expect(markdown).toContain('не определена; пар: 4');
    expect(markdown).toContain('Корреляция не доказывает причину.');
  });
});
