import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, DollarSign, PieChart, ShieldAlert, 
  RefreshCw, PlusCircle, CheckCircle2, Clock, AlertTriangle, 
  ExternalLink, FileText, ArrowUpRight, ArrowDownRight, Activity,
  Brain, Cpu, Download, Upload, Database, Sparkles, FileSpreadsheet, Check
} from 'lucide-react';

export default function App() {
  const [navSummary, setNavSummary] = useState(null);
  const [navHistory, setNavHistory] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [orders, setOrders] = useState([]);
  const [reports, setReports] = useState([]);
  const [activeTab, setActiveTab] = useState('portfolio');
  const [loading, setLoading] = useState(true);

  // Machine Learning Lab State
  const [mlModelInfo, setMlModelInfo] = useState(null);
  const [mlRankings, setMlRankings] = useState([]);
  const [mlExtracting, setMlExtracting] = useState(false);
  const [mlUploading, setMlUploading] = useState(false);
  const fileInputRef = useRef(null);

  // Modals
  const [showFillModal, setShowFillModal] = useState(false);
  const [selectedReportUrl, setSelectedReportUrl] = useState(null);

  // Form state
  const [fillForm, setFillForm] = useState({
    ticker: 'HPG',
    action: 'BUY',
    volume: 1000,
    price: 28.5,
    trade_date: new Date().toISOString().split('T')[0],
    notes: 'Nhập từ Web Dashboard'
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      const [navRes, histRes, pfRes, ordRes, repRes, mlInfoRes, mlRankRes] = await Promise.all([
        fetch('/api/nav/summary').then(r => r.json()),
        fetch('/api/nav/history').then(r => r.json()),
        fetch('/api/portfolio').then(r => r.json()),
        fetch('/api/orders').then(r => r.json()),
        fetch('/api/reports').then(r => r.json()),
        fetch('/api/ml/model/info').then(r => r.json()).catch(() => null),
        fetch('/api/ml/rankings?top_n=10').then(r => r.json()).catch(() => ({ rankings: [] }))
      ]);

      setNavSummary(navRes);
      setNavHistory(histRes);
      setPortfolio(pfRes);
      setOrders(ordRes);
      setReports(repRes);
      if (mlInfoRes) setMlModelInfo(mlInfoRes);
      if (mlRankRes) setMlRankings(mlRankRes.rankings || []);
    } catch (err) {
      console.error('Lỗi tải dữ liệu API:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMlData = async () => {
    try {
      const [infoRes, rankRes] = await Promise.all([
        fetch('/api/ml/model/info').then(r => r.json()),
        fetch('/api/ml/rankings?top_n=10').then(r => r.json())
      ]);
      setMlModelInfo(infoRes);
      setMlRankings(rankRes.rankings || []);
    } catch (err) {
      console.error('Lỗi tải dữ liệu ML:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleExtractFeatures = async () => {
    try {
      setMlExtracting(true);
      const res = await fetch('/api/ml/extract', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ ${data.message}\nTổng số mẫu: ${Number(data.total_samples).toLocaleString()} (Thắng: ${data.pos_pct}%)\nTệp CSV đã sẵn sàng để tải về!`);
        fetchMlData();
      } else {
        alert('Lỗi trích xuất: ' + data.detail);
      }
    } catch (err) {
      alert('Lỗi: ' + err);
    } finally {
      setMlExtracting(false);
    }
  };

  const handleModelUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.joblib')) {
      alert('⚠️ Vui lòng chỉ chọn tệp mô hình có định dạng .joblib');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setMlUploading(true);
      const res = await fetch('/api/ml/model/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        alert(`🎉 ${data.message}\nLần cuối huấn luyện: ${data.trained_at}\nThuật toán: ${data.algorithm}`);
        fetchMlData();
      } else {
        alert('Lỗi tải lên: ' + data.detail);
      }
    } catch (err) {
      alert('Lỗi kết nối: ' + err);
    } finally {
      setMlUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCloseNav = async () => {
    if (!confirm('Bạn có chắc chắn muốn chốt sổ NAV ngày hôm nay theo giá thị trường mới nhất?')) return;
    try {
      const res = await fetch('/api/nav/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: 'Chốt sổ EOD từ Web Dashboard' })
      });
      const data = await res.json();
      alert(`✅ Đã chốt sổ NAV thành công!\nTổng NAV: ${Number(data.nav_report.total_nav).toLocaleString()} VND`);
      fetchData();
    } catch (err) {
      alert('Lỗi chốt sổ: ' + err);
    }
  };

  const handleFillSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/orders/fill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: fillForm.ticker,
          action: fillForm.action,
          volume: Number(fillForm.volume),
          price: Number(fillForm.price),
          trade_date: fillForm.trade_date,
          notes: fillForm.notes
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ Đã ghi nhận lệnh khớp: ${data.order_id}`);
        setShowFillModal(false);
        fetchData();
      } else {
        alert('Lỗi: ' + data.detail);
      }
    } catch (err) {
      alert('Lỗi gửi lệnh: ' + err);
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* 1. TOP NAVBAR */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-30 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <TrendingUp className="w-6 h-6 text-slate-950 font-bold" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">AI Personal Investment Fund</h1>
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                ACTIVE
              </span>
            </div>
            <p className="text-xs text-slate-400">Hệ thống Quỹ Đầu tư Đa Tác tử • Zero-Token Reporting Engine</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button 
            onClick={() => setShowFillModal(true)}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition shadow-md shadow-emerald-600/20 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nhập Lệnh Khớp</span>
          </button>

          <button 
            onClick={handleCloseNav}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition cursor-pointer"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Chốt Sổ NAV Ngày</span>
          </button>

          <button 
            onClick={fetchData}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
            title="Làm mới dữ liệu"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* 2. MAIN CONTENT AREA */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        
        {/* STATS OVERVIEW CARDS */}
        {navSummary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            
            {/* Card 1: Total NAV */}
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-sm relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
                <span>Tổng Tài Sản Ròng (NAV)</span>
                <DollarSign className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold tracking-tight text-white">
                {formatVND(navSummary.total_nav)}
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                <span>Ngày chốt: <strong className="text-slate-300">{navSummary.trade_date}</strong></span>
                <span className="text-emerald-400 font-medium">NAV/Share: 10,000 đ</span>
              </div>
            </div>

            {/* Card 2: Cash & Stock Value */}
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-sm">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
                <span>Cơ Cấu Tiền Mặt / Cổ Phiếu</span>
                <PieChart className="w-4 h-4 text-teal-400" />
              </div>
              <div className="flex items-baseline space-x-2">
                <span className="text-xl font-bold text-white">{formatVND(navSummary.cash_balance)}</span>
                <span className="text-xs text-slate-400">Tiền mặt</span>
              </div>
              <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden flex">
                <div 
                  className="bg-teal-500 h-full transition-all duration-500" 
                  style={{ width: `${(navSummary.cash_balance / (navSummary.total_nav || 1)) * 100}%` }}
                  title="Tiền mặt"
                ></div>
                <div 
                  className="bg-emerald-500 h-full transition-all duration-500" 
                  style={{ width: `${(navSummary.stock_value / (navSummary.total_nav || 1)) * 100}%` }}
                  title="Cổ phiếu"
                ></div>
              </div>
              <div className="mt-2 flex justify-between text-[11px] text-slate-400">
                <span className="text-teal-400">Tiền: {((navSummary.cash_balance / (navSummary.total_nav || 1)) * 100).toFixed(1)}%</span>
                <span className="text-emerald-400">Cổ: {((navSummary.stock_value / (navSummary.total_nav || 1)) * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Card 3: Daily PnL */}
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-sm">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
                <span>Biến Động Trong Ngày</span>
                {navSummary.daily_pnl >= 0 ? (
                  <ArrowUpRight className="w-4 h-4 text-emerald-400" />
                ) : (
                  <ArrowDownRight className="w-4 h-4 text-rose-400" />
                )}
              </div>
              <div className={`text-2xl font-bold tracking-tight ${navSummary.daily_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {navSummary.daily_pnl >= 0 ? '+' : ''}{formatVND(navSummary.daily_pnl)}
              </div>
              <div className="mt-3 flex items-center text-xs font-medium">
                <span className={`px-2 py-0.5 rounded-full ${navSummary.daily_pnl >= 0 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                  {navSummary.daily_pnl >= 0 ? '+' : ''}{Number(navSummary.daily_pnl_pct || 0).toFixed(2)}% hôm nay
                </span>
              </div>
            </div>

            {/* Card 4: Cumulative Return */}
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-sm">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
                <span>Lợi Nhuận Lũy Kế (All-Time)</span>
                <Activity className="w-4 h-4 text-emerald-400" />
              </div>
              <div className={`text-2xl font-bold tracking-tight ${navSummary.cumulative_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {navSummary.cumulative_pnl >= 0 ? '+' : ''}{formatVND(navSummary.cumulative_pnl)}
              </div>
              <div className="mt-3 text-xs text-slate-400">
                Lợi nhuận tạm tính: <strong className="text-white">{formatVND(navSummary.unrealized_pnl)}</strong>
              </div>
            </div>

          </div>
        )}

        {/* NAVIGATION TABS */}
        <div className="flex space-x-1 border-b border-slate-800">
          <button
            onClick={() => setActiveTab('portfolio')}
            className={`px-4 py-2.5 text-sm font-medium transition cursor-pointer border-b-2 flex items-center space-x-2 ${
              activeTab === 'portfolio' 
                ? 'border-emerald-500 text-emerald-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <PieChart className="w-4 h-4" />
            <span>Danh Mục & Sổ Lệnh</span>
          </button>

          <button
            onClick={() => setActiveTab('chart')}
            className={`px-4 py-2.5 text-sm font-medium transition cursor-pointer border-b-2 flex items-center space-x-2 ${
              activeTab === 'chart' 
                ? 'border-emerald-500 text-emerald-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span>Biểu Đồ Đường Cong Vốn (NAV)</span>
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`px-4 py-2.5 text-sm font-medium transition cursor-pointer border-b-2 flex items-center space-x-2 ${
              activeTab === 'reports' 
                ? 'border-emerald-500 text-emerald-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Phòng Lab Chiến Lược (vn-backtest)</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">
              {reports.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('ml')}
            className={`px-4 py-2.5 text-sm font-medium transition cursor-pointer border-b-2 flex items-center space-x-2 ${
              activeTab === 'ml' 
                ? 'border-purple-500 text-purple-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Brain className="w-4 h-4 text-purple-400" />
            <span>Machine Learning Lab</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-purple-500/20 text-purple-300 font-mono">
              AI Alpha
            </span>
          </button>
        </div>

        {/* TAB 1: PORTFOLIO & ORDERS */}
        {activeTab === 'portfolio' && (
          <div className="space-y-6">
            
            {/* 1.1 Holdings Table */}
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white">Vị Thế Đang Nắm Giữ (Holdings)</h2>
                  <p className="text-xs text-slate-400">Danh mục tài sản thực tế theo giá đóng cửa</p>
                </div>
                <span className="text-xs font-mono text-slate-400">{portfolio.length} mã cổ phiếu</span>
              </div>

              {portfolio.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">
                  📭 Danh mục đang giữ 100% Tiền mặt. Chưa có vị thế cổ phiếu nào mở.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950/50 text-slate-400 text-xs uppercase font-semibold border-b border-slate-800">
                      <tr>
                        <th className="px-6 py-3.5">Mã CP</th>
                        <th className="px-6 py-3.5">Khối lượng</th>
                        <th className="px-6 py-3.5">Giá vốn</th>
                        <th className="px-6 py-3.5">Thị giá</th>
                        <th className="px-6 py-3.5">Giá trị thị trường</th>
                        <th className="px-6 py-3.5">Lãi / Lỗ</th>
                        <th className="px-6 py-3.5">Tỷ trọng NAV</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {portfolio.map((item) => (
                        <tr key={item.ticker} className="hover:bg-slate-800/30 transition">
                          <td className="px-6 py-4 font-bold text-emerald-400 flex items-center space-x-2">
                            <span>{item.ticker}</span>
                          </td>
                          <td className="px-6 py-4 font-mono">{Number(item.quantity).toLocaleString()}</td>
                          <td className="px-6 py-4 font-mono">{Number(item.avg_buy_price).toFixed(2)}</td>
                          <td className="px-6 py-4 font-mono text-white font-medium">{Number(item.current_price).toFixed(2)}</td>
                          <td className="px-6 py-4 font-mono font-medium">{formatVND(item.market_value)}</td>
                          <td className="px-6 py-4">
                            <span className={`font-mono font-semibold ${item.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {item.unrealized_pnl >= 0 ? '+' : ''}{Number(item.unrealized_pnl_pct).toFixed(2)}%
                            </span>
                            <div className="text-[11px] text-slate-400">
                              {item.unrealized_pnl >= 0 ? '+' : ''}{formatVND(item.unrealized_pnl)}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center space-x-2">
                              <span className="font-mono text-xs">{Number(item.weight_pct || 0).toFixed(1)}%</span>
                              <div className="w-16 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                <div className="bg-emerald-500 h-full" style={{ width: `${Math.min(100, item.weight_pct || 0)}%` }}></div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 1.2 Recent Orders Table */}
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white">Sổ Lệnh & Trạng Thái Khớp (Order Book)</h2>
                  <p className="text-xs text-slate-400">Lịch sử các đề xuất và xác nhận khớp thực tế</p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-950/50 text-slate-400 text-xs uppercase font-semibold border-b border-slate-800">
                    <tr>
                      <th className="px-6 py-3.5">Mã Lệnh</th>
                      <th className="px-6 py-3.5">Lệnh</th>
                      <th className="px-6 py-3.5">Đề Xuất (AI)</th>
                      <th className="px-6 py-3.5">Khớp Thực Tế</th>
                      <th className="px-6 py-3.5">Trượt Giá</th>
                      <th className="px-6 py-3.5">Trạng Thái</th>
                      <th className="px-6 py-3.5">Thời Gian</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                    {orders.map((ord) => (
                      <tr key={ord.order_id} className="hover:bg-slate-800/30 transition">
                        <td className="px-6 py-3.5 text-slate-400">{ord.order_id}</td>
                        <td className="px-6 py-3.5">
                          <span className={`px-2 py-0.5 rounded font-bold ${ord.action === 'BUY' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                            {ord.action} {ord.ticker}
                          </span>
                        </td>
                        <td className="px-6 py-3.5">
                          {Number(ord.proposed_volume).toLocaleString()} CP @ {Number(ord.proposed_price).toFixed(2)}
                        </td>
                        <td className="px-6 py-3.5 font-semibold text-white">
                          {ord.executed_volume ? `${Number(ord.executed_volume).toLocaleString()} CP @ ${Number(ord.executed_price).toFixed(2)}` : '—'}
                        </td>
                        <td className="px-6 py-3.5">
                          {ord.slippage_pct ? (
                            <span className={ord.slippage_pct > 0 ? 'text-rose-400' : 'text-emerald-400'}>
                              {ord.slippage_pct > 0 ? '+' : ''}{Number(ord.slippage_pct).toFixed(2)}%
                            </span>
                          ) : '0.00%'}
                        </td>
                        <td className="px-6 py-3.5">
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                            ord.status === 'FILLED' ? 'bg-emerald-500/20 text-emerald-300' :
                            ord.status === 'PROPOSED' ? 'bg-amber-500/20 text-amber-300' :
                            ord.status === 'SUBMITTED' ? 'bg-sky-500/20 text-sky-300' :
                            'bg-slate-800 text-slate-400'
                          }`}>
                            {ord.status}
                          </span>
                        </td>
                        <td className="px-6 py-3.5 text-slate-400">{ord.trade_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

        {/* TAB 2: NAV GROWTH CURVE */}
        {activeTab === 'chart' && (
          <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">Đường Cong Vốn Của Quỹ (Equity Curve)</h2>
                <p className="text-xs text-slate-400">Theo dõi sự tăng trưởng của NAV theo thời gian (0 Token)</p>
              </div>
              <span className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 font-mono">
                Số mốc dữ liệu: {navHistory.length}
              </span>
            </div>

            {/* Simple Elegant SVG Equity Chart */}
            <div className="h-64 w-full bg-slate-950/60 rounded-xl border border-slate-800/80 p-4 flex flex-col justify-between">
              {navHistory.length <= 1 ? (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                  ℹ️ Đang tích lũy chuỗi dữ liệu giao dịch hàng ngày để dựng đồ thị đường cong vốn.
                </div>
              ) : (
                <div className="w-full h-full flex items-end space-x-2">
                  {navHistory.map((pt, idx) => {
                    const minNav = Math.min(...navHistory.map(h => h.total_nav));
                    const maxNav = Math.max(...navHistory.map(h => h.total_nav));
                    const heightPct = maxNav === minNav ? 50 : Math.max(10, ((pt.total_nav - minNav) / (maxNav - minNav)) * 100);
                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
                        <div 
                          className="w-full bg-emerald-500/60 group-hover:bg-emerald-400 transition-all rounded-t-sm"
                          style={{ height: `${heightPct}%` }}
                        ></div>
                        {/* Tooltip on hover */}
                        <div className="absolute -top-12 bg-slate-900 border border-slate-700 text-white text-[10px] px-2 py-1 rounded shadow-lg opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap z-20">
                          <div>{pt.trade_date}</div>
                          <div className="font-bold text-emerald-400">{formatVND(pt.total_nav)}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">Vốn Khởi Lập</div>
                <div className="text-lg font-bold text-white mt-1">1,000,000,000 đ</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">NAV Hiện Tại</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{formatVND(navSummary?.total_nav)}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">Tỷ Suất Sinh Lời</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">
                  +{(((navSummary?.total_nav - 1_000_000_000) / 1_000_000_000) * 100).toFixed(3)}%
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: STRATEGY LAB & BACKTEST REPORTS */}
        {activeTab === 'reports' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">Thư Viện Chiến Lược Định Lượng (vn-backtest)</h2>
                <p className="text-xs text-slate-400">Các chiến lược được Hội đồng Rủi ro (CRO) thẩm định trên dữ liệu 5 năm</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {reports.map((rep, idx) => (
                <div key={idx} className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-bold text-white">{rep.title}</h3>
                      <p className="text-xs font-mono text-slate-400 mt-0.5">Mã: {rep.tickers.join(', ')}</p>
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                      rep.cro_status.includes('APPROVED')
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}>
                      {rep.cro_status}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/50">
                    "{rep.verdict}"
                  </p>

                  <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                    <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">CAGR</div>
                      <div className="font-bold text-white mt-0.5">{rep.cagr_pct ? rep.cagr_pct.toFixed(2) : 0}%/năm</div>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">Sharpe</div>
                      <div className={`font-bold mt-0.5 ${rep.sharpe >= 1.2 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {rep.sharpe ? rep.sharpe.toFixed(2) : 0}
                      </div>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">Max DD</div>
                      <div className="font-bold text-rose-400 mt-0.5">-{rep.mdd_pct ? rep.mdd_pct.toFixed(2) : 0}%</div>
                    </div>
                  </div>

                  <div className="pt-2 flex space-x-3">
                    <button
                      onClick={() => setSelectedReportUrl(rep.html_url)}
                      className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-white transition flex items-center justify-center space-x-1.5 cursor-pointer"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Xem Biểu Đồ Plotly Chi Tiết</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: MACHINE LEARNING LAB */}
        {activeTab === 'ml' && (
          <div className="space-y-6">
            
            {/* 4.1 Model Overview & Last Trained Status Banner */}
            <div className="p-6 rounded-2xl bg-gradient-to-r from-purple-950/40 via-slate-900/80 to-slate-900 border border-purple-500/30 shadow-xl relative overflow-hidden">
              <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>
              
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start space-x-4">
                  <div className="w-12 h-12 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0 shadow-lg shadow-purple-500/10">
                    <Brain className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h2 className="text-lg font-bold text-white">Universal Quant Alpha Model</h2>
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30">
                        {mlModelInfo?.algorithm || 'LightGBM Classifier'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Bộ não chấm điểm xác suất thắng độc lập 100% với chiến lược • Đánh giá rủi ro Triple-Barrier
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <Clock className="w-5 h-5 text-purple-400 shrink-0" />
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Lần Cuối Huấn Luyện (Trained At)</div>
                    <div className="text-sm font-bold text-white font-mono">
                      {mlModelInfo?.trained_at || 'Chưa huấn luyện'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Metric stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-4 border-t border-slate-800/80">
                <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">ROC-AUC Test</span>
                  <div className="text-lg font-bold text-purple-400 mt-0.5 font-mono">
                    {mlModelInfo?.metrics?.test_auc ? (mlModelInfo.metrics.test_auc * 100).toFixed(1) + '%' : '51.6%'}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Tập Dữ Liệu Parquet</span>
                  <div className="text-lg font-bold text-white mt-0.5 font-mono">
                    {mlModelInfo?.dataset?.sample_count ? mlModelInfo.dataset.sample_count.toLocaleString() + ' nến' : '11,860 nến'}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Số Cây Quyết Định</span>
                  <div className="text-lg font-bold text-emerald-400 mt-0.5 font-mono">
                    {mlModelInfo?.metrics?.best_iteration || 25} trees
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Trạng Thái Model</span>
                  <div className="text-xs font-bold text-emerald-400 mt-1 flex items-center space-x-1">
                    <Check className="w-3.5 h-3.5" />
                    <span>SẴN SÀNG (PRODUCTION)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 4.2 Interactive Action Control Grid (3 Buttons) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              
              {/* ACTION 1: TRÍCH XUẤT 15 ĐẶC TRƯNG & GÁN NHÃN */}
              <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between space-y-4 hover:border-slate-700 transition">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-3">
                    <Database className="w-5 h-5" />
                  </div>
                  <h3 className="text-sm font-bold text-white">1. Trích Xuất 15 Đặc Trưng</h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                    Tính toán 15 chỉ số kỹ thuật, dòng tiền và áp dụng nhãn Triple-Barrier (+5% TP, -3% SL trong 5 phiên) từ kho dữ liệu Parquet 5 năm.
                  </p>
                </div>

                <button
                  onClick={handleExtractFeatures}
                  disabled={mlExtracting}
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 text-emerald-400 ${mlExtracting ? 'animate-spin' : ''}`} />
                  <span>{mlExtracting ? 'Đang trích xuất...' : 'Trích Xuất 15 Đặc Trưng'}</span>
                </button>
              </div>

              {/* ACTION 2: TẢI TỆP CSV VỀ MÁY */}
              <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between space-y-4 hover:border-slate-700 transition">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3">
                    <Download className="w-5 h-5" />
                  </div>
                  <h3 className="text-sm font-bold text-white">2. Tải Tệp CSV Huấn Luyện</h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                    Tải tệp <code className="text-blue-300 font-mono">ml_dataset_train.csv</code> về máy tính ({mlModelInfo?.dataset?.csv_size_mb || 4.97} MB) để tải lên Kaggle / Google Colab GPU miễn phí.
                  </p>
                </div>

                <a
                  href="/api/ml/dataset/download"
                  download="ml_dataset_train.csv"
                  className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition flex items-center justify-center space-x-2 cursor-pointer shadow-md shadow-blue-600/20"
                >
                  <Download className="w-4 h-4" />
                  <span>Tải Tệp CSV Về Máy</span>
                </a>
              </div>

              {/* ACTION 3: UPLOAD MODEL .JOBLIB TỪ KAGGLE */}
              <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between space-y-4 hover:border-slate-700 transition">
                <div>
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-3">
                    <Upload className="w-5 h-5" />
                  </div>
                  <h3 className="text-sm font-bold text-white">3. Tải Lên Model (.joblib)</h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                    Sau khi huấn luyện xong trên Kaggle, tải tệp <code className="text-purple-300 font-mono">universal_alpha_model.joblib</code> lên đây để hệ thống tự động cập nhật ngay lập tức.
                  </p>
                </div>

                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleModelUpload} 
                  accept=".joblib" 
                  className="hidden" 
                />

                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={mlUploading}
                  className="w-full py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition flex items-center justify-center space-x-2 cursor-pointer shadow-md shadow-purple-600/20 disabled:opacity-50"
                >
                  <Upload className={`w-4 h-4 ${mlUploading ? 'animate-bounce' : ''}`} />
                  <span>{mlUploading ? 'Đang nạp mô hình...' : 'Tải Lên File .joblib'}</span>
                </button>
              </div>

            </div>

            {/* 4.3 Live Market ML Alpha Rankings Table */}
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <div>
                    <h2 className="text-base font-bold text-white">Bảng Xếp Hạng Alpha Score Thị Trường (Live Market Rankings)</h2>
                    <p className="text-xs text-slate-400">Dự báo xác suất thắng (0.00 đến 1.00) cho phiên giao dịch gần nhất</p>
                  </div>
                </div>
                <button
                  onClick={fetchMlData}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition flex items-center space-x-1.5 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-purple-400" />
                  <span>Làm mới điểm số</span>
                </button>
              </div>

              {mlRankings.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">
                  Chưa có dữ liệu xếp hạng. Vui lòng bấm Làm mới điểm số.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950/50 text-slate-400 text-xs uppercase font-semibold border-b border-slate-800">
                      <tr>
                        <th className="px-6 py-3.5">Hạng</th>
                        <th className="px-6 py-3.5">Mã CP</th>
                        <th className="px-6 py-3.5">Thị Giá</th>
                        <th className="px-6 py-3.5">Xác Suất Thắng (ML Score)</th>
                        <th className="px-6 py-3.5">Đánh Giá Phân Hạng</th>
                        <th className="px-6 py-3.5">Vol / SMA20</th>
                        <th className="px-6 py-3.5">RSI (14)</th>
                        <th className="px-6 py-3.5">Lãi 5 Phiên</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {mlRankings.map((item, idx) => {
                        let scoreColor = 'text-rose-400';
                        let barBg = 'bg-rose-500';
                        if (item.ml_score >= 0.65) {
                          scoreColor = 'text-emerald-400';
                          barBg = 'bg-emerald-500';
                        } else if (item.ml_score >= 0.55) {
                          scoreColor = 'text-amber-400';
                          barBg = 'bg-amber-500';
                        } else if (item.ml_score >= 0.45) {
                          scoreColor = 'text-blue-400';
                          barBg = 'bg-blue-500';
                        }

                        return (
                          <tr key={item.ticker} className="hover:bg-slate-800/30 transition">
                            <td className="px-6 py-3.5 font-bold text-slate-400">#{idx + 1}</td>
                            <td className="px-6 py-3.5 font-bold text-white text-base">{item.ticker}</td>
                            <td className="px-6 py-3.5 text-slate-200">{Number(item.price).toFixed(2)}</td>
                            <td className="px-6 py-3.5">
                              <div className="flex items-center space-x-3">
                                <span className={`font-bold ${scoreColor}`}>
                                  {(item.ml_score * 100).toFixed(2)}%
                                </span>
                                <div className="w-20 bg-slate-800 h-2 rounded-full overflow-hidden">
                                  <div className={`${barBg} h-full`} style={{ width: `${Math.min(100, item.ml_score * 100)}%` }}></div>
                                </div>
                              </div>
                            </td>
                            <td className="px-6 py-3.5 font-sans text-xs">
                              <span className={`px-2 py-0.5 rounded-full font-medium ${
                                item.rating === 'STRONG_BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                                item.rating === 'ACCUMULATE' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                                item.rating === 'NEUTRAL' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                                'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {item.label}
                              </span>
                            </td>
                            <td className="px-6 py-3.5 text-slate-300">{item.vol_ratio_20}x</td>
                            <td className="px-6 py-3.5 text-slate-300">{item.rsi_14}</td>
                            <td className="px-6 py-3.5">
                              <span className={item.ret_5d_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                                {item.ret_5d_pct >= 0 ? '+' : ''}{item.ret_5d_pct}%
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 4.4 Quick Guide Card */}
            <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 space-y-2">
              <div className="font-bold text-slate-200 flex items-center space-x-1.5 text-sm">
                <span>💡 Hướng dẫn Quy trình Huấn Luyện Không Cần Chạm Code:</span>
              </div>
              <p>1. Bấm nút <strong>"Trích Xuất 15 Đặc Trưng"</strong> ở trên ➔ Bấm <strong>"Tải Tệp CSV Về Máy"</strong>.</p>
              <p>2. Mở Kaggle / Google Colab (GPU miễn phí), import notebook <code className="text-purple-300 font-mono">notebooks/kaggle_train_lightgbm.ipynb</code> và bấm <strong>Run All</strong>.</p>
              <p>3. Tải tệp <code className="text-purple-300 font-mono">universal_alpha_model.joblib</code> từ Kaggle về máy ➔ Bấm nút <strong>"Tải Lên File .joblib"</strong> ở Thẻ 3 phía trên để cập nhật hệ thống ngay lập tức.</p>
            </div>

          </div>
        )}

      </main>

      {/* MODAL 1: NHẬP LỆNH KHỚP THỰC TẾ (/fill) */}
      {showFillModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">Ghi Nhận Lệnh Khớp Thực Tế</h3>
              <button 
                onClick={() => setShowFillModal(false)}
                className="text-slate-400 hover:text-white cursor-pointer"
              >✕</button>
            </div>

            <form onSubmit={handleFillSubmit} className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Mã Cổ Phiếu</label>
                  <input
                    type="text"
                    value={fillForm.ticker}
                    onChange={e => setFillForm({...fillForm, ticker: e.target.value.toUpperCase()})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono uppercase focus:border-emerald-500 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Hành Động</label>
                  <select
                    value={fillForm.action}
                    onChange={e => setFillForm({...fillForm, action: e.target.value})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
                  >
                    <option value="BUY">MUA (BUY)</option>
                    <option value="SELL">BÁN (SELL)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Khối Lượng Khớp</label>
                  <input
                    type="number"
                    step="100"
                    value={fillForm.volume}
                    onChange={e => setFillForm({...fillForm, volume: e.target.value})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Giá Khớp Thực Tế</label>
                  <input
                    type="number"
                    step="0.05"
                    value={fillForm.price}
                    onChange={e => setFillForm({...fillForm, price: e.target.value})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Ngày Giao Dịch</label>
                <input
                  type="date"
                  value={fillForm.trade_date}
                  onChange={e => setFillForm({...fillForm, trade_date: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div className="pt-3 flex space-x-3">
                <button
                  type="button"
                  onClick={() => setShowFillModal(false)}
                  className="flex-1 py-2 px-4 rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition cursor-pointer"
                >Hủy</button>
                <button
                  type="submit"
                  className="flex-1 py-2 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition cursor-pointer shadow-lg shadow-emerald-600/20"
                >Ghi Nhận Khớp</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: XEM BIỂU ĐỒ PLOTLY VN-BACKTEST */}
      {selectedReportUrl && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-5xl w-full h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Báo Cáo Tương Tác vn-backtest (Plotly)</span>
              </h3>
              <button 
                onClick={() => setSelectedReportUrl(null)}
                className="text-slate-400 hover:text-white cursor-pointer px-2 py-1 text-sm rounded bg-slate-800"
              >Đóng ✕</button>
            </div>
            <div className="flex-1 bg-white">
              <iframe 
                src={selectedReportUrl} 
                title="vn-backtest report" 
                className="w-full h-full border-none"
              />
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
