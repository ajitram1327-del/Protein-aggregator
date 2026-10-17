/**
 * Outbound Affiliate Route Sanitizer & Monetization Engine (PRD Section 7.2)
 *
 * Appends Cuelinks/subid parameters to outgoing merchant URLs while stripping
 * transient tracking, session IDs, and competitor referral parameters.
 */

const COMPETITOR_AFFILIATE_PARAMS = [
  'tag',          // Amazon Associate Tag
  'ascsubtag',    // Amazon Subtag
  'affid',        // Flipkart/HealthKart
  'affExtParam1', // Flipkart
  'affExtParam2', // Flipkart
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'gclid',
  'fbclid',
  'ref',
  'ref_',
  '_encoding',
];

export interface AffiliateMeta {
  rawUrl: string;
  sanitizedUrl: string;
  affiliateUrl: string;
  platform: string;
}

export function generateAffiliateUrl(rawUrl: string, platform: string = 'direct'): string {
  if (!rawUrl || rawUrl.trim() === '' || rawUrl.startsWith('#')) {
    return '#';
  }

  try {
    const url = new URL(rawUrl);

    // 1. Strip competitor tracking parameters
    for (const param of COMPETITOR_AFFILIATE_PARAMS) {
      url.searchParams.delete(param);
    }

    const cueLinksPubId = process.env.NEXT_PUBLIC_CUELINKS_PUB_ID;

    // Direct brand store or local fallback
    if (!cueLinksPubId) {
      return url.toString();
    }

    // Wrap via affiliate network aggregator
    const baseUrl = 'https://linksredirect.com/';
    const affiliateSubId = 'proteindex_web';
    return `${baseUrl}?pub_id=${cueLinksPubId}&url=${encodeURIComponent(url.toString())}&subid=${affiliateSubId}`;
  } catch {
    return rawUrl;
  }
}
