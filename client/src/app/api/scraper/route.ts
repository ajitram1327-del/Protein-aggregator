import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { exec, spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    // 1. Get database row counts
    const [pRes, vRes, oRes, plRes, uRes] = await Promise.all([
      supabase.from('products').select('*', { count: 'exact', head: true }),
      supabase.from('variants').select('*', { count: 'exact', head: true }),
      supabase.from('offers').select('*', { count: 'exact', head: true }),
      supabase.from('price_listings').select('*', { count: 'exact', head: true }),
      supabase.from('unmatched_products').select('*', { count: 'exact', head: true }),
    ]);

    const isVercel = process.env.VERCEL === '1';

    if (isVercel) {
      return NextResponse.json({
        success: true,
        status: {
          isRunning: false,
          counts: {
            products: pRes.count ?? 0,
            variants: vRes.count ?? 0,
            offers: oRes.count ?? 0,
            priceListings: plRes.count ?? 0,
            unmatched: uRes.count ?? 0,
          },
          recentLogs: [
            '[Vercel Serverless Environment]',
            'Local file system logs and scraper process control are only accessible in local development.',
            'Production scraping runs via external worker / scheduled automation.',
          ],
          logAvailable: false,
          lastCheckedAt: new Date().toISOString(),
        },
      });
    }

    // 2. Read recent scraper log lines if available (local development only)
    const rootDir = process.cwd();
    const possibleLogPaths = [
      path.join(rootDir, '..', 'scraper', 'scrapling_scraper', 'scraper_production.log'),
      path.join(rootDir, 'scraper', 'scrapling_scraper', 'scraper_production.log'),
    ];

    let logLines: string[] = [];
    let logFound = false;

    for (const logPath of possibleLogPaths) {
      if (fs.existsSync(/*turbopackIgnore: true*/ logPath)) {
        try {
          const content = fs.readFileSync(/*turbopackIgnore: true*/ logPath, 'utf-8');
          const allLines = content.trim().split(/\r?\n/);
          logLines = allLines.slice(-100); // Last 100 lines
          logFound = true;
          break;
        } catch (e) {
          // continue
        }
      }
    }

    // 3. Check if scraper process is currently running (local development only)
    const isWin = process.platform === 'win32';
    const checkCommand = isWin ? 'tasklist /FI "IMAGENAME eq python.exe"' : 'pgrep -f "python"';

    return new Promise<NextResponse>((resolve) => {
      exec(checkCommand, (err, stdout) => {
        const isRunning = isWin
          ? (stdout || '').toLowerCase().includes('python.exe')
          : !err && (stdout || '').trim().length > 0;

        resolve(
          NextResponse.json({
            success: true,
            status: {
              isRunning,
              counts: {
                products: pRes.count ?? 0,
                variants: vRes.count ?? 0,
                offers: oRes.count ?? 0,
                priceListings: plRes.count ?? 0,
                unmatched: uRes.count ?? 0,
              },
              recentLogs: logLines,
              logAvailable: logFound,
              lastCheckedAt: new Date().toISOString(),
            },
          })
        );
      });
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || 'Failed to fetch scraper status' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    if (process.env.VERCEL === '1') {
      return NextResponse.json(
        {
          success: false,
          error: 'Background process execution is disabled in the Vercel serverless environment. Run scrapers locally or trigger a worker.',
        },
        { status: 400 }
      );
    }

    const body = await request.json().catch(() => ({}));
    const action = body.action; // 'start_scrape' | 'purge_database' | 'stop_scrape'

    const rootDir = process.cwd();
    // Resolve project root (whether cwd is client or root)
    const projectRoot = fs.existsSync(/*turbopackIgnore: true*/ path.join(rootDir, 'scraper'))
      ? rootDir
      : path.join(rootDir, '..');

    const isWin = process.platform === 'win32';
    const pythonExe = isWin ? 'python.exe' : 'python3';
    const venvPython = path.join(
      projectRoot,
      'scraper',
      'scrapling_scraper',
      '.venv',
      isWin ? 'Scripts' : 'bin',
      pythonExe
    );

    if (action === 'purge_database') {
      const purgeScript = path.join(projectRoot, 'scripts', 'purge_database.py');
      return new Promise<NextResponse>((resolve) => {
        exec(`"${venvPython}" "${purgeScript}"`, { cwd: projectRoot }, (err, stdout, stderr) => {
          if (err) {
            resolve(
              NextResponse.json(
                { success: false, error: err.message, stderr },
                { status: 500 }
              )
            );
          } else {
            resolve(
              NextResponse.json({
                success: true,
                message: 'Catalogue and datapoints purged successfully.',
                output: stdout,
              })
            );
          }
        });
      });
    }

    if (action === 'start_scrape') {
      const engineScript = path.join(
        projectRoot,
        'scraper',
        'scrapling_scraper',
        'src',
        'scraper',
        'engine.py'
      );
      const cwd = path.join(projectRoot, 'scraper', 'scrapling_scraper');

      // Spawn detached background process
      const child = spawn(venvPython, [engineScript], {
        cwd,
        detached: true,
        stdio: 'ignore',
      });
      child.unref();

      return NextResponse.json({
        success: true,
        message: 'Omni-Channel Scraper engine started in background.',
        pid: child.pid,
      });
    }

    if (action === 'stop_scrape') {
      const killCommand = isWin ? 'taskkill /F /IM python.exe' : 'pkill -f "python"';
      return new Promise<NextResponse>((resolve) => {
        exec(killCommand, (err, stdout, stderr) => {
          resolve(
            NextResponse.json({
              success: true,
              message: 'Scraper background processes stopped.',
              output: stdout,
            })
          );
        });
      });
    }

    return NextResponse.json(
      { success: false, error: `Invalid action: ${action}` },
      { status: 400 }
    );
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || 'Operation failed' },
      { status: 500 }
    );
  }
}
