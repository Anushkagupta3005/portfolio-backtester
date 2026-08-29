import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Trade {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  shares: number;
  pnl: number;
  pnl_pct: number;
}

export interface PortfolioPoint {
  date: string;
  value: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface PricePoint {
  date: string;
  price: number;
  signal: 'BUY' | 'SELL' | 'HOLD';
}

export interface RsiPoint {
  date: string;
  rsi: number;
}

export interface BacktestResult {
  ticker: string;
  strategy: string;
  metrics: {
    total_return: number;
    cagr: number;
    sharpe_ratio: number;
    max_drawdown: number;
    volatility: number;
    final_value: number;
  };
  completed_trades: number;
  trade_log: Trade[];
  portfolio_series: PortfolioPoint[];
  drawdown_series: DrawdownPoint[];
  price_series: PricePoint[];
  rsi_series: RsiPoint[];
}

export interface CompareResultEntry extends BacktestResult {
  error?: string;
}

export interface CompareResult {
  ticker: string;
  // keyed by strategy name ("SMA", "RSI", "Buy & Hold"); a value may
  // carry only an `error` field if that strategy couldn't run for the
  // given range (e.g. RSI's warm-up period longer than the range)
  results: Record<string, CompareResultEntry>;
  // strategy names ranked best-to-worst by total_return; strategies
  // that errored are omitted from ranking but still present in `results`
  ranking: string[];
}

export interface HistoryRun {
  id: number;
  ticker: string;
  strategy: string;
  start_date: string | null;
  end_date: string | null;
  total_return: number;
  cagr: number;
  sharpe_ratio: number;
  max_drawdown: number;
  final_value: number;
  note: string | null;
  created_at: string;
}

export interface SaveHistoryPayload {
  ticker: string;
  strategy: string;
  start_date?: string;
  end_date?: string;
  total_return: number;
  cagr: number;
  sharpe_ratio: number;
  max_drawdown: number;
  final_value: number;
  note?: string;
}

export interface AddTickerResult {
  ticker: string;
  rows_loaded: number;
  start_date: string;
  end_date: string;
  added: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class BacktestService {
  private baseUrl = 'http://localhost:5001/api';

  constructor(private http: HttpClient) {}

  getTickers(): Observable<{ tickers: string[] }> {
    return this.http.get<{ tickers: string[] }>(`${this.baseUrl}/tickers`);
  }

  addTicker(ticker: string, startDate?: string, endDate?: string): Observable<AddTickerResult> {
    const body: any = { ticker };
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;
    return this.http.post<AddTickerResult>(`${this.baseUrl}/tickers`, body);
  }

  getStrategies(): Observable<{ strategies: string[] }> {
    return this.http.get<{ strategies: string[] }>(`${this.baseUrl}/strategies`);
  }

  runBacktest(ticker: string, strategy: string, startDate?: string, endDate?: string): Observable<BacktestResult> {
    const body: any = { ticker, strategy };
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;
    return this.http.post<BacktestResult>(`${this.baseUrl}/backtest`, body);
  }

  compareStrategies(ticker: string, startDate?: string, endDate?: string): Observable<CompareResult> {
    const body: any = { ticker };
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;
    return this.http.post<CompareResult>(`${this.baseUrl}/compare`, body);
  }

  getHistory(): Observable<{ runs: HistoryRun[] }> {
    return this.http.get<{ runs: HistoryRun[] }>(`${this.baseUrl}/history`);
  }

  saveToHistory(payload: SaveHistoryPayload): Observable<{ id: number; saved: boolean }> {
    return this.http.post<{ id: number; saved: boolean }>(`${this.baseUrl}/history`, payload);
  }

  updateHistoryNote(id: number, note: string): Observable<{ id: number; updated: boolean }> {
    return this.http.patch<{ id: number; updated: boolean }>(`${this.baseUrl}/history/${id}`, { note });
  }

  deleteHistoryRun(id: number): Observable<{ id: number; deleted: boolean }> {
    return this.http.delete<{ id: number; deleted: boolean }>(`${this.baseUrl}/history/${id}`);
  }
}