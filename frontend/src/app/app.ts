import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

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

@Component({
  selector: 'app-root',
  imports: [ReactiveFormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  protected readonly health = signal<'checking' | 'healthy' | 'unavailable'>('checking');
  protected readonly datasets = signal<DatasetSummary[]>([]);
  protected readonly selectedDataset = signal<Dataset | null>(null);
  protected readonly isLoading = signal(true);
  protected readonly isUploading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly fileControl = new FormControl<File | null>(null);

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
    this.error.set(null);
    this.http.get<Dataset>(`/api/datasets/${dataset.id}`).subscribe({
      next: value => this.selectedDataset.set(value),
      error: error => this.error.set(this.messageFor(error))
    });
  }

  protected valueFor(row: Dataset['preview'][number], column: string): string | number | boolean | null {
    return row[column] ?? null;
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
