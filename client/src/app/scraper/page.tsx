"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { 
  Play, 
  Square, 
  Trash2, 
  RefreshCw, 
  Database, 
  Layers, 
  DollarSign, 
  AlertCircle, 
  Terminal, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  ArrowLeft,
  Globe,
  Send,
  Copy,
  Check,
  Server,
  ShieldCheck,
} from "lucide-react";

interface ScraperStatusData {
  isRunning: boolean;
  counts: {
    products: number;
    variants: number;
    offers: number;
    priceListings: number;
    unmatched: number;
  };
  recentLogs: string[];
  logAvailable: boolean;
  lastCheckedAt: string;
}

export default function ScraperPage() {
  const [statusData, setStatusData] = useState<ScraperStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // API Console States (Stitch Screen 3)
  const [activeEndpoint, setActiveEndpoint] = useState("/api/products");
  const [apiLoading, setApiLoading] = useState(false);
  const [apiResponse, setApiResponse] = useState<any>(null);
  const [apiStatus, setApiStatus] = useState<number | null>(null);
  const [apiLatency, setApiLatency] = useState<number | null>(null);
  const [copiedCurl, setCopiedCurl] = useState(false);

  const executeApiRequest = async (endpointUrl: string) => {
    setApiLoading(true);
    setApiStatus(null);
    setApiResponse(null);
    const start = performance.now();
    try {
      const res = await fetch(endpointUrl);
      const latency = Math.round(performance.now() - start);
      setApiLatency(latency);
      setApiStatus(res.status);
      const data = await res.json();
      setApiResponse(data);
    } catch (err: any) {
      setApiLatency(Math.round(performance.now() - start));
      setApiStatus(500);
      setApiResponse({ error: err.message || "Failed to execute request" });
    } finally {
      setApiLoading(false);
    }
  };

  const handleCopyCurl = () => {
    if (typeof window !== "undefined") {
      const fullUrl = `${window.location.origin}${activeEndpoint}`;
      const curlCmd = `curl -X GET "${fullUrl}" -H "Accept: application/json"`;
      navigator.clipboard.writeText(curlCmd);
      setCopiedCurl(true);
      setTimeout(() => setCopiedCurl(false), 2000);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/scraper");
      if (!res.ok) throw new Error("Failed to fetch scraper status");
      const json = await res.json();
      if (json.success) {
        setStatusData(json.status);
      }
    } catch (err: any) {
      console.error("Error polling scraper status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    if (!autoRefresh) return;
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [statusData?.recentLogs]);

  const handleAction = async (action: 'start_scrape' | 'purge_database' | 'stop_scrape') => {
    if (action === 'purge_database') {
      const confirmed = window.confirm(
        "WARNING: This will completely erase all products, variants, price listings, and unmatched data points from Supabase. Are you sure?"
      );
      if (!confirmed) return;
    }

    setActionInProgress(action);
    setActionFeedback(null);

    try {
      const res = await fetch("/api/scraper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();

      if (data.success) {
        setActionFeedback({
          type: 'success',
          message: data.message || `Action ${action} completed successfully.`,
        });
      } else {
        setActionFeedback({
          type: 'error',
          message: data.error || `Action ${action} failed.`,
        });
      }
      await fetchStatus();
    } catch (err: any) {
      setActionFeedback({
        type: 'error',
        message: err.message || 'Request failed',
      });
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-emerald-500 selection:text-white">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-30 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link 
              href="/"
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all flex items-center gap-2 text-sm font-semibold"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Store</span>
            </Link>
            <div className="h-5 w-px bg-slate-700" />
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-emerald-400" />
              <h1 className="font-bold text-lg text-white tracking-wide">
                Proteindex Scraper Control Plane
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
              <input 
                type="checkbox" 
                checked={autoRefresh} 
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-slate-600 text-emerald-500 focus:ring-0"
              />
              <span>Live Poll (3s)</span>
            </label>

            <button 
              onClick={fetchStatus}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              title="Refresh Now"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Banner / Feedback Notification */}
        {actionFeedback && (
          <div 
            className={`p-4 rounded-xl flex items-center justify-between border ${
              actionFeedback.type === 'success' 
                ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200' 
                : 'bg-rose-950/60 border-rose-800 text-rose-200'
            }`}
          >
            <div className="flex items-center gap-3">
              {actionFeedback.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
              )}
              <span className="text-sm font-medium">{actionFeedback.message}</span>
            </div>
            <button 
              onClick={() => setActionFeedback(null)}
              className="text-xs uppercase font-semibold opacity-70 hover:opacity-100"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Hero Control Bar */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
          {/* Status Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Engine Status
              </span>
              <div className="mt-3 flex items-center gap-3">
                <div className="relative flex h-3.5 w-3.5">
                  {statusData?.isRunning ? (
                    <>
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500"></span>
                    </>
                  ) : (
                    <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-slate-600"></span>
                  )}
                </div>
                <span className="text-xl font-bold tracking-tight text-white">
                  {statusData?.isRunning ? "ACTIVE / RUNNING" : "IDLE / STANDBY"}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                {statusData?.isRunning 
                  ? "Scrapling workers are actively querying configured platforms and indexing data."
                  : "Scraper is not running. Ready to trigger or execute full market collection."}
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span>Last Checked</span>
              <span className="font-mono text-slate-300">
                {statusData?.lastCheckedAt ? new Date(statusData.lastCheckedAt).toLocaleTimeString() : "Never"}
              </span>
            </div>
          </div>

          {/* Action Trigger Buttons */}
          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Execution Controls
              </span>
              <h2 className="text-lg font-bold text-white mt-1">
                Scraper Engine Operations
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Start a complete multi-source extraction, cleanly purge the catalogue, or stop active processes.
              </p>
            </div>

            <div className="mt-6 flex flex-wrap gap-4">
              {/* Start Scrape Button */}
              <button
                onClick={() => handleAction('start_scrape')}
                disabled={actionInProgress !== null || statusData?.isRunning}
                className="flex-1 min-w-[180px] px-5 py-3.5 rounded-xl font-bold text-sm bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2.5 shadow-lg shadow-emerald-950/50 transition-all active:scale-[0.98]"
              >
                <Play className="w-4 h-4 fill-white" />
                <span>
                  {actionInProgress === 'start_scrape' ? "Starting..." : "Run Complete Scrape"}
                </span>
              </button>

              {/* Stop Scrape Button */}
              <button
                onClick={() => handleAction('stop_scrape')}
                disabled={actionInProgress !== null || !statusData?.isRunning}
                className="px-5 py-3.5 rounded-xl font-bold text-sm bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 border border-slate-700 transition-all"
              >
                <Square className="w-4 h-4 fill-slate-300" />
                <span>
                  {actionInProgress === 'stop_scrape' ? "Stopping..." : "Stop Scraper"}
                </span>
              </button>

              {/* Purge Master Catalogue Button */}
              <button
                onClick={() => handleAction('purge_database')}
                disabled={actionInProgress !== null}
                className="px-5 py-3.5 rounded-xl font-bold text-sm bg-rose-950/50 hover:bg-rose-900/60 text-rose-300 border border-rose-800/80 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
              >
                <Trash2 className="w-4 h-4 text-rose-400" />
                <span>
                  {actionInProgress === 'purge_database' ? "Purging Database..." : "Erase Master Catalogue"}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Database Metric Cards */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              <span>Live Database Metrics (Supabase)</span>
            </h3>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold uppercase">Products</span>
                <Database className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-black text-white font-mono">
                {statusData?.counts.products.toLocaleString() ?? "—"}
              </div>
              <span className="text-[11px] text-slate-500">Master Formulations</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold uppercase">Variants</span>
                <Layers className="w-4 h-4 text-blue-400" />
              </div>
              <div className="text-3xl font-black text-white font-mono">
                {statusData?.counts.variants.toLocaleString() ?? "—"}
              </div>
              <span className="text-[11px] text-slate-500">Size & Flavor SKUs</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold uppercase">Price Listings</span>
                <DollarSign className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-black text-white font-mono">
                {statusData?.counts.priceListings.toLocaleString() ?? "—"}
              </div>
              <span className="text-[11px] text-slate-500">Active Retailer Quotes</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold uppercase">Offers</span>
                <DollarSign className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-3xl font-black text-white font-mono">
                {statusData?.counts.offers.toLocaleString() ?? "—"}
              </div>
              <span className="text-[11px] text-slate-500">Legacy Offers Table</span>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold uppercase">Unmatched</span>
                <AlertCircle className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-3xl font-black text-white font-mono">
                {statusData?.counts.unmatched.toLocaleString() ?? "—"}
              </div>
              <span className="text-[11px] text-slate-500">Raw Staging Queue</span>
            </div>
          </div>
        </div>

        {/* Section 1: Scraper Ingestion Workers Matrix (Stitch Screen 3) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-mono font-bold tracking-wider uppercase text-slate-200">
                Active Scraper Ingestion Workers Matrix
              </h2>
            </div>
            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              4 / 4 Nodes Online
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Node 1: Amazon */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold">Worker Node 01</span>
                  <h3 className="font-bold text-sm text-white">Amazon India (IN)</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs font-mono space-y-1 text-slate-400">
                <div className="flex justify-between">
                  <span>Engine:</span>
                  <span className="text-slate-200 font-semibold">Playwright Stealth</span>
                </div>
                <div className="flex justify-between">
                  <span>Avg Latency:</span>
                  <span className="text-emerald-400 font-semibold">420ms</span>
                </div>
                <div className="flex justify-between">
                  <span>Success Rate:</span>
                  <span className="text-slate-200 font-semibold">99.4%</span>
                </div>
                <div className="flex justify-between">
                  <span>Anti-Bot:</span>
                  <span className="text-cyan-400 font-semibold">Browser Fingerprint</span>
                </div>
              </div>
            </div>

            {/* Node 2: Nutrabay */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold">Worker Node 02</span>
                  <h3 className="font-bold text-sm text-white">Nutrabay Direct</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs font-mono space-y-1 text-slate-400">
                <div className="flex justify-between">
                  <span>Engine:</span>
                  <span className="text-slate-200 font-semibold">Direct API Fetch</span>
                </div>
                <div className="flex justify-between">
                  <span>Avg Latency:</span>
                  <span className="text-emerald-400 font-semibold">180ms</span>
                </div>
                <div className="flex justify-between">
                  <span>Success Rate:</span>
                  <span className="text-slate-200 font-semibold">100.0%</span>
                </div>
                <div className="flex justify-between">
                  <span>Anti-Bot:</span>
                  <span className="text-cyan-400 font-semibold">Session Cookies</span>
                </div>
              </div>
            </div>

            {/* Node 3: Flipkart */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold">Worker Node 03</span>
                  <h3 className="font-bold text-sm text-white">Flipkart Retail</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs font-mono space-y-1 text-slate-400">
                <div className="flex justify-between">
                  <span>Engine:</span>
                  <span className="text-slate-200 font-semibold">Mobile DOM Scraper</span>
                </div>
                <div className="flex justify-between">
                  <span>Avg Latency:</span>
                  <span className="text-emerald-400 font-semibold">610ms</span>
                </div>
                <div className="flex justify-between">
                  <span>Success Rate:</span>
                  <span className="text-slate-200 font-semibold">98.1%</span>
                </div>
                <div className="flex justify-between">
                  <span>Anti-Bot:</span>
                  <span className="text-cyan-400 font-semibold">Rotating User-Agent</span>
                </div>
              </div>
            </div>

            {/* Node 4: HealthKart */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold">Worker Node 04</span>
                  <h3 className="font-bold text-sm text-white">HealthKart Store</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs font-mono space-y-1 text-slate-400">
                <div className="flex justify-between">
                  <span>Engine:</span>
                  <span className="text-slate-200 font-semibold">GraphQL Feed</span>
                </div>
                <div className="flex justify-between">
                  <span>Avg Latency:</span>
                  <span className="text-emerald-400 font-semibold">350ms</span>
                </div>
                <div className="flex justify-between">
                  <span>Success Rate:</span>
                  <span className="text-slate-200 font-semibold">99.0%</span>
                </div>
                <div className="flex justify-between">
                  <span>Anti-Bot:</span>
                  <span className="text-cyan-400 font-semibold">Header Checksum</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Interactive API Workbench & Console (Stitch Screen 3) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl space-y-4 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-mono font-bold tracking-wider uppercase text-slate-200">
                Interactive Aggregator REST API Console
              </h2>
            </div>

            {/* Quick Endpoint Presets */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
              {[
                { label: "All Products", path: "/api/products" },
                { label: "Whey Isolate", path: "/api/products?category=whey_protein" },
                { label: "Nakpro Brand", path: "/api/products?brand=Nakpro" },
                { label: "Scraper Status", path: "/api/scraper" },
              ].map((preset) => (
                <button
                  key={preset.path}
                  type="button"
                  onClick={() => {
                    setActiveEndpoint(preset.path);
                    executeApiRequest(preset.path);
                  }}
                  className={`px-2 py-1 rounded border text-[11px] transition-colors ${
                    activeEndpoint === preset.path
                      ? "bg-emerald-950 border-emerald-700 text-emerald-300 font-bold"
                      : "bg-slate-800 border-slate-700 text-slate-300 hover:text-white"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive URL Bar */}
          <div className="flex items-center gap-2 bg-slate-950 p-2 rounded-xl border border-slate-800 font-mono text-xs">
            <span className="px-2.5 py-1 bg-emerald-900/60 text-emerald-400 border border-emerald-700/80 rounded font-bold">
              GET
            </span>
            <input
              type="text"
              value={activeEndpoint}
              onChange={(e) => setActiveEndpoint(e.target.value)}
              placeholder="/api/products"
              className="flex-1 bg-transparent text-slate-200 focus:outline-none px-2"
            />
            <button
              type="button"
              onClick={() => executeApiRequest(activeEndpoint)}
              disabled={apiLoading}
              className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold rounded flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              {apiLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>Execute</span>
            </button>
            <button
              type="button"
              onClick={handleCopyCurl}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded flex items-center gap-1.5 transition-colors"
              title="Copy cURL Command"
            >
              {copiedCurl ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedCurl ? "Copied" : "cURL"}</span>
            </button>
          </div>

          {/* API Response Preview Panel */}
          {apiResponse && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-2">
              <div className="flex items-center justify-between text-[11px] pb-2 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded font-bold ${
                      apiStatus === 200
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : "bg-rose-950 text-rose-400 border border-rose-800"
                    }`}
                  >
                    HTTP {apiStatus || 200} OK
                  </span>
                  {apiLatency !== null && (
                    <span className="text-slate-400">Response time: <strong className="text-slate-200">{apiLatency}ms</strong></span>
                  )}
                </div>
                <span className="text-slate-500">Payload: application/json</span>
              </div>
              <pre className="max-h-64 overflow-y-auto text-[11px] text-slate-300 scrollbar-thin scrollbar-thumb-slate-800 leading-relaxed">
                {JSON.stringify(apiResponse, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Live Terminal Log Stream */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
          <div className="bg-slate-850 px-6 py-3.5 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono font-bold tracking-wider uppercase text-slate-300">
                Real-Time Scraper Engine Output (scraper_production.log)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
            </div>
          </div>

          <div 
            ref={logContainerRef}
            className="p-6 font-mono text-xs text-slate-300 bg-slate-950/90 h-96 overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-slate-800"
          >
            {statusData?.recentLogs && statusData.recentLogs.length > 0 ? (
              statusData.recentLogs.map((line, idx) => {
                let colorClass = "text-slate-300";
                if (line.includes("[ERROR]") || line.includes("Failed")) colorClass = "text-rose-400 font-semibold";
                else if (line.includes("[WARNING]")) colorClass = "text-amber-300";
                else if (line.includes("MATCHED") || line.includes("valid products") || line.includes("Found")) colorClass = "text-emerald-400";
                else if (line.includes("Commencing extraction")) colorClass = "text-cyan-300 font-bold";

                return (
                  <div key={idx} className={`leading-relaxed break-all ${colorClass}`}>
                    {line}
                  </div>
                );
              })
            ) : (
              <div className="text-slate-500 italic py-8 text-center">
                No logs recorded yet. Click &quot;Run Complete Scrape&quot; to begin scraping data into the master catalogue.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
