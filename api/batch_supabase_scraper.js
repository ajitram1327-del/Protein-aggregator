import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import * as cheerio from 'cheerio';
import Groq from 'groq-sdk';
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config();
puppeteer.use(StealthPlugin());

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

// ====================================================================
// ALL 41 BRANDS — D2C + E-Commerce targets with fallback URLs
// ====================================================================
const ALL_BRANDS = [
    { brand: 'MuscleBlaze',         tier1: 'https://www.muscleblaze.com/products.json?limit=250',     tier2: 'https://www.muscleblaze.com/category/proteins' },
    { brand: 'Nakpro',              tier1: 'https://nakpro.com/products.json?limit=250',               tier2: 'https://nakpro.com/collections/all' },
    { brand: 'AS-IT-IS Nutrition',  tier1: 'https://asitisnutrition.com/products.json?limit=250',      tier2: 'https://asitisnutrition.com/collections/all' },
    { brand: 'Nutrabay',            tier1: 'https://nutrabay.com/products.json?limit=250',             tier2: 'https://nutrabay.com/collections/whey-protein' },
    { brand: 'Avvatar',             tier1: 'https://avvatarindia.com/products.json?limit=250',         tier2: 'https://avvatarindia.com/collections/all' },
    { brand: 'TrueBasics',          tier1: 'https://truebasics.com/products.json?limit=250',           tier2: 'https://truebasics.com/collections/proteins' },
    { brand: 'Cosmix',              tier1: 'https://cosmix.in/products.json?limit=250',                tier2: 'https://cosmix.in/collections/all' },
    { brand: 'MyFitFuel',           tier1: 'https://www.myfitfuel.in/products.json?limit=250',         tier2: 'https://www.myfitfuel.in/collections/all' },
    { brand: 'Foodstrong',          tier1: 'https://foodstrong.co/products.json?limit=250',            tier2: 'https://foodstrong.co/collections/all' },
    { brand: 'Naturaltein',         tier1: 'https://naturaltein.in/products.json?limit=250',           tier2: 'https://naturaltein.in/collections/all' },
    { brand: 'The Whole Truth',     tier1: 'https://thewholetruthfoods.com/products.json?limit=250',  tier2: 'https://thewholetruthfoods.com/collections/protein' },
    { brand: 'Amul',                tier1: 'https://shop.amul.com/products.json?limit=250',            tier2: 'https://shop.amul.com/en/browse/fitness-nutrition' },
    { brand: 'Mille Supergrain',    tier1: 'https://millesupergrain.com/products.json?limit=250',     tier2: 'https://millesupergrain.com/collections/all' },
    { brand: 'Yogabar',             tier1: 'https://www.yogabars.in/products.json?limit=250',          tier2: 'https://www.yogabars.in/collections/proteins' },
    { brand: 'GetMyMettle',         tier1: 'https://getmymettle.com/products.json?limit=250',          tier2: 'https://getmymettle.com/collections/all' },
    { brand: 'Dame Health',         tier1: 'https://damehealth.in/products.json?limit=250',            tier2: 'https://damehealth.in/collections/all' },
    { brand: 'Optimum Nutrition',   tier1: 'https://www.optimumnutrition.co.in/products.json?limit=250', tier2: 'https://www.optimumnutrition.co.in/collections/whey-protein' },
    { brand: 'Myprotein',           tier1: 'https://www.myprotein.com/products.json?limit=250',        tier2: 'https://www.myprotein.com/sportsnfitness/whey-protein.list' },
    { brand: 'GNC India',           tier1: 'https://www.guardian.in/products.json?limit=250',          tier2: 'https://www.guardian.in/collections/proteins' },
    { brand: 'Muscletech',          tier1: 'https://muscletech.in/products.json?limit=250',            tier2: 'https://muscletech.in/collections/protein' },
    { brand: 'Plix',                tier1: 'https://www.plixlife.com/products.json?limit=250',         tier2: 'https://www.plixlife.com/collections/protein-powder' },
    { brand: 'Kapiva',              tier1: 'https://kapiva.in/products.json?limit=250',                tier2: 'https://kapiva.in/collections/protein' },
    { brand: 'Boldfit',             tier1: 'https://boldfit.in/products.json?limit=250',               tier2: 'https://boldfit.in/collections/protein' },
    { brand: 'Fast&Up',             tier1: 'https://www.fastandup.in/products.json?limit=250',         tier2: 'https://www.fastandup.in/collections/protein' },
    { brand: 'bGREEN',              tier1: 'https://bgreen.in/products.json?limit=250',                tier2: 'https://bgreen.in/collections/all' },
    { brand: 'Bigmuscles Nutrition',tier1: 'https://bigmusclesnutrition.com/products.json?limit=250',  tier2: 'https://bigmusclesnutrition.com/collections/whey-protein' },
    { brand: 'Fuel One',            tier1: 'https://fuelone.in/products.json?limit=250',               tier2: 'https://fuelone.in/collections/all' },
    { brand: 'Osoaa',               tier1: 'https://www.osoaa.com/products.json?limit=250',            tier2: 'https://www.osoaa.com/collections/whey-protein' },
    { brand: 'Nutrabox',            tier1: 'https://www.nutrabox.in/products.json?limit=250',          tier2: 'https://www.nutrabox.in/collections/all' },
    { brand: 'Trunativ',            tier1: 'https://trunativ.com/products.json?limit=250',             tier2: 'https://trunativ.com/collections/all' },
    { brand: 'XLR8',                tier1: 'https://www.xlr8nutrition.in/products.json?limit=250',     tier2: 'https://www.xlr8nutrition.in/collections/protein' },
    { brand: 'SuperYou',            tier1: 'https://www.superyou.life/products.json?limit=250',        tier2: 'https://www.superyou.life/collections/all' },
    { brand: 'BeastLife',           tier1: 'https://beastlife.in/products.json?limit=250',             tier2: 'https://beastlife.in/collections/all' },
    { brand: 'Divine Nutrition',    tier1: 'https://www.divinenutrition.in/products.json?limit=250',   tier2: 'https://www.divinenutrition.in/collections/all' },
    { brand: 'GM Nutrition',        tier1: 'https://gmnutrition.in/products.json?limit=250',           tier2: 'https://gmnutrition.in/collections/all' },
    { brand: 'MB PROWL',            tier1: 'https://mbprowl.com/products.json?limit=250',              tier2: 'https://mbprowl.com/collections/all' },
    { brand: 'HRX Nutrition',       tier1: null,                                                       tier2: 'https://www.flipkart.com/hrx-nutrition-protein/pr?sid=hcw%2F8po' },
    { brand: 'Dymatize',            tier1: null,                                                       tier2: 'https://www.healthkart.com/brands/dymatize' },
    { brand: 'Isopure',             tier1: null,                                                       tier2: 'https://www.healthkart.com/brands/isopure' },
    { brand: 'Ultimate Nutrition',  tier1: null,                                                       tier2: 'https://www.healthkart.com/brands/ultimate-nutrition' },
    { brand: 'Atom',                tier1: 'https://asitisnutrition.com/products.json?limit=250',      tier2: 'https://asitisnutrition.com/collections/atom' },
];

const BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*',
};

function isTargetProduct(title) {
    const t = title.toLowerCase();
    if (t.match(/shaker|bottle|t-shirt|bag|cap|combo|bundle|gymwear|crockery|cookware/)) return false;
    return !!/protein|whey|isolate|casein|plant|pea|creatine|mass gainer|weight gainer|pre[\s-]?workout/i.test(t);
}

function guessSubCategory(title) {
    const t = title.toLowerCase();
    if (t.includes('mass') || t.includes('gainer') || t.includes('weight gainer')) return 'Mass Gainer';
    if (t.includes('creatine')) return 'Creatine';
    if (t.includes('pre-workout') || t.includes('pre workout')) return 'Pre-Workout';
    if (t.includes('isolate') || t.includes('wpi')) return 'Whey Isolate';
    if (t.includes('concentrate') || t.includes('wpc')) return 'Whey Concentrate';
    if (t.includes('casein')) return 'Casein';
    if (t.includes('plant') || t.includes('pea') || t.includes('vegan') || t.includes('brown rice')) return 'Plant Protein';
    if (t.includes('yeast') || t.includes('fermented')) return 'Fermented Yeast';
    return 'Whey Blend';
}

function classifyProteinSource(title) {
    const t = title.toLowerCase();
    if (t.includes('plant') || t.includes('pea') || t.includes('brown rice') || t.includes('vegan')) return 'Plant';
    if (t.includes('yeast') || t.includes('fermented')) return 'Yeast';
    return 'Whey';
}

async function upsertProduct(brandName, title, price, imageUrl, variantTitle = 'Default') {
    if (!isTargetProduct(title)) return false;

    const subCat = guessSubCategory(title);
    const pSource = classifyProteinSource(title);
    const silo = subCat === 'Mass Gainer' ? 'mass_gainer' : subCat === 'Creatine' ? 'creatine' : subCat === 'Pre-Workout' ? 'pre_workout' : 'protein';
    let baseName = title.split(',')[0].split('|')[0].split('-')[0].trim().substring(0, 80);

    const { data: productData, error: pErr } = await supabase
        .from('products')
        .upsert({ brand: brandName, base_name: baseName, category_silo: silo, protein_source: pSource, image_url: imageUrl }, { onConflict: 'brand,base_name' })
        .select().single();
    if (pErr || !productData) return false;

    let weightMatch = (variantTitle + ' ' + title).match(/(\d+(?:\.\d+)?)\s*(kg|g|lbs|lb)/i);
    let weightGrams = 1000;
    if (weightMatch) {
        const val = parseFloat(weightMatch[1]), unit = weightMatch[2].toLowerCase();
        if (unit === 'kg') weightGrams = val * 1000;
        else if (unit === 'g') weightGrams = val;
        else if (unit === 'lb' || unit === 'lbs') weightGrams = val * 453.592;
    }
    const servingsCount = Math.max(1, Math.floor(weightGrams / 33));
    const trueCost = price / (servingsCount * 24);
    const skuId = `sku-${brandName.replace(/\W/g, '')}-${Buffer.from(baseName + variantTitle).toString('base64').substring(0, 20)}`;

    await supabase.from('variants').upsert({
        product_id: productData.id, sku_id: skuId,
        flavor: variantTitle !== 'Default Title' ? variantTitle : 'Unflavored',
        weight_grams: weightGrams, lowest_price_inr: price,
        servings_count: servingsCount, best_value_metric: trueCost,
        raw_json_data: { source: 'Scraper', packaging: { weightGrams }, pricing: { lowestPriceInr: price } }
    }, { onConflict: 'sku_id' });
    return true;
}

// ===================== TIER 1 =====================
async function tier1_shopify(brand, url) {
    let delay = 1000;
    for (let i = 0; i < 3; i++) {
        try {
            const res = await fetch(url, { headers: BROWSER_HEADERS });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!data?.products?.length) throw new Error('Empty product array');

            let count = 0;
            for (const item of data.products) {
                if (!item.title || !isTargetProduct(item.title)) continue;
                const image = item.images?.[0]?.src || '';
                for (const v of item.variants) {
                    const price = parseFloat(v.price);
                    if (!price || isNaN(price)) continue;
                    if (await upsertProduct(brand, item.title, price, image, v.title)) count++;
                }
            }
            return { success: true, count };
        } catch (err) {
            await new Promise(r => setTimeout(r, delay));
            delay *= 2;
        }
    }
    return { success: false, count: 0 };
}

// ===================== TIER 2 + 3 =====================
async function tier2_stealth(browser, brand, url) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent(BROWSER_HEADERS['User-Agent']);

    try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 35000 });
        await new Promise(r => setTimeout(r, 4000));

        const html = await page.content();
        const $ = cheerio.load(html);
        $('nav, footer, script, style, noscript, iframe, svg, header, .header, .footer, .menu, .navbar').remove();

        let strippedContent = '';
        $('a, .product, .grid-item, article, li, [class*="product"], [class*="item"]').each((_, el) => {
            const text = $(el).text().replace(/\s+/g, ' ').trim();
            const href = $(el).attr('href') || '';
            const img = $(el).find('img').attr('src') || '';
            if (text.length > 5 && text.length < 300) {
                strippedContent += `[TEXT: ${text} | LINK: ${href} | IMG: ${img}]\n`;
            }
        });

        if (strippedContent.length < 100) return { success: false, count: 0 };

        // Tier 3 — LLM extraction
        const completion = await groq.chat.completions.create({
            messages: [
                {
                    role: 'system',
                    content: `You are a strict data extractor. From the provided text, extract all supplement products that are: protein powder, whey protein, plant protein, creatine, mass gainer, or pre-workout. 
Return ONLY a valid JSON array of objects with exactly these keys: "name" (string), "price_inr" (number or null), "weight_grams" (number or null), "flavor" (string or null), "image_url" (string or null).
Do not include accessories, shakers, vitamins, or any other products. Do not return markdown. Only pure JSON.`
                },
                { role: 'user', content: `Brand: ${brand}\n\n${strippedContent.substring(0, 14000)}` }
            ],
            model: 'qwen/qwen3.8-27b',
            temperature: 0,
        });

        let products = [];
        try {
            const raw = completion.choices[0]?.message?.content || '[]';
            const jsonStart = raw.indexOf('[');
            const jsonEnd = raw.lastIndexOf(']') + 1;
            products = JSON.parse(raw.substring(jsonStart, jsonEnd));
        } catch (e) {
            return { success: false, count: 0 };
        }

        let count = 0;
        for (const p of products) {
            if (!p.name || !p.price_inr) continue;
            const inserted = await upsertProduct(brand, p.name, p.price_inr, p.image_url || '', p.flavor || 'Default');
            if (inserted) count++;
        }
        return { success: true, count };
    } catch (err) {
        return { success: false, count: 0, error: err.message };
    } finally {
        await page.close();
    }
}

// ===================== LIVE TERMINAL DASHBOARD =====================
const BRAND_TOTAL = ALL_BRANDS.length;
const brandStatus = {}; // brand -> { state: 'pending'|'running'|'done'|'failed', tier, count }
ALL_BRANDS.forEach(b => { brandStatus[b.brand] = { state: 'pending', tier: '-', count: 0 }; });

const C = {
    reset: '\x1b[0m', bold: '\x1b[1m', dim: '\x1b[2m',
    green: '\x1b[32m', red: '\x1b[31m', yellow: '\x1b[33m',
    cyan: '\x1b[36m', white: '\x1b[37m', blue: '\x1b[34m',
    clearLine: '\x1b[2K', up: (n) => `\x1b[${n}A`,
    saveCursor: '\x1b[s', restoreCursor: '\x1b[u',
};

let dashboardLines = 0;
let stats = { tier1: 0, tier2: 0, failed: 0, total: 0, done: 0 };

function progressBar(done, total, width = 36) {
    const pct = Math.min(done / total, 1);
    const filled = Math.round(pct * width);
    const bar = '█'.repeat(filled) + '░'.repeat(width - filled);
    return `${C.cyan}${bar}${C.reset} ${C.bold}${done}/${total}${C.reset}`;
}

function stateIcon(state) {
    if (state === 'done')    return `${C.green}✓${C.reset}`;
    if (state === 'failed')  return `${C.red}✗${C.reset}`;
    if (state === 'running') return `${C.yellow}⟳${C.reset}`;
    return `${C.dim}·${C.reset}`;
}

function tierBadge(tier) {
    if (tier === 'T1') return `${C.green}T1 API ${C.reset}`;
    if (tier === 'T2') return `${C.yellow}T2 DOM ${C.reset}`;
    return `${C.dim}  -   ${C.reset}`;
}

function renderDashboard() {
    const lines = [];
    lines.push(`${C.bold}${C.blue}╔══════════════════════════════════════════════════════════╗${C.reset}`);
    lines.push(`${C.bold}${C.blue}║       PROTEIN AGGREGATOR — LIVE SCRAPE DASHBOARD         ║${C.reset}`);
    lines.push(`${C.bold}${C.blue}╚══════════════════════════════════════════════════════════╝${C.reset}`);
    lines.push(`  Progress  ${progressBar(stats.done, BRAND_TOTAL)}`);
    lines.push(`  ${C.green}T1 wins: ${stats.tier1}${C.reset}   ${C.yellow}T2 wins: ${stats.tier2}${C.reset}   ${C.red}Failed: ${stats.failed}${C.reset}   ${C.bold}Total Products: ${stats.total}${C.reset}`);
    lines.push(`  ${'─'.repeat(56)}`);
    lines.push(`  ${'Brand'.padEnd(24)} ${'Status'.padEnd(10)} ${'Tier'.padEnd(9)} ${'Products'}`);
    lines.push(`  ${'─'.repeat(56)}`);

    for (const b of ALL_BRANDS) {
        const s = brandStatus[b.brand];
        const icon = stateIcon(s.state);
        const name = b.brand.padEnd(24).substring(0, 24);
        const status = s.state === 'running' ? `${C.yellow}scraping${C.reset}` :
                       s.state === 'done'    ? `${C.green}done    ${C.reset}` :
                       s.state === 'failed'  ? `${C.red}failed  ${C.reset}` :
                                              `${C.dim}waiting ${C.reset}`;
        const count = s.count > 0 ? `${C.bold}${s.count}${C.reset}` : `${C.dim}0${C.reset}`;
        lines.push(`  ${icon} ${name} ${status} ${tierBadge(s.tier)} ${count}`);
    }

    lines.push(`  ${'─'.repeat(56)}`);
    lines.push(`  ${C.dim}Last updated: ${new Date().toLocaleTimeString()}${C.reset}`);

    // Move cursor up to overwrite previous render
    if (dashboardLines > 0) {
        process.stdout.write(C.up(dashboardLines));
    }
    const output = lines.map(l => `${C.clearLine}${l}`).join('\n') + '\n';
    process.stdout.write(output);
    dashboardLines = lines.length;
}

// ===================== MAIN ORCHESTRATOR =====================
async function runUnifiedScraper() {
    // Clear screen and hide cursor for clean dashboard
    process.stdout.write('\x1b[2J\x1b[H\x1b[?25l');

    renderDashboard();

    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
    });

    const failed_brands = [];

    for (let i = 0; i < ALL_BRANDS.length; i++) {
        const target = ALL_BRANDS[i];

        // Mark as running
        brandStatus[target.brand].state = 'running';
        renderDashboard();

        let result = { success: false, count: 0 };

        // Tier 1: Shopify API
        if (target.tier1) {
            result = await tier1_shopify(target.brand, target.tier1);
            if (result.success && result.count > 0) {
                brandStatus[target.brand] = { state: 'done', tier: 'T1', count: result.count };
                stats.tier1++; stats.total += result.count; stats.done++;
                renderDashboard();
                continue;
            }
        }

        // Tier 2+3: Auto-escalate — no user prompt
        brandStatus[target.brand].tier = 'T2';
        renderDashboard();
        if (target.tier2) {
            result = await tier2_stealth(browser, target.brand, target.tier2);
            if (result.success && result.count > 0) {
                brandStatus[target.brand] = { state: 'done', tier: 'T2', count: result.count };
                stats.tier2++; stats.total += result.count; stats.done++;
                renderDashboard();
                continue;
            }
        }

        brandStatus[target.brand] = { state: 'failed', tier: '-', count: 0 };
        stats.failed++; stats.done++;
        failed_brands.push(target.brand);
        renderDashboard();
    }

    await browser.close();

    // Restore cursor
    process.stdout.write('\x1b[?25h');

    // Final summary below dashboard
    process.stdout.write(`\n${C.bold}${C.green}═══ SCRAPE COMPLETE ═══${C.reset}\n`);
    process.stdout.write(`  Tier 1 wins  : ${stats.tier1}\n`);
    process.stdout.write(`  Tier 2 wins  : ${stats.tier2}\n`);
    process.stdout.write(`  Failed       : ${stats.failed}\n`);
    process.stdout.write(`  Total Products in DB: ${C.bold}${stats.total}${C.reset}\n`);
    if (failed_brands.length) {
        process.stdout.write(`  Failed brands: ${C.red}${failed_brands.join(', ')}${C.reset}\n`);
    }
}

runUnifiedScraper();

