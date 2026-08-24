import { Component, OnInit, ElementRef, ViewChild, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BacktestService, BacktestResult } from './backtest.service';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  @ViewChild('portfolioChart') chartCanvas?: ElementRef<HTMLCanvasElement>;

  tickers: string[] = [];
  strategies: string[] = [];

  selectedTicker = '';
  selectedStrategy = '';
  startDate = '';
  endDate = '';

  result: BacktestResult | null = null;
  loading = false;
  errorMessage = '';

  private chart: Chart | null = null;

  constructor(
    private backtestService: BacktestService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.backtestService.getTickers().subscribe({
      next: (res: { tickers: string[] }) => {
        this.tickers = res.tickers;
        if (this.tickers.length) this.selectedTicker = this.tickers[0];
      },
      error: () => {
        this.errorMessage = 'Could not reach the backend API. Is Flask running on port 5001?';
      }
    });

    this.backtestService.getStrategies().subscribe({
      next: (res: { strategies: string[] }) => {
        this.strategies = res.strategies;
        if (this.strategies.length) this.selectedStrategy = this.strategies[0];
      }
    });
  }

  runBacktest(): void {
    if (!this.selectedTicker || !this.selectedStrategy) return;

    this.loading = true;
    this.errorMessage = '';
    this.result = null;
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }

    this.backtestService
      .runBacktest(this.selectedTicker, this.selectedStrategy, this.startDate || undefined, this.endDate || undefined)
      .subscribe({
        next: (res: BacktestResult) => {
          this.result = res;
          this.loading = false;

          // Force Angular to synchronously apply the *ngIf="result" template
          // change now, so the <canvas> element exists in the DOM before we
          // try to attach Chart.js to it. Without this, this.chartCanvas can
          // still be undefined at this point.
          this.cdr.detectChanges();

          // One more tick to be safe for layout/sizing before Chart.js reads
          // the canvas's rendered dimensions.
          requestAnimationFrame(() => this.drawChart());
        },
        error: (err: any) => {
          this.errorMessage = err?.error?.error || 'Something went wrong running the backtest.';
          this.loading = false;
        }
      });
  }

  private drawChart(): void {
    if (!this.result || !this.chartCanvas) {
      console.warn('Chart not drawn: missing result or canvas ref', this.result, this.chartCanvas);
      return;
    }

    if (this.chart) {
      this.chart.destroy();
    }

    const labels = this.result.portfolio_series.map(p => p.date);
    const values = this.result.portfolio_series.map(p => p.value);

    this.chart = new Chart(this.chartCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: `${this.result.ticker} Portfolio Value`,
          data: values,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.12)',
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          tension: 0.15
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { maxTicksLimit: 10, color: '#6b7280' },
            grid: { display: false },
            border: { color: '#1f2530' }
          },
          y: {
            ticks: {
              color: '#6b7280',
              callback: (value) => '$' + Number(value).toLocaleString()
            },
            grid: { color: '#1a1f2b' },
            border: { color: '#1f2530' }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#12161f',
            borderColor: '#262b38',
            borderWidth: 1,
            titleColor: '#e5e7eb',
            bodyColor: '#e5e7eb',
            callbacks: {
              label: (ctx) => '$' + Number(ctx.parsed.y).toLocaleString(undefined, { maximumFractionDigits: 0 })
            }
          }
        }
      }
    });
  }
}