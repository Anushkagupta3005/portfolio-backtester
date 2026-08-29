import { Component, OnInit, ElementRef, ViewChild, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BacktestService, BacktestResult, CompareResult, HistoryRun } from './backtest.service';
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
  // one canvas ref per chart in the Run Backtest grid
  @ViewChild('portfolioChart') portfolioCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('drawdownChart') drawdownCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('priceChart') priceCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('rsiChart') rsiCanvas?: ElementRef<HTMLCanvasElement>;
  // canvas for the Compare Strategies overlay chart
  @ViewChild('compareChart') compareCanvas?: ElementRef<HTMLCanvasElement>;

  activeTab: 'run' | 'compare' | 'history' = 'run';

  // sub-tab within the pre-run explorer panel (Quick picks / How it works / Result preview)
  explorerTab: 'picks' | 'how' | 'preview' = 'picks';

  tickers: string[] = [];
  strategies: string[] = [];

  selectedTicker = '';
  selectedStrategy = '';
  startDate = '';
  endDate = '';

  result: BacktestResult | null = null;
  loading = false;
  errorMessage = '';

  // "saved" state resets to false every time a fresh result comes in,
  // so the button always reflects whether *this* result is saved yet
  runSaved = false;
  runSaving = false;

  // Compare Strategies tab state -- deliberately separate from the Run
  // Backtest state above rather than reused, since the two tabs run
  // independently and switching tabs shouldn't clear either one's results
  compareTicker = '';
  compareStartDate = '';
  compareEndDate = '';
  compareResult: CompareResult | null = null;
  compareLoading = false;
  compareErrorMessage = '';
  compareSaved = false;
  compareSaving = false;

  // History tab state
  historyRuns: HistoryRun[] = [];
  historyLoading = false;
  historyErrorMessage = '';
  // id of the run currently being edited inline, or null if none
  editingNoteId: number | null = null;
  editingNoteText = '';

  // Add Ticker state (Quick Picks panel)
  showAddTicker = false;
  newTickerSymbol = '';
  addingTicker = false;
  addTickerError = '';
  addTickerSuccess = '';

  private portfolioChart: Chart | null = null;
  private drawdownChart: Chart | null = null;
  private priceChart: Chart | null = null;
  private rsiChart: Chart | null = null;
  private compareChart: Chart | null = null;

  constructor(
    private backtestService: BacktestService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.backtestService.getTickers().subscribe({
      next: (res: { tickers: string[] }) => {
        this.tickers = res.tickers;
        if (this.tickers.length) {
          this.selectedTicker = this.tickers[0];
          this.compareTicker = this.tickers[0];
        }
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

    // fetched quietly on load, independent of which tab is active, so the
    // header badge is accurate the moment the page opens
    this.backtestService.getHistory().subscribe({
      next: (res) => {
        this.lastRunAt = res.runs.length ? res.runs[0].created_at : null;
      },
      error: () => {
        // header badge silently stays on its "no runs yet" default;
        // this isn't worth surfacing as a page-level error
      }
    });
  }

  lastRunAt: string | null = null;

  get lastRunLabel(): string {
    if (!this.lastRunAt) return 'No runs yet';

    // created_at comes back as "YYYY-MM-DD HH:MM:SS" (MySQL TIMESTAMP
    // format via the API) -- Safari's Date parser rejects that format
    // with a space separator, so normalize to ISO-with-T first
    const isoLike = this.lastRunAt.replace(' ', 'T');
    const then = new Date(isoLike).getTime();
    if (isNaN(then)) return 'Last run: unknown';

    const diffMs = Date.now() - then;
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return 'Last run: just now';
    if (diffMin < 60) return `Last run: ${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `Last run: ${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    return `Last run: ${diffDay}d ago`;
  }

  setTab(tab: 'run' | 'compare' | 'history'): void {
    this.activeTab = tab;
    // the compare canvas only exists in the DOM once its tab is active
    // and compareResult is set, so redraw when switching back to it
    if (tab === 'compare' && this.compareResult) {
      this.cdr.detectChanges();
      requestAnimationFrame(() => this.drawCompareChart());
    }
    if (tab === 'history') {
      this.loadHistory();
    }
  }

  get isRsiStrategy(): boolean {
    return this.selectedStrategy === 'RSI' || this.result?.strategy === 'RSI';
  }

  get winCount(): number {
    if (!this.result) return 0;
    return this.result.trade_log.filter(t => t.pnl >= 0).length;
  }

  saveRunToHistory(): void {
    if (!this.result || this.runSaving) return;
    this.runSaving = true;

    this.backtestService.saveToHistory({
      ticker: this.result.ticker,
      strategy: this.result.strategy,
      start_date: this.startDate || undefined,
      end_date: this.endDate || undefined,
      total_return: this.result.metrics.total_return,
      cagr: this.result.metrics.cagr,
      sharpe_ratio: this.result.metrics.sharpe_ratio,
      max_drawdown: this.result.metrics.max_drawdown,
      final_value: this.result.metrics.final_value,
    }).subscribe({
      next: () => {
        this.runSaved = true;
        this.runSaving = false;
      },
      error: () => {
        this.errorMessage = 'Could not save this run to history.';
        this.runSaving = false;
      }
    });
  }

  saveCompareToHistory(): void {
    if (!this.compareResult || this.compareSaving) return;
    this.compareSaving = true;

    const ranked = this.compareRankedStrategies;
    const saves = ranked.map(name => {
      const r = this.compareResult!.results[name];
      return this.backtestService.saveToHistory({
        ticker: r.ticker,
        strategy: r.strategy,
        start_date: this.compareStartDate || undefined,
        end_date: this.compareEndDate || undefined,
        total_return: r.metrics.total_return,
        cagr: r.metrics.cagr,
        sharpe_ratio: r.metrics.sharpe_ratio,
        max_drawdown: r.metrics.max_drawdown,
        final_value: r.metrics.final_value,
      });
    });

    // fire all three saves; if any fails, still let the succeeding ones
    // through rather than losing everything to one bad request
    let remaining = saves.length;
    let hadError = false;
    saves.forEach(obs => obs.subscribe({
      next: () => {
        remaining--;
        if (remaining === 0) {
          this.compareSaving = false;
          this.compareSaved = !hadError;
          if (hadError) this.compareErrorMessage = 'Some strategies could not be saved to history.';
        }
      },
      error: () => {
        hadError = true;
        remaining--;
        if (remaining === 0) {
          this.compareSaving = false;
          this.compareErrorMessage = 'Some strategies could not be saved to history.';
        }
      }
    }));
  }

  loadHistory(): void {
    this.historyLoading = true;
    this.historyErrorMessage = '';
    this.backtestService.getHistory().subscribe({
      next: (res) => {
        this.historyRuns = res.runs;
        this.historyLoading = false;
      },
      error: () => {
        this.historyErrorMessage = 'Could not load history.';
        this.historyLoading = false;
      }
    });
  }

  startEditingNote(run: HistoryRun): void {
    this.editingNoteId = run.id;
    this.editingNoteText = run.note ?? '';
  }

  cancelEditingNote(): void {
    this.editingNoteId = null;
    this.editingNoteText = '';
  }

  saveNote(run: HistoryRun): void {
    this.backtestService.updateHistoryNote(run.id, this.editingNoteText).subscribe({
      next: () => {
        run.note = this.editingNoteText;
        this.editingNoteId = null;
      },
      error: () => {
        this.historyErrorMessage = 'Could not save the note.';
      }
    });
  }

  deleteRun(run: HistoryRun): void {
    this.backtestService.deleteHistoryRun(run.id).subscribe({
      next: () => {
        this.historyRuns = this.historyRuns.filter(r => r.id !== run.id);
      },
      error: () => {
        this.historyErrorMessage = 'Could not delete this run.';
      }
    });
  }

  toggleAddTicker(): void {
    this.showAddTicker = !this.showAddTicker;
    this.addTickerError = '';
    this.addTickerSuccess = '';
  }

  addNewTicker(): void {
    const symbol = this.newTickerSymbol.trim().toUpperCase();
    if (!symbol || this.addingTicker) return;

    this.addingTicker = true;
    this.addTickerError = '';
    this.addTickerSuccess = '';

    this.backtestService.addTicker(symbol).subscribe({
      next: (res) => {
        this.addingTicker = false;
        this.addTickerSuccess = `${res.ticker} added — ${res.rows_loaded} days of data loaded.`;
        this.newTickerSymbol = '';
        // fold the new ticker straight into the dropdown lists so it's
        // immediately usable without a manual page refresh
        if (!this.tickers.includes(res.ticker)) {
          this.tickers = [...this.tickers, res.ticker].sort();
        }
      },
      error: (err: any) => {
        this.addingTicker = false;
        this.addTickerError = err?.error?.error || `Could not add ${symbol}. Check the symbol and try again.`;
      }
    });
  }

  downloadCsv(): void {
    if (!this.result || !this.result.trade_log.length) return;

    const header = ['Entry Date', 'Entry Price', 'Exit Date', 'Exit Price', 'Shares', 'P&L', 'P&L %', 'Running P&L'];
    let runningPnl = 0;

    const rows = this.result.trade_log.map(t => {
      runningPnl += t.pnl;
      return [
        t.entry_date,
        t.entry_price.toFixed(2),
        t.exit_date,
        t.exit_price.toFixed(2),
        t.shares,
        t.pnl.toFixed(2),
        t.pnl_pct.toFixed(2),
        runningPnl.toFixed(2)
      ].join(',');
    });

    const csvContent = [header.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.result.ticker}_${this.result.strategy.replace(/\s+/g, '-')}_trades.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  private destroyCharts(): void {
    this.portfolioChart?.destroy();
    this.drawdownChart?.destroy();
    this.priceChart?.destroy();
    this.rsiChart?.destroy();
    this.portfolioChart = null;
    this.drawdownChart = null;
    this.priceChart = null;
    this.rsiChart = null;
  }

  runCompare(): void {
    if (!this.compareTicker) return;

    this.compareLoading = true;
    this.compareErrorMessage = '';
    this.compareResult = null;
    this.compareSaved = false;
    this.compareChart?.destroy();
    this.compareChart = null;

    this.backtestService
      .compareStrategies(this.compareTicker, this.compareStartDate || undefined, this.compareEndDate || undefined)
      .subscribe({
        next: (res: CompareResult) => {
          this.compareResult = res;
          this.compareLoading = false;
          this.cdr.detectChanges();
          requestAnimationFrame(() => this.drawCompareChart());
        },
        error: (err: any) => {
          this.compareErrorMessage = err?.error?.error || 'Something went wrong comparing strategies.';
          this.compareLoading = false;
        }
      });
  }

  // strategies the compare run actually succeeded for, in rank order --
  // used by both the chart and the leaderboard template so they never
  // disagree about which strategies are shown
  get compareRankedStrategies(): string[] {
    return this.compareResult?.ranking ?? [];
  }

  // ranking excludes strategies that errored (e.g. RSI on a range too
  // short for its warm-up period); surfaced separately so the template
  // can show a plain "unavailable" note instead of silently omitting them
  get compareFailedStrategies(): string[] {
    if (!this.compareResult) return [];
    return Object.keys(this.compareResult.results).filter(
      name => this.compareResult!.results[name].error
    );
  }

  private strategyColor(name: string): string {
    switch (name) {
      case 'SMA': return '#3b82f6';
      case 'RSI': return '#a78bfa';
      case 'Buy & Hold': return '#f59e0b';
      default: return '#6b7280';
    }
  }

  private drawCompareChart(): void {
    if (!this.compareResult || !this.compareCanvas) return;

    const ranked = this.compareRankedStrategies;
    if (!ranked.length) return;

    // portfolio_series length/dates can differ slightly between
    // strategies right at the edges (RSI's warm-up period trims its
    // first ~14 rows), so use the longest series' dates as the shared
    // x-axis and let Chart.js leave gaps where a shorter series has no
    // point yet, rather than forcing a naive zip that could misalign
    // dates between strategies
    const longest = ranked.reduce((a, b) =>
      this.compareResult!.results[a].portfolio_series.length >=
      this.compareResult!.results[b].portfolio_series.length ? a : b
    );
    const labels = this.compareResult.results[longest].portfolio_series.map(p => p.date);

    const datasets = ranked.map(name => {
      const series = this.compareResult!.results[name].portfolio_series;
      const byDate = new Map(series.map(p => [p.date, p.value]));
      const color = this.strategyColor(name);
      return {
        label: name,
        data: labels.map(d => byDate.get(d) ?? null),
        borderColor: color,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0.15,
        spanGaps: true
      };
    });

    this.compareChart = new Chart(this.compareCanvas.nativeElement, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { maxTicksLimit: 10, color: '#7b8494' },
            grid: { display: false },
            border: { color: '#232b39' }
          },
          y: {
            ticks: {
              color: '#7b8494',
              callback: (value) => '$' + Number(value).toLocaleString()
            },
            grid: { color: '#1e2531' },
            border: { color: '#232b39' }
          }
        },
        plugins: {
          legend: {
            display: true,
            labels: { color: '#9ca3af', boxWidth: 10, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: '#151b26',
            borderColor: '#232b39',
            borderWidth: 1,
            titleColor: '#e6e8ec',
            bodyColor: '#e6e8ec',
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            }
          }
        }
      }
    });
  }

  runBacktest(): void {
    if (!this.selectedTicker || !this.selectedStrategy) return;

    this.loading = true;
    this.errorMessage = '';
    this.result = null;
    this.runSaved = false;
    this.destroyCharts();

    this.backtestService
      .runBacktest(this.selectedTicker, this.selectedStrategy, this.startDate || undefined, this.endDate || undefined)
      .subscribe({
        next: (res: BacktestResult) => {
          this.result = res;
          this.loading = false;

          // Force Angular to synchronously apply the *ngIf="result" template
          // change now, so the <canvas> elements exist in the DOM before we
          // try to attach Chart.js to them.
          this.cdr.detectChanges();

          // One more tick to be safe for layout/sizing before Chart.js reads
          // each canvas's rendered dimensions.
          requestAnimationFrame(() => this.drawAllCharts());
        },
        error: (err: any) => {
          this.errorMessage = err?.error?.error || 'Something went wrong running the backtest.';
          this.loading = false;
        }
      });
  }

  private drawAllCharts(): void {
    if (!this.result) return;
    this.drawPortfolioChart();
    this.drawDrawdownChart();
    this.drawPriceChart();
    if (this.result.strategy === 'RSI') {
      this.drawRsiChart();
    }
  }

  private baseAxisOptions() {
    return {
      x: {
        ticks: { maxTicksLimit: 8, color: '#6b7280' },
        grid: { display: false },
        border: { color: '#1f2530' }
      }
    };
  }

  private drawPortfolioChart(): void {
    if (!this.result || !this.portfolioCanvas) return;

    const labels = this.result.portfolio_series.map(p => p.date);
    const values = this.result.portfolio_series.map(p => p.value);

    this.portfolioChart = new Chart(this.portfolioCanvas.nativeElement, {
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
          ...this.baseAxisOptions(),
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

  private drawDrawdownChart(): void {
    if (!this.result || !this.drawdownCanvas) return;

    const labels = this.result.drawdown_series.map(p => p.date);
    // negate so drawdown reads as a dip below zero, matching the
    // fill_between(..., 0, -dd, ...) look from the matplotlib version
    const values = this.result.drawdown_series.map(p => -p.drawdown);

    this.drawdownChart = new Chart(this.drawdownCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Drawdown',
          data: values,
          borderColor: '#f87171',
          backgroundColor: 'rgba(248, 113, 113, 0.18)',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          tension: 0.1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          ...this.baseAxisOptions(),
          y: {
            max: 0,
            ticks: {
              color: '#6b7280',
              callback: (value) => Number(value).toFixed(0) + '%'
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
              label: (ctx) => Number(ctx.parsed.y).toFixed(2) + '%'
            }
          }
        }
      }
    });
  }

  private drawPriceChart(): void {
    if (!this.result || !this.priceCanvas) return;

    const series = this.result.price_series;
    const labels = series.map(p => p.date);
    const prices = series.map(p => p.price);

    // BUY/SELL markers plotted as sparse scatter points on the same
    // label axis as the price line -- null everywhere except the signal day
    const buyPoints = series.map(p => (p.signal === 'BUY' ? p.price : null));
    const sellPoints = series.map(p => (p.signal === 'SELL' ? p.price : null));

    this.priceChart = new Chart(this.priceCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: `${this.result.ticker} Close`,
            data: prices,
            borderColor: '#9ca3af',
            borderWidth: 1.25,
            pointRadius: 0,
            fill: false,
            tension: 0.1
          },
          {
            label: 'Buy',
            data: buyPoints,
            borderColor: '#4ade80',
            backgroundColor: '#4ade80',
            pointStyle: 'triangle',
            pointRadius: 6,
            pointHoverRadius: 8,
            showLine: false
          },
          {
            label: 'Sell',
            data: sellPoints,
            borderColor: '#f87171',
            backgroundColor: '#f87171',
            pointStyle: 'rectRot',
            pointRadius: 6,
            pointHoverRadius: 8,
            showLine: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          ...this.baseAxisOptions(),
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
          legend: {
            display: true,
            labels: { color: '#9ca3af', boxWidth: 10, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: '#12161f',
            borderColor: '#262b38',
            borderWidth: 1,
            titleColor: '#e5e7eb',
            bodyColor: '#e5e7eb',
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed.y).toFixed(2)}`
            }
          }
        }
      }
    });
  }

  private drawRsiChart(): void {
    if (!this.result || !this.rsiCanvas || !this.result.rsi_series.length) return;

    const labels = this.result.rsi_series.map(p => p.date);
    const values = this.result.rsi_series.map(p => p.rsi);
    // flat reference lines at the 30/70 thresholds -- drawn as ordinary
    // datasets (constant value repeated) since no annotation plugin is
    // installed; this keeps the dependency list unchanged from what
    // Session 7 already has (Chart.js core only)
    const overboughtLine = labels.map(() => 70);
    const oversoldLine = labels.map(() => 30);

    this.rsiChart = new Chart(this.rsiCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'RSI (14)',
            data: values,
            borderColor: '#a78bfa',
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.1
          },
          {
            label: 'Overbought (70)',
            data: overboughtLine,
            borderColor: 'rgba(248, 113, 113, 0.5)',
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Oversold (30)',
            data: oversoldLine,
            borderColor: 'rgba(74, 222, 128, 0.5)',
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          ...this.baseAxisOptions(),
          y: {
            min: 0,
            max: 100,
            ticks: { color: '#6b7280', stepSize: 25 },
            grid: { color: '#1a1f2b' },
            border: { color: '#1f2530' }
          }
        },
        plugins: {
          legend: {
            display: true,
            labels: { color: '#9ca3af', boxWidth: 10, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: '#12161f',
            borderColor: '#262b38',
            borderWidth: 1,
            titleColor: '#e5e7eb',
            bodyColor: '#e5e7eb'
          }
        }
      }
    });
  }
}