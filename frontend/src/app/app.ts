import { HttpClient } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';

@Component({
  selector: 'app-root',
  imports: [],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  protected readonly health = signal<'checking' | 'healthy' | 'unavailable'>('checking');

  constructor(private readonly http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<{ status: string; database: string }>('/api/health').subscribe({
      next: (response) => this.health.set(
        response.status === 'ok' && response.database === 'connected' ? 'healthy' : 'unavailable'
      ),
      error: () => this.health.set('unavailable')
    });
  }
}
