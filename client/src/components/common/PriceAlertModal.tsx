"use client";

import React, { useState } from "react";
import { X, Bell, Check, Sparkles, AlertCircle } from "lucide-react";
import { GroupedProduct } from "@/components/ProductBrowser";
import { formatInr } from "@/lib/analytics";

interface PriceAlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  products?: GroupedProduct[];
  preselectedProduct?: GroupedProduct | null;
}

export const PriceAlertModal: React.FC<PriceAlertModalProps> = ({
  isOpen,
  onClose,
  products = [],
  preselectedProduct = null,
}) => {
  const [selectedProductId, setSelectedProductId] = useState<string>(
    preselectedProduct?.id || products[0]?.id || ""
  );
  const [targetPrice, setTargetPrice] = useState<number>(() => {
    if (preselectedProduct) return Math.round(preselectedProduct.lowestPrice * 0.9);
    return 2499;
  });
  const [notificationChannel, setNotificationChannel] = useState<"whatsapp" | "email">("whatsapp");
  const [contactValue, setContactValue] = useState("");
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const currentSelected = products.find((p) => p.id === selectedProductId) || preselectedProduct;
  const currentPrice = currentSelected?.lowestPrice || 2999;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactValue.trim()) return;

    // Save alert in localStorage
    if (typeof window !== "undefined") {
      const existing = JSON.parse(localStorage.getItem("proteindex_alerts") || "[]");
      existing.push({
        id: Date.now().toString(),
        productId: selectedProductId,
        productName: currentSelected?.baseProductName || "Custom Supplement",
        currentPrice,
        targetPrice,
        channel: notificationChannel,
        contact: contactValue,
        createdAt: new Date().toISOString(),
      });
      localStorage.setItem("proteindex_alerts", JSON.stringify(existing));
    }

    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      onClose();
    }, 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs font-sans">
      <div className="bg-white border border-slate-300 rounded-sm shadow-xl max-w-md w-full overflow-hidden">
        {/* Modal Header */}
        <div className="bg-slate-900 text-white p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="size-4 text-emerald-400" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider">
              Set Price Drop Target Alert
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Modal Body */}
        {submitted ? (
          <div className="p-8 text-center space-y-3">
            <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
              <Check className="size-6" />
            </div>
            <h4 className="text-base font-bold text-slate-900">Price Target Alert Armed</h4>
            <p className="text-xs text-slate-600 leading-relaxed font-mono">
              We will monitor Amazon, Flipkart, Nutrabay & D2C stores 24/7. When price hits{" "}
              <strong className="text-emerald-700 font-bold">{formatInr(targetPrice)}</strong>, an alert will be dispatched to{" "}
              <span className="font-bold">{contactValue}</span>.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-5 space-y-4">
            <p className="text-xs text-slate-600 leading-relaxed">
              Never miss a genuine price glitch or flash discount. Our automated scraper monitors authorized stores every hour.
            </p>

            {/* Product selection */}
            {products.length > 0 && !preselectedProduct && (
              <div>
                <label className="block text-xs font-mono font-bold text-slate-700 uppercase mb-1">
                  Select Tracked Product
                </label>
                <select
                  value={selectedProductId}
                  onChange={(e) => {
                    setSelectedProductId(e.target.value);
                    const sel = products.find((p) => p.id === e.target.value);
                    if (sel) setTargetPrice(Math.round(sel.lowestPrice * 0.9));
                  }}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-xs font-mono font-medium text-slate-900 focus:outline-none focus:border-slate-800"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.brand} — {p.baseProductName} (Current: ₹{p.lowestPrice})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {preselectedProduct && (
              <div className="bg-slate-50 border border-slate-200 p-2.5 rounded-xs text-xs font-mono">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Targeting</span>
                <span className="font-bold text-slate-900">{preselectedProduct.baseProductName}</span>
                <span className="text-slate-500 block text-[11px] mt-0.5">
                  Current lowest ask: <strong className="text-emerald-700">{formatInr(currentPrice)}</strong>
                </span>
              </div>
            )}

            {/* Target Price */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-mono font-bold text-slate-700 uppercase">
                  Trigger Target Price
                </label>
                <span className="text-[10px] font-mono text-emerald-700 font-bold">
                  {Math.round(((currentPrice - targetPrice) / currentPrice) * 100)}% Discount Goal
                </span>
              </div>
              <div className="relative flex items-center">
                <span className="absolute left-3 text-xs font-mono text-slate-500 font-bold">₹</span>
                <input
                  type="number"
                  required
                  min={100}
                  max={50000}
                  step={50}
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xs pl-7 pr-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
                />
              </div>
            </div>

            {/* Channel Selection */}
            <div>
              <label className="block text-xs font-mono font-bold text-slate-700 uppercase mb-1">
                Notification Channel
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setNotificationChannel("whatsapp")}
                  className={`py-1.5 px-3 text-xs font-mono font-bold rounded-xs border text-center transition-colors ${
                    notificationChannel === "whatsapp"
                      ? "bg-slate-900 border-slate-900 text-white"
                      : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  WhatsApp Instant
                </button>
                <button
                  type="button"
                  onClick={() => setNotificationChannel("email")}
                  className={`py-1.5 px-3 text-xs font-mono font-bold rounded-xs border text-center transition-colors ${
                    notificationChannel === "email"
                      ? "bg-slate-900 border-slate-900 text-white"
                      : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  Email Digest
                </button>
              </div>
            </div>

            {/* Contact Input */}
            <div>
              <label className="block text-xs font-mono font-bold text-slate-700 uppercase mb-1">
                {notificationChannel === "whatsapp" ? "WhatsApp 10-Digit Mobile" : "Email Address"}
              </label>
              <input
                type={notificationChannel === "whatsapp" ? "tel" : "email"}
                required
                placeholder={
                  notificationChannel === "whatsapp" ? "e.g. 9876543210" : "name@example.com"
                }
                value={contactValue}
                onChange={(e) => setContactValue(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:border-slate-800"
              />
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                className="w-full py-2.5 px-4 bg-emerald-700 hover:bg-emerald-800 text-white font-mono text-xs font-bold uppercase tracking-wider rounded-xs transition-colors flex items-center justify-center gap-1.5 shadow-xs"
              >
                <Bell className="size-3.5" />
                <span>Arm Price Drop Monitor</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
