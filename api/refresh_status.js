// Reads the scraper task log, parses state, rewrites scraping_status.md
import fs from 'fs';

const LOG_PATH = String.raw`C:\Users\ajith\.gemini\antigravity\brain\584882f0-3237-4b78-af13-adbc9b6147be\.system_generated\tasks\task-514.log`;
const ARTIFACT_PATH = String.raw`C:\Users\ajith\.gemini\antigravity\brain\584882f0-3237-4b78-af13-adbc9b6147be\scraping_status.md`;

const ALL_BRANDS = [
    'MuscleBlaze','Nakpro','AS-IT-IS Nutrition','Nutrabay','Avvatar','TrueBasics',
    'Cosmix','MyFitFuel','Foodstrong','Naturaltein','The Whole Truth','Amul',
    'Mille Supergrain','Yogabar','GetMyMettle','Dame Health','Optimum Nutrition',
    'Myprotein','GNC India','Muscletech','Plix','Kapiva','Boldfit','Fast&Up',
    'bGREEN','Bigmuscles Nutrition','Fuel One','Osoaa','Nutrabox','Trunativ',
    'XLR8','SuperYou','BeastLife','Divine Nutrition','GM Nutrition','MB PROWL',
    'HRX Nutrition','Dymatize','Isopure','Ultimate Nutrition','Atom'
];

function parseLog(raw) {
    const lines = raw.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').split('\n'); // strip ANSI
    const status = {};
    let t1 = 0, t2 = 0, failed = 0, total = 0;
    
    for (const line of lines) {
        const l = line.trim();

        for (const brand of ALL_BRANDS) {
            if (!l.includes(brand)) continue;
            if (l.includes('failed') || l.includes('Failed')) {
                status[brand] = { state: 'failed', tier: '-', count: 0 };
                if (!status[brand]?.counted) { failed++; status[brand].counted = true; }
            } else if (l.includes('Tier1') || l.includes('T1 API')) {
                const m = l.match(/(\d+)\s*products?/);
                const count = m ? parseInt(m[1]) : 0;
                status[brand] = { state: 'done', tier: 'T1', count };
                t1++; total += count;
            } else if (l.includes('Tier2') || l.includes('T2 DOM')) {
                const m = l.match(/(\d+)\s*products?/);
                const count = m ? parseInt(m[1]) : 0;
                status[brand] = { state: 'done', tier: 'T2', count };
                t2++; total += count;
            } else if (l.includes('scraping')) {
                if (!status[brand]) status[brand] = { state: 'running', tier: '-', count: 0 };
            }
        }

        // Parse summary stats line
        const statsMatch = l.match(/T1 wins:\s*(\d+).*T2 wins:\s*(\d+).*Failed:\s*(\d+).*Total Products:\s*(\d+)/);
        if (statsMatch) {
            t1 = parseInt(statsMatch[1]);
            t2 = parseInt(statsMatch[2]);
            failed = parseInt(statsMatch[3]);
            total = parseInt(statsMatch[4]);
        }
    }

    const done = t1 + t2 + failed;
    return { status, t1, t2, failed, total, done };
}

function bar(done, total, width = 30) {
    const pct = total > 0 ? Math.min(done / total, 1) : 0;
    const filled = Math.round(pct * width);
    return '█'.repeat(filled) + '░'.repeat(width - filled) + ` ${done}/${total}`;
}

function stateEmoji(state) {
    if (state === 'done')    return '✅';
    if (state === 'failed')  return '❌';
    if (state === 'running') return '⚙️';
    return '⏳';
}

function generateMarkdown(parsed, isComplete) {
    const { status, t1, t2, failed, total, done } = parsed;
    const pct = ALL_BRANDS.length > 0 ? Math.round((done / ALL_BRANDS.length) * 100) : 0;
    const now = new Date().toLocaleTimeString('en-IN');

    const rows = ALL_BRANDS.map(brand => {
        const s = status[brand] || { state: 'waiting', tier: '-', count: 0 };
        const emoji = stateEmoji(s.state);
        const tier = s.tier !== '-' ? `\`${s.tier}\`` : '-';
        const count = s.count > 0 ? `**${s.count}**` : '0';
        const statusLabel = s.state === 'done' ? 'Done' : s.state === 'failed' ? 'Failed' : s.state === 'running' ? '⚙️ Active' : 'Waiting';
        return `| ${emoji} | ${brand} | ${statusLabel} | ${tier} | ${count} |`;
    }).join('\n');

    return `# Live Scraping Status Dashboard
> 🔄 Last refreshed: **${now}** — ${isComplete ? '🏁 **COMPLETE**' : '⚙️ **IN PROGRESS**'}

## Overall Progress
\`${bar(done, ALL_BRANDS.length)}\` — **${pct}%**

| Metric | Value |
|:---|:---|
| ✅ Tier 1 wins (Fast API) | **${t1}** |
| 🔶 Tier 2 wins (Stealth Chromium + LLM) | **${t2}** |
| ❌ Failed (both tiers) | **${failed}** |
| 📦 Total Products Uploaded to DB | **${total}** |

---

## Per-Brand Status

| | Brand | Status | Tier | Products |
|:---:|:---|:---|:---:|---:|
${rows}`;
}

const raw = fs.existsSync(LOG_PATH) ? fs.readFileSync(LOG_PATH, 'utf8') : '';
const parsed = parseLog(raw);
const isComplete = raw.includes('SCRAPE COMPLETE') || raw.includes('UNIFIED SCRAPE COMPLETED');
const md = generateMarkdown(parsed, isComplete);
fs.writeFileSync(ARTIFACT_PATH, md, 'utf8');
console.log(`[${new Date().toLocaleTimeString()}] Refreshed scraping_status.md — ${parsed.done}/${ALL_BRANDS.length} done, ${parsed.total} products`);
