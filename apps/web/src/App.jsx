import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, DollarSign, PieChart, ShieldAlert, 
  RefreshCw, PlusCircle, CheckCircle2, Clock, AlertTriangle, 
  ExternalLink, FileText, ArrowUpRight, ArrowDownRight, Activity,
  Brain, Cpu, Download, Upload, Database, Sparkles, FileSpreadsheet, Check,
  Globe, Lock, Award, Users, CheckCircle, XCircle, Send, Gavel, Scale,
  Zap, ShieldCheck
} from 'lucide-react';

export default function App() {
  const [navSummary, setNavSummary] = useState(null);
  const [navHistory, setNavHistory] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState('ALL');
  const [selectedBook, setSelectedBook] = useState('ALL');
  const [orders, setOrders] = useState([]);
  const [reports, setReports] = useState([]);
  const [activeTab, setActiveTab] = useState('portfolio');
  const [loading, setLoading] = useState(true);
  const [capitalSummary, setCapitalSummary] = useState(null);

  // Machine Learning Lab State
  const [mlModelInfo, setMlModelInfo] = useState(null);
  const [mlRankings, setMlRankings] = useState([]);
  const [mlExtracting, setMlExtracting] = useState(false);
  const [mlUploading, setMlUploading] = useState(false);
  const fileInputRef = useRef(null);

  // Live Investment Committee State
  const [committeeMemos, setCommitteeMemos] = useState([]);
  const [agentsTelemetry, setAgentsTelemetry] = useState([]);
  const [latestJevTelemetry, setLatestJevTelemetry] = useState(null);
  const [activeMemo, setActiveMemo] = useState(null);
  const [summonTicker, setSummonTicker] = useState('HPG');
  const [summonBook, setSummonBook] = useState('CORE');
  const [summonLoading, setSummonLoading] = useState(false);
  const [committeeActionLoading, setCommitteeActionLoading] = useState(false);

  // Modals
  const [showFillModal, setShowFillModal] = useState(false);
  const [selectedReportUrl, setSelectedReportUrl] = useState(null);
  const [syncingBq, setSyncingBq] = useState(false);

  // Form state
  const [fillForm, setFillForm] = useState({
    ticker: 'HPG',
    action: 'BUY',
    volume: 1000,
    price: 28.5,
    trade_date: new Date().toISOString().split('T')[0],
    strategy_book: 'QUANT',
    notes: 'Nhập từ Web Dashboard'
  });

  const fetchData = async (acc = selectedAccount) => {
    try {
      setLoading(true);
      const accParam = acc && acc !== 'ALL' ? `?account=${acc}` : '';
      const [navRes, histRes, pfRes, ordRes, repRes, mlInfoRes, mlRankRes, accRes, capRes, commRes] = await Promise.all([
        fetch('/api/nav/summary').then(r => r.json()),
        fetch('/api/nav/history').then(r => r.json()),
        fetch('/api/portfolio' + accParam).then(r => r.json()),
        fetch('/api/orders').then(r => r.json()),
        fetch('/api/reports').then(r => r.json()),
        fetch('/api/ml/model/info').then(r => r.json()).catch(() => null),
        fetch('/api/ml/rankings?top_n=10').then(r => r.json()).catch(() => ({ rankings: [] })),
        fetch('/api/accounts').then(r => r.json()).catch(() => []),
        fetch('/api/capital/summary' + accParam).then(r => r.json()).catch(() => null),
        fetch('/api/committee/memos').then(r => r.json()).catch(() => ({ memos: [], agents: [] }))
      ]);

      setNavSummary(navRes);
      setNavHistory(histRes);
      setPortfolio(pfRes);
      setOrders(ordRes);
      setReports(repRes);
      setAccounts(accRes || []);
      setCapitalSummary(capRes);
      if (mlInfoRes) setMlModelInfo(mlInfoRes);
      if (mlRankRes) setMlRankings(mlRankRes.rankings || []);
      if (commRes) {
        setCommitteeMemos(commRes.memos || []);
        setAgentsTelemetry(commRes.agents || []);
        if (commRes.latest_jev_telemetry) {
          setLatestJevTelemetry(commRes.latest_jev_telemetry);
        }
        if (commRes.memos && commRes.memos.length > 0) {
          setActiveMemo(prev => prev || commRes.memos[0]);
          if (commRes.memos[0].jev_telemetry) {
            setLatestJevTelemetry(commRes.memos[0].jev_telemetry);
          }
        }
      }
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

  const handleSyncBigQuery = async () => {
    if (!confirm('Bạn có muốn đồng bộ giá đóng cửa thực tế mới nhất từ Google BigQuery và cập nhật lại danh mục?')) return;
    setSyncingBq(true);
    try {
      const res = await fetch('/api/nav/sync-bigquery', {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok) {
        const priceList = Object.entries(data.prices || {}).map(([t, p]) => `${t}: ${(p/1000).toFixed(2)}k`).join(' | ');
        alert(`✅ Đã đồng bộ giá thực tế từ BigQuery thành công!\nPhiên: ${data.as_of_date}\n${priceList}\nTổng NAV: ${Number(data.nav_report.total_nav).toLocaleString()} VND`);
        fetchData();
      } else {
        alert('❌ Lỗi đồng bộ: ' + (data.detail || 'Không xác định'));
      }
    } catch (err) {
      alert('Lỗi kết nối: ' + err);
    } finally {
      setSyncingBq(false);
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
          strategy_book: fillForm.strategy_book || 'QUANT',
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

  const handleSummonCommittee = async (e) => {
    if (e) e.preventDefault();
    if (!summonTicker) return;
    try {
      setSummonLoading(true);
      const res = await fetch(`/api/committee/debate/${summonTicker.trim().toUpperCase()}?book=${summonBook}`, {
        method: 'POST'
      }).then(r => r.json());
      if (res.status === 'SUCCESS' && res.memo) {
        setActiveMemo(res.memo);
        if (res.memo.jev_telemetry) setLatestJevTelemetry(res.memo.jev_telemetry);
        await fetchData();
      } else {
        alert(res.detail || 'Không thể triệu tập phiên họp Ủy ban');
      }
    } catch (err) {
      alert('Lỗi kết nối khi triệu tập họp: ' + err.message);
    } finally {
      setSummonLoading(false);
    }
  };

  const handleApproveMemo = async (memoId) => {
    try {
      setCommitteeActionLoading(true);
      const res = await fetch(`/api/committee/memos/${memoId}/approve`, {
        method: 'POST'
      }).then(r => r.json());
      if (res.status === 'SUCCESS') {
        setActiveMemo(prev => prev && prev.memo_id === memoId ? { ...prev, status: 'APPROVED' } : prev);
        await fetchData();
      }
    } catch (err) {
      alert('Lỗi phê duyệt: ' + err.message);
    } finally {
      setCommitteeActionLoading(false);
    }
  };

  const handleRejectMemo = async (memoId) => {
    try {
      setCommitteeActionLoading(true);
      const res = await fetch(`/api/committee/memos/${memoId}/reject`, {
        method: 'POST'
      }).then(r => r.json());
      if (res.status === 'SUCCESS') {
        setActiveMemo(prev => prev && prev.memo_id === memoId ? { ...prev, status: 'REJECTED' } : prev);
        await fetchData();
      }
    } catch (err) {
      alert('Lỗi bác bỏ: ' + err.message);
    } finally {
      setCommitteeActionLoading(false);
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN', { maximumFractionDigits: 0 }) + ' đ';

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
            onClick={handleSyncBigQuery}
            disabled={syncingBq}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-sm font-medium border border-indigo-500/30 transition cursor-pointer disabled:opacity-50"
            title="Đồng bộ giá đóng cửa thực tế mới nhất từ Google BigQuery"
          >
            <Database className={`w-4 h-4 text-indigo-400 ${syncingBq ? 'animate-pulse' : ''}`} />
            <span>{syncingBq ? 'Đang lấy giá...' : 'Đồng Bộ Giá BigQuery'}</span>
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
              <div className="mt-2 text-xs text-slate-400 flex flex-col space-y-0.5">
                <div>Đã chốt (Realized): <strong className="text-emerald-400">+{formatVND(navSummary.realized_pnl)}</strong></div>
                <div>Tạm tính (Unrealized): <strong className="text-rose-400">{formatVND(navSummary.unrealized_pnl)}</strong> <span className="text-[10px] text-slate-500">(FLC: -215.8M)</span></div>
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

          <button
            onClick={() => setActiveTab('committee')}
            className={`px-4 py-2.5 text-sm font-medium transition cursor-pointer border-b-2 flex items-center space-x-2 ${
              activeTab === 'committee' 
                ? 'border-indigo-500 text-indigo-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Ủy Ban Đầu Tư AI (Live Committee)</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-500/20 text-indigo-300 font-mono font-bold">
              {committeeMemos.length > 0 ? committeeMemos.length : 'Live'}
            </span>
          </button>
        </div>

        {/* TAB 1: PORTFOLIO & ORDERS */}
        {activeTab === 'portfolio' && (
          <div className="space-y-6">
            
            {/* 1.1 Holdings Table */}
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-bold text-white">Vị Thế Đang Nắm Giữ (Holdings)</h2>
                  <p className="text-xs text-slate-400">Danh mục tài sản thực tế theo Sổ Core / Quant và 4 tài khoản CTCK</p>
                </div>
                
                <div className="flex flex-wrap items-center gap-2">
                  {/* Strategy Book Filter Pills */}
                  <div className="flex items-center space-x-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800 text-xs">
                    <button
                      onClick={() => setSelectedBook('ALL')}
                      className={`px-2.5 py-1 rounded-lg transition font-medium cursor-pointer ${selectedBook === 'ALL' ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      Tất cả Sổ
                    </button>
                    <button
                      onClick={() => setSelectedBook('CORE')}
                      className={`px-2.5 py-1 rounded-lg transition font-medium cursor-pointer ${selectedBook === 'CORE' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      📘 CORE (Fundamental)
                    </button>
                    <button
                      onClick={() => setSelectedBook('QUANT')}
                      className={`px-2.5 py-1 rounded-lg transition font-medium cursor-pointer ${selectedBook === 'QUANT' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30 font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      ⚡ QUANT (Trading)
                    </button>
                  </div>

                  {/* Account Filter Pills */}
                  <div className="flex items-center space-x-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800 text-xs">
                    <button
                      onClick={() => { setSelectedAccount('ALL'); fetchData('ALL'); }}
                      className={`px-2.5 py-1 rounded-lg transition font-medium ${selectedAccount === 'ALL' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      Tất cả ({portfolio.length})
                    </button>
                    <button
                      onClick={() => { setSelectedAccount('0001716319'); fetchData('0001716319'); }}
                      className={`px-2.5 py-1 rounded-lg transition font-medium ${selectedAccount === '0001716319' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      0001716319
                    </button>
                    <button
                      onClick={() => { setSelectedAccount('009C105992'); fetchData('009C105992'); }}
                      className={`px-2.5 py-1 rounded-lg transition font-medium ${selectedAccount === '009C105992' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      009C105992
                    </button>
                    <button
                      onClick={() => { setSelectedAccount('127008'); fetchData('127008'); }}
                      className={`px-2.5 py-1 rounded-lg transition font-medium ${selectedAccount === '127008' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                      127008
                    </button>
                  </div>
                </div>
              </div>

              {portfolio.filter(p => (selectedAccount === 'ALL' || p.account === selectedAccount) && (selectedBook === 'ALL' || (p.strategy_book || 'QUANT') === selectedBook)).length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">
                  📭 Không có vị thế cổ phiếu nào phù hợp với bộ lọc đã chọn.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950/50 text-slate-400 text-xs uppercase font-semibold border-b border-slate-800">
                      <tr>
                        <th className="px-6 py-3.5">Mã CP</th>
                        <th className="px-6 py-3.5">Sổ</th>
                        <th className="px-6 py-3.5">Tài khoản</th>
                        <th className="px-6 py-3.5">Khối lượng</th>
                        <th className="px-6 py-3.5">Giá vốn</th>
                        <th className="px-6 py-3.5">Thị giá</th>
                        <th className="px-6 py-3.5">Giá trị thị trường</th>
                        <th className="px-6 py-3.5">Lãi / Lỗ</th>
                        <th className="px-6 py-3.5">Tỷ trọng NAV</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {portfolio
                        .filter(p => (selectedAccount === 'ALL' || p.account === selectedAccount) && (selectedBook === 'ALL' || (p.strategy_book || 'QUANT') === selectedBook))
                        .map((item) => (
                        <tr key={`${item.account}-${item.ticker}-${item.strategy_book || 'QUANT'}`} className="hover:bg-slate-800/30 transition">
                          <td className="px-6 py-4 font-bold text-emerald-400 flex items-center space-x-2">
                            <span>{item.ticker}</span>
                            {item.ticker === 'FLC' && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                Treo sàn (0 đ)
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                              item.strategy_book === 'CORE'
                                ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                                : 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                            }`}>
                              {item.strategy_book || 'QUANT'}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800/80 text-slate-300 border border-slate-700/60">
                              {item.account}
                            </span>
                          </td>
                          <td className="px-6 py-4 font-mono">{Number(item.quantity).toLocaleString()}</td>
                          <td className="px-6 py-4 font-mono">{Number(item.avg_buy_price).toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} đ</td>
                          <td className="px-6 py-4 font-mono text-white font-medium">{Number(item.current_price).toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} đ</td>
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
                  <p className="text-xs text-slate-400">Lịch sử các đề xuất và xác nhận khớp thực tế kèm Sổ chiến lược</p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-950/50 text-slate-400 text-xs uppercase font-semibold border-b border-slate-800">
                    <tr>
                      <th className="px-6 py-3.5">Mã Lệnh</th>
                      <th className="px-6 py-3.5">Lệnh</th>
                      <th className="px-6 py-3.5">Sổ</th>
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
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            ord.strategy_book === 'CORE' ? 'bg-blue-500/20 text-blue-300' : 'bg-purple-500/20 text-purple-300'
                          }`}>
                            {ord.strategy_book || 'QUANT'}
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

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-center">
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">Vốn Gốc Đang Đầu Tư</div>
                <div className="text-lg font-bold text-white mt-1">{formatVND(capitalSummary?.active_capital || 0)}</div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Nộp: {formatVND(capitalSummary?.total_deposited)} • Rút: {formatVND(capitalSummary?.total_withdrawn)}
                  {(capitalSummary?.profit_withdrawn || 0) > 0 && (
                    <div className="text-emerald-400 font-medium mt-0.5">Lãi đã rút: +{formatVND(capitalSummary?.profit_withdrawn)}</div>
                  )}
                </div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">NAV Hiện Tại</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{formatVND(capitalSummary?.current_nav || navSummary?.total_nav)}</div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Tiền: {formatVND(capitalSummary?.cash_balance)} • Cổ: {formatVND(capitalSummary?.stock_value)}
                </div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">Lợi Nhuận Toàn Lịch Sử</div>
                <div className={`text-lg font-bold mt-1 ${(capitalSummary?.net_profit || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(capitalSummary?.net_profit || 0) >= 0 ? '+' : ''}{formatVND(capitalSummary?.net_profit || 0)}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  NAV + Lãi đã rút - Vốn gốc đang gửi
                </div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800/60">
                <div className="text-xs text-slate-400 uppercase font-semibold">Tỷ Suất Sinh Lời Thực Tế</div>
                <div className={`text-lg font-bold mt-1 ${(capitalSummary?.return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(capitalSummary?.return_pct || 0) >= 0 ? '+' : ''}{Number(capitalSummary?.return_pct || 0).toFixed(2)}%
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Tính trên vốn gốc đầu tư thực tế
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

        {/* ========================================================= */}
        {/* TAB 5: ỦY BAN ĐẦU TƯ AI (LIVE INVESTMENT COMMITTEE)       */}
        {/* ========================================================= */}
        {activeTab === 'committee' && (
          <div className="space-y-6">
            
            {/* 5.1 HEADER & FAST SUMMON FORM */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 bg-gradient-to-tr from-amber-500/20 to-orange-500/20 border border-amber-500/30 rounded-xl text-amber-400">
                    <Scale className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white flex items-center space-x-2">
                      <span>Ủy Ban Đầu Tư Trực Tuyến</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 animate-pulse">
                        LIVE TELEMETRY
                      </span>
                    </h2>
                    <p className="text-xs text-slate-400">
                      Mô phỏng 6 AI Agents đa nhiệm tranh biện 2 chiều, phản biện bẫy rủi ro và ra phán quyết trước khi CEO duyệt
                    </p>
                  </div>
                </div>
              </div>

              {/* Fast Summon Form */}
              <form onSubmit={handleSummonCommittee} className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <input
                    type="text"
                    value={summonTicker}
                    onChange={e => setSummonTicker(e.target.value.toUpperCase())}
                    placeholder="Mã CP (FPT, HPG...)"
                    className="w-32 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white font-mono uppercase focus:border-amber-500 focus:outline-none"
                    required
                  />
                </div>

                <div className="flex bg-slate-950 border border-slate-800 rounded-xl p-1">
                  <button
                    type="button"
                    onClick={() => setSummonBook('CORE')}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition cursor-pointer ${
                      summonBook === 'CORE' 
                        ? 'bg-blue-600 text-white shadow-sm' 
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    CORE (70%)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSummonBook('QUANT')}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition cursor-pointer ${
                      summonBook === 'QUANT' 
                        ? 'bg-purple-600 text-white shadow-sm' 
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    QUANT (30%)
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={summonLoading}
                  className="px-4 py-2 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-amber-600/20 transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Gavel className={`w-4 h-4 ${summonLoading ? 'animate-spin' : ''}`} />
                  <span>{summonLoading ? 'Đang Họp Tranh Biện...' : 'Triệu Tập Tranh Biện'}</span>
                </button>
              </form>
            </div>

            {/* 5.2 AGENT PIPELINE TOPOLOGY (Trạng Thái Trực Quan 7 Nhân Viên AI) */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center justify-between">
                <span>Cấu Trúc Luồng Vận Hành Hội Đồng (Agent Pipeline Topology)</span>
                <span className="text-slate-500">Mô hình Đa Tác Tử Không Tiêu Thụ Token (Zero-Token Architecture)</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                {[
                  { id: 'macro', name: 'Macro Scout', role: 'Vĩ mô & Lãi suất', icon: Globe, color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/20' },
                  { id: 'fa', name: 'FA Analyst', role: 'BCTC & Screener (0-Token)', icon: FileSpreadsheet, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
                  { id: 'quant', name: 'Quant / ML', role: 'Universal Alpha LightGBM', icon: Cpu, color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' },
                  { id: 'bull', name: 'Bull Advocate', role: 'Phe Mua (Tăng trưởng)', icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/20' },
                  { id: 'bear', name: 'Bear Red-Team', role: 'Phe Bán (Bẫy Kế toán)', icon: ShieldAlert, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' },
                  { id: 'cro', name: 'CRO Veto', role: 'Kiểm soát Rủi ro & Kelly', icon: Lock, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
                  { id: 'cio', name: 'CIO Decision', role: 'Giám đốc Đầu tư Quỹ', icon: Award, color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/20' }
                ].map((agent) => (
                  <div key={agent.id} className={`p-3 rounded-xl border ${agent.bg} flex flex-col justify-between space-y-2 relative overflow-hidden`}>
                    <div className="flex items-center justify-between">
                      <agent.icon className={`w-5 h-5 ${agent.color}`} />
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-mono bg-slate-950/80 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span>ONLINE</span>
                      </span>
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white leading-tight">{agent.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">{agent.role}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 5.2.B JEV AI SYSTEM 1 & HARNESS GUARDRAIL TELEMETRY */}
            <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-indigo-500/30 rounded-2xl p-5 shadow-xl space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2.5">
                  <div className="p-2 bg-amber-500/20 text-amber-400 rounded-xl border border-amber-500/30">
                    <Zap className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white flex items-center space-x-2">
                      <span>Jev AI System 1 Telemetry (Phản Xạ Quyết Định Tốc Độ Cao)</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono border border-indigo-500/30">
                        {latestJevTelemetry?.system_1_latency_ms ? `${latestJevTelemetry.system_1_latency_ms} ms` : '< 10 ms'} • Target &lt; 500ms
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Tách biệt System 1 (3 Primitives: Noul, Choice, Score) và System 2 Frontier LLM (Chỉ kích hoạt khi Confidence ≥ 0.75)
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs px-2.5 py-1 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono font-bold flex items-center space-x-1.5">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>HARNESS GUARDRAIL: ACTIVE</span>
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono">
                {/* 1. Noul Triage */}
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                  <div className="text-[11px] text-slate-400 font-sans font-bold flex items-center justify-between">
                    <span>1. Noul (Event Triage)</span>
                    <span className="text-amber-400 text-[10px]">
                      {latestJevTelemetry?.triage?.latency_ms ? `${latestJevTelemetry.triage.latency_ms}ms` : '0.1ms'}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-bold border ${
                      latestJevTelemetry?.triage?.value 
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/30' 
                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    }`}>
                      {latestJevTelemetry?.triage?.value ? 'MATERIAL IMPACT' : 'NOISE FILTERED'}
                    </span>
                    <span className="text-xs text-slate-300">
                      Conf: {latestJevTelemetry?.triage?.confidence ? (latestJevTelemetry.triage.confidence * 100).toFixed(1) + '%' : '99.0%'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-sans truncate">
                    {latestJevTelemetry?.triage?.reasoning || 'Lọc nhiễu thành công, sự kiện trong ngưỡng an toàn.'}
                  </p>
                </div>

                {/* 2. Choice Route */}
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                  <div className="text-[11px] text-slate-400 font-sans font-bold flex items-center justify-between">
                    <span>2. Choice (Book Routing)</span>
                    <span className="text-purple-400 text-[10px]">
                      {latestJevTelemetry?.route?.latency_ms ? `${latestJevTelemetry.route.latency_ms}ms` : '1.2ms'}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-bold border ${
                      (latestJevTelemetry?.route?.value || activeMemo?.strategy_book) === 'CORE'
                        ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                        : 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                    }`}>
                      SỔ {latestJevTelemetry?.route?.value || activeMemo?.strategy_book || 'CORE'}
                    </span>
                    <span className="text-xs text-slate-300">
                      Conf: {latestJevTelemetry?.route?.confidence ? (latestJevTelemetry.route.confidence * 100).toFixed(1) + '%' : '85.0%'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-sans truncate">
                    {latestJevTelemetry?.route?.reasoning || 'Định tuyến tự động dựa trên FA Score và xung lượng Alpha.'}
                  </p>
                </div>

                {/* 3. Score Execution Risk */}
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                  <div className="text-[11px] text-slate-400 font-sans font-bold flex items-center justify-between">
                    <span>3. Score (Execution Risk)</span>
                    <span className="text-rose-400 text-[10px]">
                      {latestJevTelemetry?.risk_score?.latency_ms ? `${latestJevTelemetry.risk_score.latency_ms}ms` : '0.5ms'}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-bold border ${
                      (latestJevTelemetry?.risk_score?.value || 0.05) > 0.70
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        : (latestJevTelemetry?.risk_score?.value || 0.05) > 0.40
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    }`}>
                      RỦI RO: {(latestJevTelemetry?.risk_score?.value !== undefined ? latestJevTelemetry.risk_score.value : 0.05).toFixed(2)} / 1.00
                    </span>
                    <span className="text-[10px] text-slate-300">
                      {(latestJevTelemetry?.risk_score?.value || 0.05) <= 0.70 ? 'PASS (<= 0.70)' : 'VETO (> 0.70)'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-sans truncate">
                    {latestJevTelemetry?.risk_score?.reasoning || 'Thanh khoản đạt chuẩn, kiểm soát rủi ro T+2.5 an toàn.'}
                  </p>
                </div>
              </div>
            </div>

            {/* 5.3 PHIÊN HỌP HIỆN TẠI (ACTIVE MEMO TELEMETRY & DEBATE ARENA) */}
            {activeMemo ? (
              <div className="space-y-6">
                
                {/* Header Tờ Trình */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold font-mono text-lg">
                        {activeMemo.ticker}
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="text-lg font-bold text-white">Tờ Trình Phê Duyệt Đầu Tư: {activeMemo.ticker}</h3>
                          <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                            activeMemo.strategy_book === 'CORE'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                          }`}>
                            {activeMemo.strategy_book === 'CORE' ? 'SỔ CORE (Dài Hạn)' : 'SỔ QUANT (Ngắn Hạn)'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 font-mono mt-0.5">
                          ID: {activeMemo.memo_id} • Thời gian: {activeMemo.created_at || 'Mới cập nhật'}
                        </p>
                      </div>
                    </div>

                    {/* Status & CEO Decision Buttons */}
                    <div className="flex items-center space-x-3">
                      <span className={`text-xs font-bold px-3 py-1.5 rounded-xl border ${
                        activeMemo.status === 'APPROVED'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : activeMemo.status === 'REJECTED'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          : 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
                      }`}>
                        TRẠNG THÁI: {activeMemo.status || 'PROPOSED'}
                      </span>

                      {activeMemo.status !== 'APPROVED' && activeMemo.status !== 'REJECTED' && (
                        <div className="flex space-x-2">
                          <button
                            type="button"
                            disabled={committeeActionLoading}
                            onClick={() => handleApproveMemo(activeMemo.memo_id)}
                            className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition flex items-center space-x-1.5 cursor-pointer shadow-lg shadow-emerald-600/20"
                          >
                            <CheckCircle className="w-4 h-4" />
                            <span>Phê Duyệt Đề Xuất</span>
                          </button>
                          <button
                            type="button"
                            disabled={committeeActionLoading}
                            onClick={() => handleRejectMemo(activeMemo.memo_id)}
                            className="px-4 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-bold rounded-xl transition flex items-center space-x-1.5 cursor-pointer"
                          >
                            <XCircle className="w-4 h-4" />
                            <span>Bác Bỏ</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 3 Thẻ Thông Tin Nền Tảng (Macro, FA, Quant/ML) */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                    {/* Macro Scout Card */}
                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                      <div className="flex items-center space-x-2 text-sky-400 text-xs font-bold">
                        <Globe className="w-4 h-4" />
                        <span>1. Macro Scout (Góc Nhìn Vĩ Mô)</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {typeof activeMemo.macro_view === 'object' && activeMemo.macro_view !== null
                          ? activeMemo.macro_view.headline || JSON.stringify(activeMemo.macro_view)
                          : activeMemo.macro_view || 'Vĩ mô ổn định, chính sách tiền tệ hỗ trợ dòng vốn.'}
                      </p>
                    </div>

                    {/* FA Analyst Card */}
                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                      <div className="flex items-center space-x-2 text-emerald-400 text-xs font-bold">
                        <FileSpreadsheet className="w-4 h-4" />
                        <span>2. FA Analyst (Chấm Điểm 0-Token)</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-mono">
                        {typeof activeMemo.fa_summary === 'object' && activeMemo.fa_summary !== null
                          ? `FA Score: ${activeMemo.fa_summary.score || 'N/A'}/100 | P/E: ${activeMemo.fa_summary.pe || 'N/A'} | ROE: ${activeMemo.fa_summary.roe ? (activeMemo.fa_summary.roe * 100).toFixed(1) + '%' : 'N/A'}`
                          : activeMemo.fa_summary || 'Chỉ số cơ bản đạt yêu cầu sàng lọc.'}
                      </p>
                    </div>

                    {/* Quant/ML Card */}
                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                      <div className="flex items-center space-x-2 text-purple-400 text-xs font-bold">
                        <Cpu className="w-4 h-4" />
                        <span>3. Quant / Universal Alpha (ML)</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-mono">
                        {typeof activeMemo.ta_ml_summary === 'object' && activeMemo.ta_ml_summary !== null
                          ? `Alpha Score: ${activeMemo.ta_ml_summary.ml_score || 'N/A'} | ATR: ${activeMemo.ta_ml_summary.atr_14 || 'N/A'}`
                          : activeMemo.ta_ml_summary || 'Mô hình ML xác nhận tín hiệu động lượng tích cực.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* PHÒNG TRANH BIỆN 2 CỘT (BULL VS. BEAR DEBATE ARENA) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  
                  {/* CỘT 1: PHE BÒ (BULL ADVOCATE) */}
                  <div className="bg-slate-900/90 border border-emerald-500/30 rounded-2xl p-6 shadow-xl space-y-4 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none"></div>
                    <div className="flex items-center justify-between border-b border-emerald-500/20 pb-3">
                      <div className="flex items-center space-x-2 text-emerald-400 font-bold">
                        <TrendingUp className="w-5 h-5" />
                        <span>PHE BÒ (BULL ADVOCATE)</span>
                      </div>
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        MỤC TIÊU: {activeMemo.target_price ? Number(activeMemo.target_price).toLocaleString() + ' đ' : 'Chưa đặt'}
                      </span>
                    </div>

                    <div className="text-xs text-slate-300 space-y-2">
                      <div className="font-semibold text-emerald-300 text-xs uppercase tracking-wide">
                        Các Luận Điểm Đột Phá & Động Lực Tăng Giá:
                      </div>
                      <div className="bg-slate-950/70 rounded-xl p-4 border border-emerald-500/10 leading-relaxed space-y-2">
                        {(() => {
                          const args = activeMemo.bull_arguments;
                          if (!args) return <div>Không có ghi chú.</div>;
                          if (Array.isArray(args)) {
                            return <ul className="space-y-1.5 list-disc list-inside">{args.map((a, i) => <li key={i}>{a}</li>)}</ul>;
                          }
                          const lines = String(args).split('\n').filter(l => l.trim().length > 0);
                          return (
                            <ul className="space-y-2">
                              {lines.map((l, i) => (
                                <li key={i} className="flex items-start space-x-2">
                                  <span className="text-emerald-400 font-bold">✓</span>
                                  <span>{l.replace(/^[-*•\d.]+\s*/, '')}</span>
                                </li>
                              ))}
                            </ul>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* CỘT 2: PHE GẤU (BEAR RED-TEAM) */}
                  <div className="bg-slate-900/90 border border-rose-500/30 rounded-2xl p-6 shadow-xl space-y-4 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-rose-500/5 rounded-full blur-2xl pointer-events-none"></div>
                    <div className="flex items-center justify-between border-b border-rose-500/20 pb-3">
                      <div className="flex items-center space-x-2 text-rose-400 font-bold">
                        <ShieldAlert className="w-5 h-5" />
                        <span>PHE GẤU (BEAR RED-TEAM)</span>
                      </div>
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        CẮT LỖ: {activeMemo.stop_loss_price ? Number(activeMemo.stop_loss_price).toLocaleString() + ' đ' : 'Chưa đặt'}
                      </span>
                    </div>

                    <div className="text-xs text-slate-300 space-y-2">
                      <div className="font-semibold text-rose-300 text-xs uppercase tracking-wide">
                        Phản Biện Bẫy Định Giá & Cảnh Báo BCTC:
                      </div>
                      <div className="bg-slate-950/70 rounded-xl p-4 border border-rose-500/10 leading-relaxed space-y-2">
                        {(() => {
                          const args = activeMemo.bear_arguments;
                          if (!args) return <div>Không có cảnh báo rủi ro đặc biệt.</div>;
                          if (Array.isArray(args)) {
                            return <ul className="space-y-1.5 list-disc list-inside">{args.map((a, i) => <li key={i}>{a}</li>)}</ul>;
                          }
                          const lines = String(args).split('\n').filter(l => l.trim().length > 0);
                          return (
                            <ul className="space-y-2">
                              {lines.map((l, i) => (
                                <li key={i} className="flex items-start space-x-2">
                                  <span className="text-rose-400 font-bold">⚠</span>
                                  <span>{l.replace(/^[-*•\d.]+\s*/, '')}</span>
                                </li>
                              ))}
                            </ul>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                </div>

                {/* PHÁN QUYẾT CRO & CIO */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* CRO Card */}
                  <div className="bg-slate-900 border border-amber-500/30 rounded-2xl p-5 shadow-xl space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                      <div className="flex items-center space-x-2 text-amber-400 font-bold text-sm">
                        <Lock className="w-4 h-4" />
                        <span>Phán Quyết Quản Trị Rủi Ro (CRO Verdict)</span>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {typeof activeMemo.cro_verdict === 'object' && activeMemo.cro_verdict !== null
                          ? activeMemo.cro_verdict.decision || 'APPROVED'
                          : activeMemo.cro_verdict || 'APPROVED'}
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 space-y-2">
                      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                          <span className="text-slate-500 block text-[10px]">TỶ TRỌNG TỐI ĐA</span>
                          <span className="text-amber-400 font-bold text-sm">
                            {activeMemo.cro_position_size 
                              ? (Number(activeMemo.cro_position_size) * 100).toFixed(1) + '% NAV' 
                              : (activeMemo.strategy_book === 'CORE' ? '25.0% NAV' : '15.0% NAV')}
                          </span>
                        </div>
                        <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                          <span className="text-slate-500 block text-[10px]">KHỐI LƯỢNG ĐỀ XUẤT</span>
                          <span className="text-white font-bold text-sm">
                            {Number(activeMemo.target_volume || 0).toLocaleString()} CP
                          </span>
                        </div>
                      </div>
                      <p className="text-[11px] text-slate-400 italic">
                        {activeMemo.strategy_book === 'CORE'
                          ? 'Sổ CORE áp dụng Hard Stop-Loss 15%, Max Position 25% NAV và kiểm toán Red Flags BCTC nghiêm ngặt.'
                          : 'Sổ QUANT áp dụng Hard Stop-Loss 7%, Max Position 15% NAV và cắt lỗ dứt khoát theo ATR.'}
                      </p>
                    </div>
                  </div>

                  {/* CIO Card */}
                  <div className="bg-slate-900 border border-indigo-500/30 rounded-2xl p-5 shadow-xl space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                      <div className="flex items-center space-x-2 text-indigo-400 font-bold text-sm">
                        <Award className="w-4 h-4" />
                        <span>Quyết Định Giám Đốc Đầu Tư (CIO Decision)</span>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                        {activeMemo.action || 'BUY'}
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 space-y-2">
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 leading-relaxed font-mono">
                        {typeof activeMemo.cio_decision === 'object' && activeMemo.cio_decision !== null
                          ? activeMemo.cio_decision.rationale || JSON.stringify(activeMemo.cio_decision)
                          : activeMemo.cio_decision || 'Đề xuất giải ngân cổ phiếu theo tỷ trọng đã được CRO thông qua.'}
                      </div>
                      <div className="text-[11px] text-slate-400 flex items-center justify-between">
                        <span>Hành động: <strong className="text-white">{activeMemo.action || 'BUY'}</strong></span>
                        <span>Mục tiêu: <strong className="text-emerald-400">{Number(activeMemo.target_price || 0).toLocaleString()} đ</strong></span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl text-slate-500 space-y-3">
                <Scale className="w-10 h-10 mx-auto text-slate-600" />
                <p>Chưa có biên bản họp nào được chọn hoặc đang tải dữ liệu.</p>
                <p className="text-xs text-slate-600">Nhập mã CP ở trên và bấm "Triệu Tập Tranh Biện" để triệu tập Ủy Ban Đầu Tư ngay lập tức.</p>
              </div>
            )}

            {/* 5.4 DANH SÁCH CÁC TỜ TRÌNH ĐÃ GHI NHẬN (HISTORICAL COMMITTEE MEMOS) */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-amber-400" />
                  <span>Lịch Sử Các Tờ Trình Ủy Ban Đầu Tư ({committeeMemos.length})</span>
                </h3>
                <span className="text-xs text-slate-500">Được lưu vết bảo mật trong database SQLite</span>
              </div>

              {committeeMemos.length === 0 ? (
                <div className="text-xs text-slate-500 py-4 text-center">Chưa có tờ trình nào được ghi nhận.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="py-2.5 px-3">Thời Gian</th>
                        <th className="py-2.5 px-3">Mã CP</th>
                        <th className="py-2.5 px-3">Sổ Chiến Lược</th>
                        <th className="py-2.5 px-3">Lệnh</th>
                        <th className="py-2.5 px-3 text-right">Khối Lượng</th>
                        <th className="py-2.5 px-3 text-right">Giá Mục Tiêu</th>
                        <th className="py-2.5 px-3">Phán Quyết CRO</th>
                        <th className="py-2.5 px-3 text-center">Trạng Thái</th>
                        <th className="py-2.5 px-3 text-right">Thao Tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {committeeMemos.map((memo) => (
                        <tr 
                          key={memo.memo_id}
                          className={`hover:bg-slate-800/40 transition cursor-pointer ${
                            activeMemo && activeMemo.memo_id === memo.memo_id ? 'bg-amber-500/5' : ''
                          }`}
                          onClick={() => {
                            setActiveMemo(memo);
                            if (memo.jev_telemetry) setLatestJevTelemetry(memo.jev_telemetry);
                          }}
                        >
                          <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                            {memo.created_at ? memo.created_at.split(' ')[0] : 'N/A'}
                          </td>
                          <td className="py-2.5 px-3 font-bold text-white">{memo.ticker}</td>
                          <td className="py-2.5 px-3">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-semibold border ${
                              memo.strategy_book === 'CORE'
                                ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                            }`}>
                              {memo.strategy_book || 'QUANT'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-emerald-400 font-bold">{memo.action || 'BUY'}</td>
                          <td className="py-2.5 px-3 text-right text-slate-200">
                            {Number(memo.target_volume || 0).toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-200">
                            {Number(memo.target_price || 0).toLocaleString()} đ
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="text-[10px] text-amber-400">
                              {typeof memo.cro_verdict === 'object' && memo.cro_verdict !== null 
                                ? memo.cro_verdict.decision || 'APPROVED' 
                                : memo.cro_verdict || 'APPROVED'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                              memo.status === 'APPROVED'
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : memo.status === 'REJECTED'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            }`}>
                              {memo.status || 'PROPOSED'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setActiveMemo(memo); }}
                              className="text-[11px] text-amber-400 hover:text-amber-300 underline font-sans cursor-pointer"
                            >
                              Xem Chi Tiết
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Sổ Chiến Lược</label>
                  <select
                    value={fillForm.strategy_book || 'QUANT'}
                    onChange={e => setFillForm({...fillForm, strategy_book: e.target.value})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
                  >
                    <option value="QUANT">QUANT (Trading Ngắn)</option>
                    <option value="CORE">CORE (Fundamental)</option>
                  </select>
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
