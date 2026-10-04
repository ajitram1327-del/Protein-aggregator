# MASTER PRD: Proteindex Terminal (v2.1)

**System Type:** Decoupled, API-First Nutritional Commodity Screener & Price Aggregator

**Target Market:** India (D2C Brands, Marketplaces, Quick-Commerce)

**Primary Architecture:** Decoupled Architecture (`/api` Backend + `/client` Static Frontend) communicating exclusively via RESTful JSON.

---

## 1. System Architecture & Modularity

The codebase is strictly separated into two independent environments:

* **Headless API-First Backend:** The backend renders no HTML. It serves strictly structured, typed JSON via RESTful endpoints.
* **Failure Isolation:** A scraper failure or vendor block never crashes the frontend. The UI consumes the last verified cached JSON snapshot.
* **Stateless Extensibility:** New features are built as modular microservices (e.g., FSSAI database pings, PDCAAS calculators) without modifying the scraper or core UI layers.

---

## 2. Master Universal JSON Schema (Updated)

Every scraped SKU must be parsed, normalized, and validated against this uniform JSON contract:

```json
{
  "skuId": "nakpro-plat-iso-unflavored-1kg",
  "brand": "Nakpro",
  "productName": "Platinum Whey Protein Isolate",
  "categorySilo": "protein",
  "subCategory": "Whey Isolate",
  "flavor": "Unflavored",
  "packaging": {
    "weightGrams": 1000,
    "servingsCount": 33,
    "servingSizeGrams": 30.0
  },
  "nutritionalProfile": {
    "activeIngredientPerServingGrams": 28.0,
    "pdcaasScore": 1.0, 
    "bioavailableProteinPerServing": 28.0,
    "proteinPurityPct": 93.33,
    "caloriesPerServing": 118,
    "carbsPerServingGrams": 0.5
  },
  "usefulDoseAnalysis": {
    "leucinePerServingGrams": 2.8,
    "meetsMpsThreshold": true,
    "aminoSpikeRisk": false,
    "fillersDetected": []
  },
  "equalizerMetrics": {
    "primaryMetricLabel": "₹/g bioavailable protein",
    "primaryMetricValue": 2.10,
    "secondaryMetricLabel": "Purity %",
    "secondaryMetricValue": 93.33
  },
  "pricing": {
    "lowestPriceInr": 1949.00,
    "vendorOffers": [
      {
        "platform": "Brand D2C",
        "url": "https://nakpro.com/products/...",
        "priceInr": 1949.00
      }
    ]
  },
  "verification": {
    "tier": "gold",
    "fssai": {
      "licenseNumber": "10020043003186",
      "status": "ACTIVE",
      "verifiedManufacturer": "Nakpro Nutrition"
    },
    "records": [
      {
        "authority": "Trustified",
        "labName": "Eurofins",
        "status": "PASS",
        "proofUrl": "https://www.trustified.in/passandfail/nakpro-iso"
      }
    ]
  }
}
```

---

## 3. Isolated Category Silos & Equalizer Algorithms

Products from different categories must **never** be mixed. Each silo operates under an independent route and proprietary Equalizer Metric.

### Silo 1: Protein Powders (`/protein`)

* **Core Metric (Bioavailability-Adjusted):**

$$\text{₹ / g of Bioavailable Protein} = \frac{\text{Sticker Price}}{\text{Servings} \times (\text{Protein per Serving} \times \text{PDCAAS Score})}$$


* **Secondary Metric (Protein Purity):**

$$\text{Purity (\%)} = \left(\frac{\text{Protein per Serving (g)}}{\text{Serving Size (g)}}\right) \times 100$$



### Silo 2: Mass Gainers (`/mass-gainers`)

* **Core Metric:** `(Price ÷ Total Calories in Tub) × 1000` (₹ per 1,000 kcal).
* **Secondary Metric:** `Carbs per Serving (g) ÷ Protein per Serving (g)`.

### Silo 3: Creatine (`/creatine`)

* **Core Metric:** `Price ÷ (Servings × Creatine per Serving)` (₹ / g of pure Creatine).

### Silo 4: Pre-Workout (`/pre-workout`)

* **Core Metric:** `Price ÷ Total Full Scoops` (₹ / Standardized Serving).

---

## 4. The "Useful Dose" & Bioavailability Engine

This engine parses the nutrition panel and ingredient statement to determine physiological utility.

* **PDCAAS Scoring & Bioavailability Correction:** The system applies a backend multiplier to calculate *Bioavailable Protein*, adjusting the Equalizer Metric to penalize incomplete plant profiles (e.g., Whey Isolate = ~1.0, unblended Pea Protein = ~0.7).
* **The Leucine Threshold:** Flags products that meet the ~2.5g to 3.0g Leucine threshold required for Muscle Protein Synthesis.
* **Amino Spiking Detection:** Flags added free-form amino acids (Glycine, Taurine, L-Glutamine) in protein powder ingredient lists with a `⚠️ High Amino Spiking Risk` badge.

---

## 5. Verification & Anti-Counterfeit Engine

* **Automated FSSAI License Verification:** The backend extracts the 14-digit FSSAI license number from the brand's data. An automated microservice pings the official FoSCoS verification portal to ensure the license is active and matches the manufacturer. Products with invalid/expired licenses are shadow-banned or flagged in red.
* **Interactive Lab Badges:**
* **Gold Shield:** Verified 3rd-Party Lab (Trustified, Informed Choice, Labdoor).
* **Silver Shield:** Brand-provided NABL Accredited COA.
* Clicking the shield opens a modal showing the Testing Body, Batch Number, `PASS/FAIL` status, and a hyperlink to the original PDF.



---

## 6. The Macro-Market: "Commodity Spread" Terminal

To operate as a true market screener, the platform contextualizes retail prices against global raw material costs.

* **Global Wholesale Tracker:** A backend cron job scrapes the global commodity price for raw Whey Protein Concentrate (WPC-80) per kg.
* **The Markup Chart:** The UI features a macro-chart overlaying the "Raw WPC-80 Index" against the "Indian Retail Protein Average."
* **Utility:** This allows users to instantly visualize the markup spread to see if a retail price hike is due to a global dairy shortage or artificial profit padding.

---

## 7. Scraper Pipeline & Anti-Bot Infrastructure

* **Tier 1: The D2C Shopify Engine:** Scrapes `products.json` endpoints using TLS-impersonation (`curl_cffi`) to match real browser JA3/JA4 fingerprints and bypass Cloudflare WAF.
* **Tier 2: Marketplace Crawler:** Uses C++ stealth-patched frameworks (`nodriver` or `camoufox`) routed through rotating Indian Residential Proxies with randomized request jitter to prevent IP bans on Amazon India, Flipkart, and HealthKart.

---

## 8. Advanced Edge Features (India-Specific)

* **Quick-Commerce Arbitrage:** Cross-references prices with 10-minute delivery apps (Blinkit, Zepto, Swiggy Instamart) via location spoofing to highlight localized dark-store clearance discounts compared to Amazon's 2-day delivery price.
* **The "True Scoop" Audit:** Adjusts the Equalizer Metric if crowdsourced/lab data proves the physical plastic scoop provided inside the tub holds more grams than the nutritional label claims (a tactic used to artificially accelerate consumption).
