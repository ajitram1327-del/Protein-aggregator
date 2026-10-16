"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Bell, Trash2, CheckCircle2, ShieldCheck, Plus, Clock } from "lucide-react";
import { formatInr } from "@/lib/analytics";

interface SavedAlert {
  id: string;
  productId: string;
  productName: string;
  currentPrice: number;
  targetPrice: number;
  channel: "whatsapp" | "email";
  contact: string;
  createdAt: string;
  active?: boolean;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<SavedAlert[]>([]);
  const [isAdding, setIsAdding] = useState(false);
  const [productName, setProductName] = useState("");
  const [targetPrice, setTargetPrice] = useState<number>(2499);
  const [channel, setChannel] = useState<"whatsapp" | "email">("whatsapp");
  const [contact, setContact] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = JSON.parse(localStorage.getItem("proteindex_alerts") || "[]");
      setAlerts(saved);
    }
  }, []);

  const handleSaveAlert = (e: React.FormEvent) => {
    e.preventDefault();
    if (!productName.trim() || !contact.trim()) return;

    const newAlert: SavedAlert = {
      id: Date.now().toString(),
      productId: "custom",
      productName: productName.trim(),
      currentPrice: Math.round(targetPrice * 1.15),
      targetPrice,
      channel,
      contact: contact.trim(),
      createdAt: new Date().toISOString(),
      active: true,
    };

    const updated = [newAlert, ...alerts];
    setAlerts(updated);
    if (typeof window !== "undefined") {
      localStorage.setItem("proteindex_alerts", JSON.stringify(updated));
    }

    setProductName("");
    setContact("");
    setIsAdding(false);
    setSuccessMsg("Alert active! We will notify you when price drops below your target.");
    setTimeout(() => setSuccessMsg(""), 4000);
  };

  const handleDeleteAlert = (id: string) => {
    const updated = alerts.filter((a) => a.id !== id);
    setAlerts(updated);
    if (typeof window !== "undefined") {
      localStorage.setItem("proteindex_alerts", JSON.stringify(updated));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-24">
      {/* Header */}
      <header className="border-b border-slate-200 px-4 sm:px-6 py-3 bg-white">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto">
          <Link href="/" className="font-black text-2xl tracking-tighter text-slate-900 italic flex items-center">
            <span className="text-emerald-700">PROTE</span>INDEX
          </Link>
          <div className="flex items-center gap-3 text-xs font-mono">
            <Link href="/catalog" className="text-slate-600 hover:text-slate-900 font-bold">
              Catalog Screener →
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <div className="mb-6 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
            <Link href="/catalog" className="hover:text-slate-900 flex items-center gap-1 font-semibold">
              <ArrowLeft className="size-3" /> Catalog
            </Link>
            <span>/</span>
            <span className="text-slate-900 font-bold">Price Drop & Stock Alerts</span>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                <Bell className="size-6 text-emerald-700" />
                <span>Price Intelligence & Drop Subscriptions</span>
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 font-mono mt-1">
                Direct notification via WhatsApp or Email whenever authorized sellers hit your target threshold.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsAdding(!isAdding)}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-900 hover:bg-emerald-800 text-white text-xs font-mono font-bold uppercase rounded-sm transition-colors self-start"
            >
              <Plus className="size-3.5" />
              <span>{isAdding ? "Cancel" : "Create New Alert"}</span>
            </button>
          </div>
        </div>

        {successMsg && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-mono rounded-sm flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-700 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Create Alert Form */}
        {isAdding && (
          <form onSubmit={handleSaveAlert} className="bg-white border border-slate-200 rounded-sm p-6 shadow-xs mb-8 font-mono text-xs">
            <h2 className="font-bold text-slate-900 uppercase tracking-wider text-sm mb-4 border-b border-slate-100 pb-2">
              Configure Target Alert
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Product or Supplement Name</label>
                <input
                  type="text"
                  required
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g. Optimum Nutrition Gold Standard Whey 2kg"
                  className="w-full px-3 py-2 border border-slate-300 rounded-sm text-xs focus:border-slate-900 outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Target Price (INR)</label>
                <input
                  type="number"
                  required
                  min="500"
                  max="50000"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-sm text-xs focus:border-slate-900 outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Notification Channel</label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value as any)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-sm text-xs focus:border-slate-900 outline-none bg-white cursor-pointer"
                >
                  <option value="whatsapp">WhatsApp (Direct Notification)</option>
                  <option value="email">Email</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-600 font-semibold mb-1">
                  {channel === "whatsapp" ? "WhatsApp Number (+91)" : "Email Address"}
                </label>
                <input
                  type={channel === "whatsapp" ? "tel" : "email"}
                  required
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder={channel === "whatsapp" ? "9876543210" : "you@example.com"}
                  className="w-full px-3 py-2 border border-slate-300 rounded-sm text-xs focus:border-slate-900 outline-none"
                />
              </div>
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="submit"
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white font-bold uppercase rounded-sm transition-colors text-xs"
              >
                Activate Subscription
              </button>
            </div>
          </form>
        )}

        {/* Existing Alerts List */}
        <div className="bg-white border border-slate-200 rounded-sm p-6 shadow-xs font-mono text-xs">
          <h2 className="font-bold text-slate-900 uppercase tracking-wider text-xs mb-4 border-b border-slate-100 pb-2 flex items-center justify-between">
            <span>Your Active Price Subscriptions ({alerts.length})</span>
            <span className="text-[10px] text-slate-400">Stored on device</span>
          </h2>

          {alerts.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <p className="font-bold text-slate-700">No price alerts active yet.</p>
              <p className="mt-1 text-[11px]">Set a price drop alert to get notified when supplements go on flash sale.</p>
              <button
                type="button"
                onClick={() => setIsAdding(true)}
                className="mt-4 px-3 py-1.5 bg-slate-900 text-white font-bold rounded-sm uppercase text-xs hover:bg-emerald-800 transition-colors"
              >
                Create Alert Now
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-sm gap-3"
                >
                  <div>
                    <div className="font-bold text-slate-900 text-sm">{alert.productName}</div>
                    <div className="flex items-center gap-3 text-slate-500 text-[11px] mt-1">
                      <span>Target: <strong className="text-emerald-800">{formatInr(alert.targetPrice)}</strong></span>
                      <span>Channel: <strong className="uppercase">{alert.channel}</strong> ({alert.contact})</span>
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" /> {new Date(alert.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteAlert(alert.id)}
                    className="self-end sm:self-center p-2 text-slate-400 hover:text-red-600 transition-colors"
                    title="Delete Alert"
                    aria-label="Delete Alert"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
