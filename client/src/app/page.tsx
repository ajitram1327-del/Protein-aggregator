import { getGroupedProducts } from "@/lib/products";
import { LandingHero } from "@/components/home/LandingHero";
import Link from "next/link";

export const revalidate = 60; // Revalidate cache every 60 seconds

export default async function Home() {
  const { products, errorMsg } = await getGroupedProducts();

  if (errorMsg) {
    return (
      <main id="main-content" className="flex flex-col items-center justify-center min-h-screen bg-slate-50 px-4 font-mono">
        <div className="max-w-lg w-full bg-white border border-slate-300 p-6 shadow-xs rounded-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-red-700 mb-2 flex items-center gap-1.5">
            <span>[DIAGNOSTIC]</span> Product Repository Query Error
          </div>
          <p className="text-xs text-slate-700 leading-relaxed">
            The terminal was unable to query product records from the database.
          </p>
          <div className="mt-3 p-3 bg-slate-100 border border-slate-200 text-[11px] text-slate-800 break-all font-mono">
            {errorMsg}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between">
            <span className="text-[10px] text-slate-500">Check NEXT_PUBLIC_SUPABASE_URL configuration</span>
            <Link
              href="/"
              className="px-3 py-1.5 bg-slate-900 text-white text-xs font-bold uppercase hover:bg-slate-800 rounded-sm"
            >
              Retry Connection
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return <LandingHero initialProducts={products} />;
}
