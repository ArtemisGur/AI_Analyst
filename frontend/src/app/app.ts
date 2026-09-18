import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ChartEvidence, ChartSpec, chartMarkdown } from './chart-evidence';
import { StatisticsEvidence, StatisticsResult, statisticsMarkdown } from './statistics-evidence';

interface DatasetSummary {
  id: string;
  name: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  created_at: string;
}

interface Dataset extends DatasetSummary {
  schema_metadata: ColumnMetadata[];
  preview: Array<Record<string, string | number | boolean | null>>;
}

interface ColumnMetadata {
  name: string;
  dtype: string;
  missing_count: number;
}

interface AnalysisContent {
  summary: string;
  key_findings: string[];
  limitations: string[];
}

interface DatasetAnalysis {
  id: string;
  dataset_id: string;
  question: string;
  created_at: string;
  content: AnalysisContent;
  provider: string;
  model: string;
  usage: { input_tokens: number; output_tokens: number };
  analysis_trace?: Array<{ tool: string; summary: string; sql_query?: string | null; statistics?: StatisticsResult | null; python_code?: string | null; python_result?: PythonResult | null; chart?: ChartSpec | null }>;
}

interface DatasetRows {
  total_rows: number;
  offset: number;
  rows: Array<Record<string, string | number | boolean | null>>;
}

interface PythonResult { result: unknown; row_count: number; column_count: number; execution_ms: number; }

@Component({
  selector: 'app-root',
  imports: [ReactiveFormsModule, StatisticsEvidence, ChartEvidence],
  templateUrl: './app.html',
  styleUrls: ['./app.scss', './analysis-history.scss']
})
export class App implements OnInit {
  protected readonly health = signal<'checking' | 'healthy' | 'unavailable'>('checking');
  protected readonly datasets = signal<DatasetSummary[]>([]);
  protected readonly selectedDataset = signal<Dataset | null>(null);
  protected readonly isLoading = signal(true);
  protected readonly isUploading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly fileControl = new FormControl<File | null>(null);
  protected readonly questionControl = new FormControl('', { nonNullable: true });
  protected readonly analysis = signal<DatasetAnalysis | null>(null);
  protected readonly isAnalyzing = signal(false);
  protected readonly navigationCollapsed = signal(false);
  protected readonly activeTab = signal<'analysis' | 'structure' | 'data'>('analysis');
  protected readonly tableModalOpen = signal(false);
  protected readonly tableRows = signal<DatasetRows | null>(null);
  protected readonly tableLoading = signal(false);
  protected readonly tableError = signal<string | null>(null);
  protected readonly tablePageSize = 100;
  protected readonly history = signal<DatasetAnalysis[]>([]);
  protected readonly historyLoading = signal(false);
  protected readonly historyError = signal<string | null>(null);
  protected readonly historyTotal = signal(0);
  protected readonly historyPage = signal(0);
  protected readonly historyPageCount = computed(() => Math.ceil(this.historyTotal() / this.historyPageSize));
  protected readonly historyPageNumbers = computed(() => {
    const pageCount = this.historyPageCount();
    const start = Math.max(0, Math.min(this.historyPage() - 2, pageCount - 5));
    return Array.from({ length: Math.min(5, pageCount) }, (_, index) => start + index);
  });
  private selectionId: string | null = null;
  private historyRequest = 0;
  protected readonly historyPageSize = 8;

  protected formatDate(value: string): string {
    return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(value));
  }

  protected loadHistory(page = 0): void {
    const id = this.selectedDataset()?.id;
    if (!id || this.historyLoading() || page < 0) return;
    const request = ++this.historyRequest;
    this.historyLoading.set(true);
    this.historyError.set(null);
    const offset = page * this.historyPageSize;
    this.http.get<DatasetAnalysis[]>(`/api/datasets/${id}/analyses?limit=${this.historyPageSize}&offset=${offset}`, { observe: 'response' }).subscribe({
      next: pageResponse => {
        if (this.selectionId !== id || request !== this.historyRequest) return;
        const rows = pageResponse.body ?? [];
        this.history.set(rows);
        this.historyPage.set(page);
        this.historyTotal.set(Number(pageResponse.headers.get('X-Total-Count') ?? rows.length));
        this.historyLoading.set(false);
      },
      error: () => {
        if (this.selectionId !== id || request !== this.historyRequest) return;
        this.historyError.set('Не удалось загрузить историю.');
        this.historyLoading.set(false);
      }
    });
  }

  protected exportAnalysis(item: DatasetAnalysis): void {
    const text = [
      '# Анализ данных', '', `Дата: ${this.formatDate(item.created_at)}`,
      `Датасет: ${this.selectedDataset()?.original_filename ?? ''}`, '',
      '## Вопрос', '', item.question, '', '## Вывод', '', item.content.summary, '',
      '## Ключевые наблюдения', ...item.content.key_findings.map(value => `- ${value}`), '',
      '## Ограничения', ...item.content.limitations.map(value => `- ${value}`), '',
      '## Ход анализа', ...(item.analysis_trace ?? []).map(step =>
        `- ${this.traceLabel(step.tool)}: ${step.summary}` + (step.sql_query ? `\n\n\`\`\`sql\n${step.sql_query}\n\`\`\`\n` : '') + (step.python_code ? `\n\n\`\`\`python\n${step.python_code}\n\`\`\`\n\nРезультат:\n\n\`\`\`json\n${this.pythonResultJson(step.python_result)}\n\`\`\`\n` : '') + (step.chart ? chartMarkdown(step.chart) : '') + (step.statistics ? statisticsMarkdown(step.statistics) : ''))
    ].join('\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `analysis-${item.created_at.slice(0, 10)}-${item.id}.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  constructor(private readonly http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<{ status: string; database: string }>('/api/health').subscribe({
      next: response => this.health.set(
        response.status === 'ok' && response.database === 'connected' ? 'healthy' : 'unavailable'
      ),
      error: () => this.health.set('unavailable')
    });
    this.loadDatasets();
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.fileControl.setValue(input.files?.item(0) ?? null);
    this.error.set(null);
  }

  protected upload(): void {
    const file = this.fileControl.value;
    if (!file) {
      this.error.set('Сначала выберите файл CSV или XLSX.');
      return;
    }
    const payload = new FormData();
    payload.append('file', file);
    this.isUploading.set(true);
    this.error.set(null);
    this.http.post<Dataset>('/api/datasets', payload).subscribe({
      next: dataset => {
        this.datasets.update(items => [dataset, ...items]);
        this.selectedDataset.set(dataset);
        this.selectionId = dataset.id;
        this.history.set([]);
        this.historyLoading.set(false);
        this.historyTotal.set(0);
        this.historyPage.set(0);
        this.historyError.set(null);
        this.analysis.set(null);
        this.activeTab.set('analysis');
        this.fileControl.reset();
        this.isUploading.set(false);
      },
      error: error => {
        this.error.set(this.messageFor(error));
        this.isUploading.set(false);
      }
    });
  }

  protected selectDataset(dataset: DatasetSummary): void {
    if (this.selectedDataset()?.id === dataset.id) return;
    this.selectionId = dataset.id;
    this.selectedDataset.set(null);
    this.history.set([]);
    this.historyLoading.set(false);
    this.historyTotal.set(0);
    this.historyPage.set(0);
    this.historyError.set(null);
    this.error.set(null);
    this.analysis.set(null);
    this.activeTab.set('analysis');
    this.tableModalOpen.set(false);
    this.tableRows.set(null);
    this.http.get<Dataset>(`/api/datasets/${dataset.id}`).subscribe({
      next: value => {
        if (this.selectionId !== dataset.id) return;
        this.selectedDataset.set(value);
        this.loadHistory();
      },
      error: error => this.error.set(this.messageFor(error))
    });
  }

  protected deleteDataset(): void {
    const dataset = this.selectedDataset();
    if (!dataset || !confirm(`Удалить датасет «${dataset.original_filename}» и его историю анализов?`)) return;
    this.http.delete(`/api/datasets/${dataset.id}`).subscribe({
      next: () => {
        this.datasets.update(items => items.filter(item => item.id !== dataset.id));
        if (this.selectionId === dataset.id) {
          this.selectionId = null;
          this.selectedDataset.set(null);
          this.analysis.set(null);
          this.history.set([]);
          this.tableModalOpen.set(false);
        }
      },
      error: error => this.error.set(this.messageFor(error))
    });
  }

  protected valueFor(row: Record<string, string | number | boolean | null>, column: string): string | number | boolean | null {
    return row[column] ?? null;
  }

  protected openTableModal(): void {
    this.tableModalOpen.set(true);
    this.loadTableRows(0);
  }

  protected closeTableModal(): void {
    this.tableModalOpen.set(false);
  }

  protected loadTableRows(offset: number): void {
    const dataset = this.selectedDataset();
    if (!dataset || this.tableLoading()) return;
    this.tableLoading.set(true);
    this.tableError.set(null);
    this.http.get<DatasetRows>(
      `/api/datasets/${dataset.id}/rows?limit=${this.tablePageSize}&offset=${offset}`
    ).subscribe({
      next: page => {
        if (this.selectedDataset()?.id === dataset.id) this.tableRows.set(page);
        this.tableLoading.set(false);
      },
      error: error => {
        this.tableError.set(this.messageFor(error));
        this.tableLoading.set(false);
      }
    });
  }

  protected analyze(): void {
    const dataset = this.selectedDataset();
    const question = this.questionControl.value.trim();
    if (!dataset || this.isAnalyzing()) return;
    if (question.length < 3) {
      this.error.set('Задайте вопрос длиной не менее трёх символов.');
      return;
    }
    this.error.set(null);
    this.isAnalyzing.set(true);
    this.analysis.set(null);
    this.http.post<DatasetAnalysis>(`/api/datasets/${dataset.id}/analysis`, { question }).subscribe({
      next: analysis => {
        if (this.selectedDataset()?.id === dataset.id) {
          this.analysis.set(analysis);
          this.loadHistory();
        }
        this.isAnalyzing.set(false);
      },
      error: error => {
        this.error.set(this.messageFor(error));
        this.isAnalyzing.set(false);
      }
    });
  }

  protected typeLabel(dtype: string): string {
    const normalized = dtype.toLowerCase();
    if (normalized.includes('datetime')) return 'Дата и время';
    if (normalized.includes('int')) return 'Целое число';
    if (normalized.includes('float') || normalized.includes('double')) return 'Число';
    if (normalized.includes('bool')) return 'Да / нет';
    return 'Текст';
  }

  protected traceLabel(tool: string): string {
    if (tool === 'execute_sql') return 'SQL-анализ';
    if (tool === 'column_statistics') return 'Статистика и выбросы';
    if (tool === 'execute_python') return 'Python-анализ';
    if (tool === 'create_chart') return 'График';
    return tool === 'dataset_summary' ? 'Сводка датасета' : tool === 'group_by_metric' ? 'Группировка по метрике' : 'Проверка данных';
  }

  protected pythonResultJson(result: PythonResult | null | undefined): string {
    return JSON.stringify(result?.result ?? null, null, 2);
  }

  private loadDatasets(): void {
    this.http.get<DatasetSummary[]>('/api/datasets').subscribe({
      next: datasets => {
        this.datasets.set(datasets);
        this.isLoading.set(false);
        if (datasets[0]) this.selectDataset(datasets[0]);
      },
      error: error => {
        this.error.set(this.messageFor(error));
        this.isLoading.set(false);
      }
    });
  }

  private messageFor(error: unknown): string {
    if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return 'Не удалось выполнить запрос. Проверьте работу API и повторите попытку.';
  }
}
