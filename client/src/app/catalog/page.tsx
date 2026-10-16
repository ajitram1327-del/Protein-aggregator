import { getGroupedProducts } from "@/lib/products";
import { CatalogView } from "@/components/catalog/CatalogView";
import Link from "next/link";

export const revalidate = 60; // 60s cache revalidation

interface PageProps {
  searchParams: Promise<{ category?: string; q?: string; search?: string; brand?: string }>;
}

export default async function CatalogPage({ searchParams }: PageProps) {
  const resolved = await searchParams;
  const queryParam = resolved.search || resolved.q;
  const { products, errorMsg } = await getGroupedProducts({
    silo: resolved.category,
    brand: resolved.brand,
    q: queryParam,
  });

  if (errorMsg) {
    return (
      <main id="main-content" className="flex flex-col items-center justify-center min-h-screen bg-slate-50 px-4 font-mono">
        <div className="max-w-lg w-full bg-white border border-slate-300 p-6 shadow-xs rounded-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-red-700 mb-2 flex items-center gap-1.5">
            <span>[DIAGNOSTIC]</span> Product Repository Query Error
          </div>
          <p className="text-xs text-slate-700 leading-relaxed">
            The catalog screener was unable to query product records from the database.
          </p>
          <div className="mt-3 p-3 bg-slate-100 border border-slate-200 text-[11px] text-slate-800 break-all font-mono">
            {errorMsg}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between">
            <Link
              href="/"
              className="text-xs font-bold text-slate-600 hover:text-slate-900 underline"
            >
              ← Return Home
            </Link>
            <a
              href="/catalog"
              className="px-3 py-1.5 bg-slate-900 text-white text-xs font-bold uppercase hover:bg-slate-800 rounded-sm"
            >
              Retry
            </a>
          </div>
        </div>
      </main>
    );
  }

  return <CatalogView initialProducts={products} initialCategory={resolved.category} />;
}
