import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const isRedisConfigured = Boolean(
  process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN
);

const redis = isRedisConfigured
  ? new Redis({
      url: process.env.UPSTASH_REDIS_REST_URL!,
      token: process.env.UPSTASH_REDIS_REST_TOKEN!,
    })
  : null;

// Screener API: Max 40 requests per 60 seconds per IP
export const apiRatelimit = redis
  ? new Ratelimit({
      redis,
      limiter: Ratelimit.slidingWindow(40, "60 s"),
      analytics: true,
      prefix: "@proteindex/ratelimit/api",
    })
  : {
      limit: async (_key: string) => ({
        success: true,
        limit: 40,
        remaining: 39,
        reset: Date.now() + 60000,
      }),
    };

// Outbound Store Link Redirector: Max 15 clicks per 60 seconds
export const outboundRatelimit = redis
  ? new Ratelimit({
      redis,
      limiter: Ratelimit.slidingWindow(15, "60 s"),
      analytics: true,
      prefix: "@proteindex/ratelimit/outbound",
    })
  : {
      limit: async (_key: string) => ({
        success: true,
        limit: 15,
        remaining: 14,
        reset: Date.now() + 60000,
      }),
    };
