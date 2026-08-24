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

export interface BacktestResult {
  ticker: string;
  strategy: string;
  metrics: {
    total_return: number;
    cagr: number;
    sharpe_ratio: number;
    max_drawdown: number;
    final_value: number;
  };
  completed_trades: number;
  trade_log: Trade[];
  portfolio_series: PortfolioPoint[];
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

  getStrategies(): Observable<{ strategies: string[] }> {
    return this.http.get<{ strategies: string[] }>(`${this.baseUrl}/strategies`);
  }

  runBacktest(ticker: string, strategy: string, startDate?: string, endDate?: string): Observable<BacktestResult> {
    const body: any = { ticker, strategy };
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;
    return this.http.post<BacktestResult>(`${this.baseUrl}/backtest`, body);
  }
}