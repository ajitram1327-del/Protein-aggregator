# Anti-AI-Slop: Field Guide and Rule Set for UI and Frontend Iterations

Written from the perspective of a senior engineer reviewing sites. Part 1 lists what gives AI-built sites away, Part 2 lists what human-crafted sites do differently, and Part 3 is the rule set to follow for all UI and frontend work.

---

## Part 1: AI-Generated Website Red Flags

### 1.1 Visual Design Patterns

- **Purple/indigo-to-blue gradients** on hero text, buttons, and backgrounds (Tailwind's `indigo-500` → `purple-600` is the single most recognizable tell).
- **Dark mode "glow" aesthetic**: near-black background, translucent cards, soft neon blurs behind the hero, glassmorphism (`backdrop-blur`) applied everywhere.
- **Gradient text on the key word of the headline** ("Build faster with *AI-powered insights*").
- **Same radius, same shadow on everything**: `rounded-xl` or `rounded-2xl` plus `shadow-lg` on every card, button, and input. No hierarchy of elevation.
- **Default typography**: Inter (or system sans) for everything, Geist in newer builds. Weights limited to 400/600/700, no display face, no real type scale, headings differ from body only by size.
- **Icon monoculture**: Lucide or Heroicons, always in a rounded-square tinted badge above a card title.
- **Safe, evenly spaced palette**: one accent, grays from the framework scale, no considered neutrals (pure `gray-500` text rather than tinted neutrals).
- **Uniform spacing**: `py-24`, `gap-8`, `p-6` repeated everywhere, so every section has the same vertical rhythm and nothing feels emphasized.
- **Emoji as icons or decoration** (🚀 ✨ 📊 in headings and feature cards).
- **Decorative blobs, grid/dot backgrounds, and floating orbs** with no relationship to the content.
- **Stock-feeling imagery**: Unsplash placeholders, gradient rectangles standing in for screenshots, or a fake dashboard mockup built from divs.

### 1.2 Component and UI Patterns

- **Predictable section order**: Hero → logo bar → 3-feature grid → how it works (1-2-3) → testimonials → pricing (3 tiers, middle one "Popular") → FAQ accordion → CTA banner → footer.
- **The pill badge above the hero headline** ("✨ Now in beta", "New: v2.0 is here").
- **Two hero buttons**: filled primary plus ghost/outline secondary ("Get Started" / "Learn More").
- **Feature cards**: icon, bold title, two-line description, identical heights, in a 3-column grid.
- **Stat strips** ("10K+ users · 99.9% uptime · 24/7 support") with invented numbers.
- **Cookie-cutter navbar**: logo left, 4 links centered or right, one CTA button, sticky with blur.
- **Testimonials with fabricated people**: "Sarah Chen, CTO at TechFlow", initials avatars, five stars.
- **Boilerplate forms and modals**: centered card, title, subtitle, fields, full-width button, no considered error states.
- **Dashboards**: four KPI cards on top, a line chart, a recent-activity table, all with the same card treatment and made-up data.
- **Footer with four link columns** of links that go nowhere, plus "© 2025 Company. All rights reserved."

### 1.3 Copy and Content Patterns

- **Template headlines**: "Supercharge your workflow", "Unlock the power of…", "Elevate your…", "The future of X is here", "Seamless, intuitive, powerful".
- **Buzzword stacks**: seamless, effortless, cutting-edge, next-generation, robust, scalable, leverage, streamline, empower, revolutionize, game-changing.
- **Rule of three everywhere**: three features, three steps, three tiers, three-adjective taglines. Occasionally six.
- **Perfect symmetry**: every card has the same number of words, every list item the same length and grammatical shape.
- **Em-dash-heavy, "It's not X, it's Y" sentence construction** and tidy parallel phrasing in paragraphs.
- **Filler microcopy**: "Something went wrong. Please try again.", "No data available", "Welcome back!", "Get started in seconds".
- **Vague claims with no specifics**: no real numbers, names, constraints, or tradeoffs. Nothing a human who actually built the product would say.
- **Placeholder tells**: "Lorem ipsum", "John Doe", `example@email.com`, `Company Name`, `#` hrefs.
- **Title Case On Every Heading** or, inversely, relentlessly cheerful sentence-case marketing tone.

### 1.4 Code-Level Signals

- **Tailwind utility chains with no design tokens**: raw `bg-gradient-to-r from-indigo-500 to-purple-600` repeated in dozens of places instead of semantic variables.
- **Arbitrary values mixed with default scale** inconsistently (`mt-[13px]` next to `mt-4`).
- **Inline styles** for one-off fixes, scattered between utility classes.
- **Comments that restate the code**: `// Handle click`, `{/* Hero Section */}`, `// Import dependencies`.
- **Uniform file structure**: `components/ui/`, `components/sections/Hero.tsx`, `Features.tsx`, `Testimonials.tsx`, `CTA.tsx`, each ~60 lines, same shape.
- **shadcn/ui components used unmodified** with the default theme (neutral/zinc, default radius).
- **Props-heavy micro-components** wrapping a single div; excessive abstraction for things used once.
- **Hardcoded data arrays at the top of each component** (`const features = [{ icon: Zap, title: "Lightning Fast", … }]`) with `.map()` rendering.
- **Over-defensive code**: try/catch around everything with `console.error`, optional chaining on values that can't be null.
- **Generic names**: `data`, `handleSubmit`, `Container`, `Wrapper`, `Card`, `Section`, `utils.ts`, `helpers.ts`.
- **No tests, no types beyond `any`, no real state model**: state is `useState` per component with fake async delays (`setTimeout` pretending to be an API).

### 1.5 Interaction and Animation Patterns

- **The universal scroll reveal**: every element fades in and slides up 20px, with staggered delays, via Framer Motion or an Intersection Observer.
- **Identical hover states**: `hover:scale-105` and `hover:shadow-xl` on every card and button, `transition-all duration-300`.
- **Pulsing or bouncing elements** (animated dots, `animate-pulse` on badges).
- **Default easing everywhere** (`ease-in-out` at 300ms), no choreography.
- **No considered feedback**: no skeleton states that match layout, no optimistic UI, no keyboard shortcuts, no focus design beyond the browser default or a generic ring.
- **Marquee logo scrollers and typewriter hero text** added because they are easy, not because they serve content.

### 1.6 Technical Stack Signals

- **Default scaffold remnants**: Vite/Next favicon, default `<title>`, boilerplate CSS.
- **Generic metadata**: missing or boilerplate `<meta description>`, no OG/Twitter images, no canonical, no theme-color.
- **Everything client-rendered** when the content is static.
- **Fonts loaded from Google with no subsetting, preload, or fallback metrics**, causing layout shift.
- **Unoptimized images**, no `width`/`height`, no `srcset`, no modern formats.
- **Fake data and fake auth**: login that always succeeds, API calls to mock endpoints left in place.

### 1.7 Accessibility and SEO Shortcuts

- **Missing or lazy alt text** (`alt="image"`, `alt=""` on meaningful images, or alt text that repeats the caption).
- **`div` soup** with `onClick` instead of buttons and links; icon-only buttons with no `aria-label`.
- **Broken heading hierarchy**: multiple `h1`s, or headings chosen for size (`h3` after `h1`).
- **No skip link, no landmark roles**, no visible focus states, low-contrast gray-on-gray text (`text-gray-400` on white).
- **Color as the only status indicator** (red/green with no icon or text).
- **No structured data** (JSON-LD), no sitemap, no robots, no `lang` attribute considered.
- **`prefers-reduced-motion` ignored** despite heavy animation.

---

## Part 2: Human-Made Website Indicators

- **Brand-driven inconsistency**: a deliberately odd corner radius, an unexpected accent used sparingly, one component that breaks the system on purpose.
- **Custom visual assets**: commissioned or hand-drawn illustration, real photography with a consistent treatment, a bespoke icon set or heavily customized icons, an actual logo with a lockup.
- **Opinionated typography**: a chosen display face paired with a text face, tuned line-height and letter-spacing per size, a real modular scale, optical alignment, proper quotes, hanging punctuation, tabular numerals where numbers align.
- **Asymmetric, purposeful layouts**: uneven columns, elements that bleed off the grid, large type that overlaps imagery, sections of different heights and densities, a clear focal point per screen.
- **Generous, uneven whitespace**: space used to create emphasis and pacing, not applied uniformly.
- **Real content**: specific numbers, named customers who exist, product screenshots from the actual product, copy with a point of view, humor or restraint that suits the brand.
- **Distinctive interaction**: bespoke scroll behavior, a custom cursor only where it adds meaning, page transitions with narrative logic, interactions unique to the product (a draggable timeline, a live calculator).
- **Evidence of iteration**: small details that took multiple passes (nudged baselines, adjusted optical sizes, a hover state that differs by element type), sometimes slightly imperfect but considered.
- **Edge-case care**: custom 404 and 500 pages, empty states that teach, skeleton loaders shaped like the real layout, offline handling, form errors that say exactly what to fix, print stylesheets.
- **Technical craft**: design tokens as CSS variables, a real type and spacing scale, clean semantic HTML, meaningful metadata and share images, performance budgets, accessibility treated as a feature.
- **Constraint and subtraction**: fewer sections, fewer effects, one or two strong ideas executed well.

---

## Part 3: Anti-AI-Slop Rules for Coding Agents

*Treat these as defaults to override only when the user explicitly asks otherwise. Before writing UI code, commit to the design direction (Rule 1). Before finishing, run the Pre-Ship Checklist.*

### Design

1. **DO NOT start building before committing to a design direction.**
   Write a short brief first (audience, tone in three words, one reference point, what makes this product different) and let it drive palette, type, layout, and copy.
2. **DO NOT use purple/indigo/blue gradients, gradient headline text, or glowing blurred orbs as a default look.**
   Choose a palette from the brand or domain. Use flat color or subtle, purposeful tonal shifts. Use one accent color sparingly and tint neutrals toward it rather than using raw framework grays.
3. **DO NOT set the entire site in Inter/system sans at default weights.**
   Pair a distinctive display or heading face with a readable text face. Define a type scale (e.g., 1.25 ratio) and set line-height and letter-spacing per size. Use tabular numerals (`tabular-nums`) for any aligned figures.
4. **DO NOT apply one radius, one shadow, and one border treatment to every element.**
   Define an elevation system (flat, raised, overlay) and a small set of radii tied to component type. Use borders or tone shifts instead of shadows where it fits. Allow sharp corners when the brand calls for it.
5. **DO NOT use Lucide/Heroicons in tinted rounded-square badges above card titles, or emojis as icons.**
   Use icons only where they aid recognition, at consistent stroke and size, without badge containers. Prefer text, numbers, small diagrams, or custom SVGs. Never use emoji as UI iconography.
6. **DO NOT use placeholder imagery, gradient rectangles as "screenshots", or div-built fake dashboards as hero art.**
   Use real product UI, an actual rendered component, a purposeful diagram, or typography-led layouts. If assets are missing, leave clearly marked slots rather than faking them.
7. **DO NOT add glassmorphism, backdrop blur, dot grids, or decorative blobs without a functional reason.**
   Let structure, type, and spacing carry the design. Add texture only when it expresses the brand and keep it to one device.
8. **DO NOT rely on color alone or low-contrast gray text for hierarchy.**
   Meet WCAG AA contrast (4.5:1 body, 3:1 large). Build hierarchy with size, weight, spacing, and position. Pair status colors with icons or text.
9. **DO NOT make data-dense interfaces look like marketing pages.**
   Use compact, aligned tables, right-aligned tabular numerals, consistent decimal precision, clear units and currency, restrained color (reserve red/green for gains/losses and also encode direction with a sign or arrow), and visible timestamps for data freshness.

### Layout

10. **DO NOT default to Hero → Logos → 3 Features → Steps → Testimonials → Pricing → FAQ → CTA → Footer.**
    Derive section order from user tasks. Cut sections that have no real content. Lead with the product itself, a demo, a concrete claim, or the core task. For apps, skip marketing fluff and build the working interface first.
11. **DO NOT build equal-width, equal-height card grids by default.**
    Vary scale to reflect importance: one dominant item, supporting items smaller. Use lists, tables, or prose when content isn't card-shaped. Break the grid deliberately in one or two places.
12. **DO NOT use the same vertical padding for every section.**
    Use a spacing scale and vary density: tight where content is related, generous around key moments.
13. **DO NOT center-align everything.**
    Left-align body copy and most headings. Center only short, ceremonial moments.
14. **DO NOT default to the sticky blurred navbar with logo, four links, and a CTA.**
    Design navigation from the information architecture: sidebar for tools, minimal header for single-purpose pages, contextual nav for long documents.
15. **DO NOT ship layouts that only work at one viewport.**
    Design mobile and desktop deliberately. Test with long names, large numbers, empty lists, and 200% zoom.

### Copy

16. **DO NOT write headlines from the template vocabulary.**
    Banned words: "Supercharge", "Unlock", "Elevate", "Seamless", "Revolutionize", "Next-generation", "Effortless", "Powerful", "Empower". State specifically what the product does, for whom, with concrete details.
17. **DO NOT default to exactly three (or six) of everything, or to symmetrical lists.**
    Use as many items as the content actually has, in varied lengths. Combine, drop, or expand items for honesty rather than balance.
18. **DO NOT invent testimonials, customer logos, user counts, uptime figures, or awards.**
    Omit the section, or insert clearly labeled placeholders for the owner to replace.
19. **DO NOT use filler microcopy.**
    Avoid "Something went wrong", "No data available", "Welcome back!", "Get started in seconds". Write specific messages: what happened, why if known, and actionable next steps.
20. **DO NOT use "It's not X, it's Y" constructions, stacked em dashes, or tidy parallel triplets in prose.**
    Vary sentence length and structure, prefer plain statements, use specifics, and cut sentences that only restate the previous one.
21. **DO NOT leave placeholder content in shipped output.**
    Avoid "Lorem ipsum", "John Doe", `example@email.com`, `href="#"`, "Company Name". Use realistic, labeled sample data and flag every placeholder in a final handoff note.

### Code Quality

22. **DO NOT repeat raw Tailwind utility strings for design decisions; establish tokens first.**
    Define CSS variables or theme tokens for color, type scale, spacing, radius, shadow, and motion. Reference semantic names (`--surface`, `--text-muted`, `--accent`).
23. **DO NOT mix arbitrary pixel values and default-scale classes ad hoc.**
    Pull values from the scale. When a custom value is needed, add it to tokens with a name.
24. **DO NOT write comments that narrate the code (`// Handle click`, `{/* Hero Section */}`).**
    Comment only the why: non-obvious decisions, workarounds, constraints, links to specs.
25. **DO NOT scaffold one component file per marketing section by reflex.**
    Structure code around domain concepts, colocate related code, and abstract only after the second or third real use.
26. **DO NOT ship shadcn/ui or any component library with the default theme untouched.**
    Customize tokens (radius, colors, fonts, focus ring, density) and restyle at least the primary components to match the design brief.
27. **DO NOT hardcode content arrays at the top of components, and DO NOT fake data layers with `setTimeout`.**
    Separate content and data from presentation. Model real types, use a proper data-fetching layer, and clearly label any mock data.
28. **DO NOT use generic names (`data`, `item`, `Wrapper`, `Container`, `utils.ts`, `helpers.ts`) or `any`.**
    Name things for the domain (`VariantRow`, `formatInr`, `useQuoteStream`). Type data properly and validate at boundaries.
29. **DO NOT wrap everything in try/catch with `console.error`, or add defensive code for impossible states.**
    Handle errors where you can do something useful (retry, message, fallback UI), let unexpected errors surface, and log meaningfully.
30. **For financial or numeric apps: DO NOT use floating-point math for money or hide rounding rules.**
    Use integer minor units or dedicated helpers, centralize formatting and rounding in one module, store currency codes, and test calculations with known cases.

### Interactions

31. **DO NOT fade-and-slide every element on scroll.**
    Animate only to explain: a state change, a spatial relationship, a focal reveal. Most content should simply be there.
32. **DO NOT use `hover:scale-105 hover:shadow-xl transition-all` on everything.**
    Define interaction states per component type (links, buttons, rows, cards), include focus-visible and active states, and transition only the properties that change.
33. **DO NOT animate with default easing and a single duration.**
    Define motion tokens (durations and custom cubic-bezier curves), use faster timing for small changes and slower for large ones, and honor `prefers-reduced-motion`.
34. **DO NOT skip loading, empty, error, and offline states.**
    Provide skeletons shaped like the real layout, instructive empty states, specific error messages with recovery actions, optimistic updates where safe, and a custom 404.
35. **DO NOT add decorative gimmicks (typewriter hero text, marquee logo bars, custom cursors) because they are easy.**
    Add one distinctive interaction that belongs to this product (e.g., live calculator, draggable range, keyboard-driven controls).

### Technical Defaults

36. **DO NOT leave scaffold defaults: Vite/Next favicon, default `<title>`, template README, unused assets, boilerplate CSS.**
    Set a real title pattern, favicon set, theme-color, and clean README. Remove unused files and dependencies.
37. **DO NOT omit metadata.**
    Provide unique title and description per page, canonical URL, Open Graph and Twitter tags with a real share image, `lang`, and JSON-LD where relevant.
38. **DO NOT use `div`s and click handlers for interactive elements, or icon-only buttons without labels.**
    Use `button`, `a`, `label`, `nav`, `main`, `header`, `footer`, and proper form associations. Give icon buttons `aria-label`s, add a skip link, one `h1` per page, and a logical heading hierarchy.
39. **DO NOT write lazy alt text (`alt="image"`) or omit it.**
    Describe what the image communicates; use empty alt only for purely decorative images and mark decorative SVGs `aria-hidden`.
40. **DO NOT ship unoptimized assets or layout-shifting fonts.**
    Set image dimensions, use responsive `srcset` and modern formats, lazy-load below the fold, subset and preload fonts with `font-display` and matched fallbacks.
41. **DO NOT leave fake auth, mock endpoints, or hardcoded secrets in place without saying so.**
    Clearly mark mocked parts in code and handoff notes, read secrets from environment variables, and never expose API keys client-side.

---

## Pre-Ship Checklist

1. Is there a written design direction, and does every visual choice trace back to it?
2. Would a stranger identify this as a template within five seconds? If yes, what specifically is generic?
3. Is the color palette free of default indigo/purple gradients and raw framework grays?
4. Is there a deliberate type pairing and scale, not just Inter at default weights?
5. Do radii, shadows, and spacing vary by purpose rather than repeat everywhere?
6. Does the section order come from the product's needs, not the template sequence?
7. Is any content fabricated (testimonials, logos, stats)? Remove or label it.
8. Are there banned buzzwords, rule-of-three lists, or "not X, it's Y" sentences in the copy?
9. Are design decisions held in tokens, with no repeated raw utility chains?
10. Do comments explain why, not what?
11. Does every interactive element work with keyboard and screen reader, with visible focus?
12. Are loading, empty, error, and 404 states designed?
13. Are animations purposeful, varied, and reduced-motion safe?
14. Are scaffold remnants gone (favicon, title, README, unused files)?
15. Are metadata, OG image, and heading hierarchy correct?
16. Are all mocks and placeholders listed in the handoff note?
