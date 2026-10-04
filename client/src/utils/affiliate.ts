/**
 * Outbound Affiliate Route Sanitizer & Monetization Engine (PRD Section 7.2)
 * Injects canonical monetization tags for Amazon and wraps network links via CueLinks.
 * Hardened against XSS (protocol injection), double-wrapping, competitor tags, and malformed URLs.
 */

const DANGEROUS_PROTOCOLS = new Set(['javascript:', 'data:', 'file:', 'vbscript:', 'blob:']);
const COMPETITOR_AFFILIATE_PARAMS = [
  'tag',
  'ascsubtag',
  'linkCode',
  'creative',
  'creativeASIN',
  'ref_',
  'ref',
  'pf_rd_r',
  'pf_rd_p',
  'pf_rd_m',
  'pf_rd_s',
  'pf_rd_t',
  'pf_rd_i',
];

const NETWORK_PARTNERS = [
  'healthkart',
  'flipkart',
  'tata1mg',
  '1mg',
  'netmeds',
  'pharmeasy',
  'hyugalife',
  'myprotein',
];

export function generateAffiliateUrl(rawUrl: string, platform: string = 'direct'): string {
  if (!rawUrl || typeof rawUrl !== 'string') return '';
  const trimmedUrl = rawUrl.trim();
  if (!trimmedUrl) return '';

  try {
    let normalizedInput = trimmedUrl;

    // Handle protocol-relative URLs
    if (normalizedInput.startsWith('//')) {
      normalizedInput = `https:${normalizedInput}`;
    } else {
      const schemeMatch = normalizedInput.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/);
      if (schemeMatch) {
        const scheme = schemeMatch[1].toLowerCase() + ':';
        if (DANGEROUS_PROTOCOLS.has(scheme) || (scheme !== 'http:' && scheme !== 'https:')) {
          return '';
        }
      } else {
        // Missing schema prefix (e.g., 'amazon.in/dp/...' or 'www.healthkart.com/...')
        if (
          normalizedInput.includes('/') ||
          normalizedInput.includes('.') ||
          normalizedInput.startsWith('www.')
        ) {
          normalizedInput = `https://${normalizedInput}`;
        } else {
          return '';
        }
      }
    }

    const url = new URL(normalizedInput);

    // SECURITY CHECK: Enforce strictly http: or https: schemas to prevent XSS / protocol injection
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return '';
    }

    // Defensive platform normalization & auto-detection from hostname
    const platformStr = String(platform || 'direct').toLowerCase();
    const normalizedPlatform = platformStr.replace(/[\s_-]+/g, '');
    const hostname = url.hostname.toLowerCase();

    const isAmazon =
      normalizedPlatform.includes('amazon') ||
      hostname.includes('amazon.') ||
      hostname === 'amzn.to';

    const isNetworkPartner =
      NETWORK_PARTNERS.some((p) => normalizedPlatform.includes(p) || hostname.includes(p));

    // Prevent double-wrapping if already redirected through CueLinks or affiliate aggregator
    if (hostname.includes('linksredirect.com') || hostname.includes('cuelinks.com')) {
      return url.toString();
    }

    if (isAmazon) {
      const amazonTag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG || 'proteindex-21';

      // Strip competitor affiliate and transient tracking parameters
      for (const param of COMPETITOR_AFFILIATE_PARAMS) {
        url.searchParams.delete(param);
      }

      // Inject canonical Proteindex associate tag
      url.searchParams.set('tag', amazonTag);
      return url.toString();
    }

    if (isNetworkPartner) {
      const cueLinksPubId = process.env.NEXT_PUBLIC_CUELINKS_ID || '123456';
      const affiliateSubId = 'proteindex_web';
      const baseUrl = 'https://linksredirect.com/';

      // Wrap target URL via CueLinks
      return `${baseUrl}?pub_id=${cueLinksPubId}&url=${encodeURIComponent(url.toString())}&subid=${affiliateSubId}`;
    }

    // Default: Clean direct brand URL
    return url.toString();
  } catch {
    // Return empty string on malformed URLs to prevent rendering broken or dangerous hrefs
    return '';
  }
}
