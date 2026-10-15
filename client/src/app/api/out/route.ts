import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabaseAdmin";
import { outboundRatelimit } from "@/lib/ratelimit";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const SIGNING_SECRET = process.env.URL_SIGNING_SECRET || "proteindex-secret-signing-key-32ch";

function verifyStoreToken(token: string): { listingId: string; isValid: boolean } {
  try {
    const raw = Buffer.from(token, "base64url").toString("utf-8");
    const [listingId, expiresAtStr, signature] = raw.split(":");
    if (!listingId || !expiresAtStr || !signature) {
      return { listingId: "", isValid: false };
    }

    const expiresAt = parseInt(expiresAtStr, 10);
    if (isNaN(expiresAt) || Date.now() > expiresAt) {
      return { listingId: "", isValid: false };
    }

    const expectedSignature = crypto
      .createHmac("sha256", SIGNING_SECRET)
      .update(`${listingId}:${expiresAtStr}`)
      .digest("hex");

    return {
      listingId,
      isValid: signature === expectedSignature,
    };
  } catch {
    return { listingId: "", isValid: false };
  }
}

export async function GET(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1";
  const { success } = await outboundRatelimit.limit(ip);

  if (!success) {
    return new NextResponse("Click rate limit exceeded. Please wait a moment.", { status: 429 });
  }

  const { searchParams } = new URL(req.url);
  const token = searchParams.get("token");

  if (!token) {
    return NextResponse.redirect(new URL("/", req.url));
  }

  const { listingId, isValid } = verifyStoreToken(token);
  if (!isValid || !listingId) {
    return new NextResponse("This link has expired or is invalid.", { status: 400 });
  }

  // Look up listing in price_listings
  const { data: listing, error } = await supabaseAdmin
    .from("price_listings")
    .select("listing_url, source_url")
    .eq("id", listingId)
    .single();

  let targetUrl = listing?.listing_url || listing?.source_url;

  // Fallback to offers table if not found
  if (!targetUrl) {
    const { data: offer } = await supabaseAdmin
      .from("offers")
      .select("url")
      .eq("id", listingId)
      .single();
    targetUrl = offer?.url;
  }

  if (!targetUrl || targetUrl.trim() === "" || targetUrl.startsWith("#")) {
    return NextResponse.redirect(new URL("/", req.url));
  }

  return NextResponse.redirect(targetUrl, {
    status: 302,
    headers: {
      "Referrer-Policy": "no-referrer-when-downgrade",
      "Cache-Control": "no-store, max-age=0",
    },
  });
}
