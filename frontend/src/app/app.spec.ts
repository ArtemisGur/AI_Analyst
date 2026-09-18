import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the datasets workspace', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/health').flush({
      status: 'ok',
      database: 'connected'
    });
    TestBed.inject(HttpTestingController).expectOne('/api/datasets').flush([]);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Датасеты');
    expect(compiled.textContent).toContain('Подключите первый датасет');
  });

  it('should submit a question and render the structured analysis', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/health').flush({ status: 'ok', database: 'connected' });
    http.expectOne('/api/datasets').flush([{
      id: 'dataset-id', name: 'sales', original_filename: 'sales.csv',
      row_count: 2, column_count: 2, created_at: '2026-01-01T00:00:00Z'
    }]);
    http.expectOne('/api/datasets/dataset-id').flush({
      id: 'dataset-id', name: 'sales', original_filename: 'sales.csv',
      row_count: 2, column_count: 2, created_at: '2026-01-01T00:00:00Z',
      schema_metadata: [], preview: []
    });

    http.expectOne('/api/datasets/dataset-id/analyses?limit=8&offset=0').flush([]);
    const app = fixture.componentInstance as any;
    app.questionControl.setValue('Что происходит с выручкой?');
    app.analyze();
    const request = http.expectOne('/api/datasets/dataset-id/analysis');
    expect(request.request.body).toEqual({ question: 'Что происходит с выручкой?' });
    request.flush({
      id: 'analysis-id', dataset_id: 'dataset-id', question: 'Что происходит с выручкой?',
      created_at: '2026-09-17T10:00:00Z',
      content: {
        summary: 'Выручка требует дополнительной проверки.',
        key_findings: ['В preview есть пропуск.'],
        evidence: [{ finding_index: 0, trace_step_indexes: [0] }],
        limitations: ['Доступен только preview.']
      },
      provider: 'openai', model: 'gpt-5.5', usage: { input_tokens: 10, output_tokens: 5 },
      analysis_trace: [{ turn: 1, tool: 'dataset_summary', summary: 'Проверено', duration_ms: 12, result_preview: '{"row_count": 2}' }]
    });
    http.expectOne('/api/datasets/dataset-id/analyses?limit=8&offset=0').flush([app.analysis()]);
    fixture.detectChanges();
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('.history-item')?.textContent).toContain('Что происходит с выручкой?');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ключевые наблюдения');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('В preview есть пропуск.');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Подтверждено: Шаг 1: Сводка датасета');
  });

  it('shows eight saved analyses per page and requests the next offset', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/health').flush({ status: 'ok', database: 'connected' });
    http.expectOne('/api/datasets').flush([{
      id: 'dataset-id', name: 'sales', original_filename: 'sales.csv',
      row_count: 2, column_count: 2, created_at: '2026-01-01T00:00:00Z'
    }]);
    http.expectOne('/api/datasets/dataset-id').flush({
      id: 'dataset-id', name: 'sales', original_filename: 'sales.csv',
      row_count: 2, column_count: 2, created_at: '2026-01-01T00:00:00Z', schema_metadata: [], preview: []
    });
    http.expectOne('/api/datasets/dataset-id/analyses?limit=8&offset=0').flush([]);

    (fixture.componentInstance as any).loadHistory(1);
    const request = http.expectOne('/api/datasets/dataset-id/analyses?limit=8&offset=8');
    request.flush(Array.from({ length: 8 }, (_, index) => ({
      id: `analysis-${index}`, dataset_id: 'dataset-id', question: `Вопрос ${index}`,
      created_at: '2026-09-18T00:00:00Z', content: { summary: 'Вывод', key_findings: [], limitations: [] },
      provider: 'openai', model: 'test', usage: { input_tokens: 1, output_tokens: 1 }
    })), { headers: { 'X-Total-Count': '17' } });

    const app = fixture.componentInstance as any;
    expect(app.history().length).toBe(8);
    expect(app.historyPage()).toBe(1);
    expect(app.historyPageCount()).toBe(3);
  });
});
