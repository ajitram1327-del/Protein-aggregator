import json
import csv
import io

CSV_DATA = """Brand Name,Origin / Tier,Core Tracked Categories,Flagship Products Tracked,Primary Scraped Channels
Optimum Nutrition (ON),Global / Import,Performance Nutrition,"Gold Standard Whey, Serious Mass, Micronized Creatine, Gold Standard Pre-Workout, Amino Energy (BCAA)","optimumnutrition.co.in, Amazon.in, HealthKart, Tata 1mg, Nutrabay"
MuscleTech,Global / Import,Performance Nutrition,"Nitro-Tech, Mass-Tech Extreme 2000, Cell-Tech Creatine, VaporX5 Pre-Workout, Platinum L-Carnitine","Amazon.in, HealthKart, Tata 1mg, Nutrabay"
Dymatize,Global / Import,Performance Nutrition,"ISO100 Hydrolyzed, Elite Whey, Super Mass Gainer, All9 Amino (BCAA), Creatine Monohydrate","Amazon.in, HealthKart, Nutrabay, Neulife"
BSN,Global / Import,Performance Nutrition,"Syntha-6, True-Mass Gainer, N.O.-XPLODE Pre-Workout, Amino X (Effervescent BCAA)","Amazon.in, HealthKart, Nutrabay"
Isopure,Global / Import,Performance Nutrition,"Zero Carb Whey Isolate, Low Carb Protein","Amazon.in, HealthKart, Nutrabay, Neulife"
Cellucor,Global / Import,Performance Nutrition,"C4 Original Pre-Workout, C4 Ripped, Cor-Performance Creatine, Alpha Amino (BCAA)","Amazon.in, HealthKart, Neulife, Nutrabay"
Nutrex,Global / Import,Performance Nutrition,"Lipo-6 Black, Outlift Pre-Workout, Creatine Drive","Amazon.in, HealthKart, Supplements Villa"
MusclePharm,Global / Import,Performance Nutrition,"Combat 100% Whey, Assault Pre-Workout, BCAA 3:1:2","Amazon.in, HealthKart, Nutrabay"
Universal / Animal,Global / Import,Performance & Micronutrients,"Animal Pak (Multivitamins), Animal Fury Pre-Workout, Animal Creatine Chews, Animal Mass","Amazon.in, HealthKart, Neulife"
Ultimate Nutrition,Global / Import,Performance Nutrition,"Prostar 100% Whey, Iso Sensation 93, Muscle Juice Gainer","Amazon.in, HealthKart, Nutrabay"
Rule 1,Global / Import,Performance Nutrition,"R1 Protein, R1 LBS Mass Gainer, R1 Pre-Train, R1 Creatine, R1 BCAA","Amazon.in, HealthKart, Neulife"
Labrada,Global / Import,Performance Nutrition,"Muscle Mass Gainer, 100% Premium Whey, Creapure Creatine, BCAA Power, Liquid L-Carnitine","Amazon.in, HealthKart, Nutrabay"
Scitec Nutrition,Global / Import,Performance Nutrition,"100% Whey Protein Professional, Jumbo Mass Gainer, BCAA Xpress","Amazon.in, HealthKart"
Olimp,Global / Import,Performance Nutrition,"Whey Protein Complex 100%, BCAA Xplode, Creatine 1250 Mega Caps","Amazon.in, HealthKart, Nutrabay"
Applied Nutrition,Global / Import,Performance Nutrition,"ABE (All Black Everything) Pre-Workout, Critical Mass, Critical Whey, Creatine Monohydrate, BCAA Amino-Hydrate","Amazon.in, HealthKart, Nutrabay"
PhD Nutrition,Global / Import,Performance Nutrition,"Diet Whey, Synergy ISO-7, Diet Plant Protein","Amazon.in, HealthKart"
Gaspari,Global / Import,Performance Nutrition,"MyoFusion Advanced Protein, SuperPump Max Pre-Workout, SizeOn","Amazon.in, HealthKart"
Redcon1,Global / Import,Performance Nutrition,"Total War Pre-Workout, Big Noise Pump, MRE Lite, Tango Creatine","Amazon.in, HealthKart"
Ghost,Global / Import,Performance Nutrition,"Ghost Legend Pre-Workout, Ghost Size (Creatine/Betaine), Ghost Whey, Ghost BCAA","Amazon.in, Neulife"
Kaged,Global / Import,Performance Nutrition,"Pre-Kaged Elite, Kaged Creatine HCl, Hydra-Charge, Fermented BCAA","Amazon.in, Nutrabay"
Bucked Up,Global / Import,Performance Nutrition,"Bucked Up Pre-Workout, Woke AF, Deer Antler Spray","Amazon.in, Ubuy"
Six Star,Global / Import,Performance Nutrition,"100% Whey Protein Plus, Pre-Workout Explosion, Creatine X3","Amazon.in, Desertcart"
Muscle Milk,Global / Import,Performance & Health Food,"Genuine Protein Powder, Pro Series Protein",Amazon.in
Orgain,Global / Import,Health Foods & Plant Protein,"Organic Plant Based Protein Powder, Organic Nutrition Shakes",Amazon.in
Garden of Life,Global / Import,Health Foods & Plant Protein,"Raw Organic Protein, Sport Certified Grass Fed Whey",Amazon.in
NOW Sports,Global / Import,Micronutrients & Performance,"Pea Protein, Whey Protein Isolate, ZMA, L-Carnitine","Amazon.in, 1mg"
Allmax,Global / Import,Performance Nutrition,"Isoflex, Aminocore BCAA, Creatine Monohydrate","Amazon.in, HealthKart"
Beast Sports Nutrition,Global / Import,Performance Nutrition,"Beast Creature Creatine, Beast Mode Pre-Workout",Amazon.in
Body Fortress,Global / Import,Performance Nutrition,"Super Advanced Whey Protein, Super Advanced Creatine",Amazon.in
Evlution Nutrition (EVL),Global / Import,Performance Nutrition,"ENGN Pre-Workout, BCAA Energy, LeanMode, 100% Whey","Amazon.in, HealthKart"
JNX Sports,Global / Import,Performance Nutrition,"The Curse Pre-Workout, The Ripper","Amazon.in, HealthKart"
Legion Athletics,Global / Import,Performance Nutrition,"Whey+ Isolate, Pulse Pre-Workout, Recharge Post-Workout","Amazon.in, Ubuy"
Mutant,Global / Import,Performance Nutrition,"Mutant Mass, Mutant Madness Pre-Workout, Mutant Creakong, Mutant BCAA","Amazon.in, HealthKart, Supplements Villa"
Naked Nutrition,Global / Import,Clean Performance Nutrition,"Naked Whey, Naked Pea, Naked Mass","Amazon.in, Ubuy"
Nutrabolics,Global / Import,Performance Nutrition,"Supernova, Mass Fusion, Anabolic State BCAA","Amazon.in, HealthKart"
Nutricost,Global / Import,Micronutrients & Performance,"Creatine Monohydrate, Whey Protein Concentrate, L-Glutamine","Amazon.in, Desertcart"
ProSupps,Global / Import,Performance Nutrition,"Mr. Hyde Pre-Workout, Dr. Jekyll, PS Whey","Amazon.in, HealthKart"
Sunwarrior,Global / Import,Health Foods & Plant Protein,"Warrior Blend, Classic Plus Organic Vegan Protein","Amazon.in, HealthKart"
Transparent Labs,Global / Import,Clean Performance Nutrition,"100% Grass-Fed Whey Isolate, Bulk Pre-Workout","Ubuy, Desertcart"
Vega,Global / Import,Health Foods & Plant Protein,"Vega Sport Premium Protein, Vega One Organic","Amazon.in, Desertcart"
Scivation / Xtend,Global / Import,Performance Nutrition,"Xtend Original BCAA, Xtend Ripped (BCAA + L-Carnitine), Xtend Elite Pre-Workout","Amazon.in, HealthKart, Nutrabay, Supplements Villa"
GAT Sport,Global / Import,Performance Nutrition,"Nitraflex Pre-Workout, Liquid L-Carnitine 1500/3000, Creatine Monohydrate, Flextreme BCAA","Amazon.in, HealthKart, Nutrabay"
Insane Labz,Global / Import,Performance Nutrition,"Psychotic Pre-Workout, Psychotic Gold, Insane Cutz, Micronized Creatine","Amazon.in, HealthKart, Supplements Villa"
Kevin Levrone Signature,Global / Import,Performance Nutrition,"Shaaboom Pump Pre-Workout, Anabolic Mass Gainer, LevroMono Creatine, Gold BCAA","Amazon.in, HealthKart, Neulife, Protein Xpress"
Ronnie Coleman Signature,Global / Import,Performance Nutrition,"Yeah Buddy Pre-Workout, King Mass XL, Creatine XS, Amino-Tone (BCAA)","Amazon.in, HealthKart, Supplements Villa"
MuscleBlaze,Domestic / D2C,Performance & Health Food,"Biozyme Whey, Super Gainer XXL, CreAMP / Monohydrate Creatine, WrathX Pre-Workout, BCAA Pro, L-Carnitine, High Protein Peanut Butter, High Protein Oats","muscleblaze.com, HealthKart, Amazon.in, Flipkart, Tata 1mg"
Avvatar,Domestic / D2C,Performance Nutrition,"Whey Protein, Absolute Isolate, Muscle Gainer, Micronized Creatine Monohydrate","avvatarindia.com, Amazon.in, HealthKart, Nutrabay"
AS-IT-IS Nutrition,Domestic / D2C,Performance & Health Food,"Pure Whey, ATOM Mass Gainer, Pure Creatine Monohydrate, ATOM Pre-Workout, ATOM BCAA, L-Carnitine, Natural Peanut Butter","asitisnutrition.com, Amazon.in, Flipkart, Tata 1mg"
Nakpro,Domestic / D2C,Performance Nutrition,"Platinum Whey, Gold Whey, Mass Gainer, Micronized Creatine, Fermented BCAA","nakpro.com, Amazon.in, Flipkart"
Fast&Up,Domestic / D2C,Performance & Micronutrients,"Plant Protein, Whey Essentials, Creatine Monohydrate, BCAA 2:1:1, L-Carnitine Carnipure, Pre-Workout, Daily Multivitamins","fastandup.in, Amazon.in, Tata 1mg, Apollo Pharmacy"
Wellcore,Domestic / D2C,Performance Nutrition,"Micronized Creatine Monohydrate, Pure Creatine Creapure, Electrolytes","wellcore.in, Amazon.in, HealthKart"
Big Muscles Nutrition,Domestic / D2C,Performance Nutrition,"Freak Pre-Workout, Real Mass Gainer, Creatine Monohydrate, Quick BCAA, Carni-Engine (L-Carnitine)","bigmusclesnutrition.com, Amazon.in, Flipkart"
Scitron,Domestic / D2C,Performance Nutrition,"Advance Whey, Volcano Pre-Workout, Mega Mass Gainer, Creatine Monohydrate, Essential BCAA","scitron.com, Amazon.in, HealthKart"
Repfuel Sports,Domestic / D2C,Performance Nutrition,"Firebreather Pre-Workout, Whey In, Alpha Creatine, BCAA 6000","repfuelsports.com, Amazon.in"
Nutrabox,Domestic / D2C,Performance Nutrition,"Ripped BCAA, Brawn Mass Gainer, Micronized Creatine, Pre-Workout Target","nutrabox.in, Amazon.in"
GNC India,Licensed / D2C,Performance & Micronutrients,"Pro Performance Whey, AMP Pure Isolate, Creatine Monohydrate, Pro Performance BCAA, Mega Men Multivitamins","guardian.in, Amazon.in, HealthKart"
Myprotein India,Global / D2C,Performance & Health Food,"Impact Whey, The Pre-Workout, Creatine Monohydrate, Essential BCAA, Protein Flapjacks & Brownies, High Protein Peanut Butter",myprotein.co.in
Pintola,Domestic / D2C,Health Foods & Pantry,"High Protein Peanut Butter (Dark Chocolate / Classic / Whey-infused), Organic Peanut Butter, Protein Muesli","pintola.in, Amazon.in, Flipkart, Zepto, Blinkit"
Alpino,Domestic / D2C,Health Foods & Pantry,"Super High Protein Peanut Butter, High Protein Super Oats (Chocolate & Plain)","alpino.in, Amazon.in, Flipkart"
MyFitness,Domestic / D2C,Health Foods & Pantry,"Original Chocolate High Protein Peanut Butter, Crispy Peanut Butter, High Protein Rolled Oats","myfitness.in, Amazon.in, HealthKart, Flipkart"
Yogabar,Domestic / D2C,Health Foods & Pantry,"20g High Protein Oats (Chocolate / Golden Crunch), 20g Protein Bars, High Protein Peanut Butter","yogabar.in, Amazon.in, BigBasket, Zepto"
RiteBite Max Protein,Domestic / D2C,Health Foods & Pantry,"Max Protein Bars (10g, 20g, 30g Daily/Ultimate), High Protein Cookies, Max Protein Chips","maxprotein.in, Amazon.in, Flipkart, Tata 1mg"
SuperYou,Domestic / D2C,Health Foods & Pantry,"High Protein Wafer Bars, Protein Bars","superyou.in, Amazon.in"
The Whole Truth Foods,Domestic / D2C,Health Foods & Pantry,"Whey Isolate, High Protein Bars, Dark Chocolate Peanut Butter, High Protein Muesli","thewholetruthfoods.com, Amazon.in, Swiggy Instamart"
Phab,Domestic / D2C,Health Foods & Pantry,"High Protein Milkshakes, 20g Protein Bars, Protein Bombs","getphab.com, Amazon.in"
NutroActive,Domestic / D2C,Functional Flours (Atta),"Brown Xtra High Protein Atta (50g+ Protein/100g), Keto Ultra Low-Carb Flour, Protein Pasta","nutroactive.com, Amazon.in, Tata 1mg"
Ketofy / Lo! Foods,Domestic / D2C,Functional Flours (Atta),"Ultra Low Carb High Protein Atta, Low Carb Protein Cookies, Protein Roti Mix","Amazon.in, Flipkart, brand stores"
True Elements,Domestic / D2C,Health Foods & Grains,"20g High Protein Rolled Oats (Dark Chocolate / Seeds), High Protein Muesli, Raw Pumpkin & Chia Seeds","trueelements.com, Amazon.in, Flipkart"
Boldfit,Domestic / D2C,Multi-Category / Daily Wellness,"Micronized Creatine Monohydrate, BCAA, L-Carnitine, High Protein Peanut Butter, Multivitamins, Probiotics, Magnesium Glycinate","boldfit.in, Amazon.in, Flipkart"
Carbamide Forte,Domestic / D2C,Micronutrients & Minerals,"Magnesium Glycinate Chelate, 50 Billion Probiotics, Triple Strength Fish Oil, Multivitamins, Pure L-Carnitine","cfstores.in, Amazon.in, Tata 1mg, Flipkart"
HealthyHey Nutrition,Domestic / D2C,Micronutrients & Minerals,"Pure Magnesium Glycinate, Chelated Zinc, Vitamin K2+D3, Vitamin B12, Potassium Citrate","healthyhey.com, Amazon.in, Tata 1mg"
Kapiva,Domestic / D2C,Ayurvedic Performance,"Pure Himalayan Shilajit Resin, Shilajit Gold, KSM-66 Ashwagandha Capsules, Biotin Gummies","kapiva.in, Amazon.in, Tata 1mg, Netmeds"
Upakarma Ayurveda,Domestic / D2C,Ayurvedic Performance,"Pure Shilajit Resin (Gold / Silver Foil), Organic Ashwagandha Root, Pure Shilajit Liquid Drops","upakarma.com, Amazon.in, Tata 1mg"
Neuherbs,Domestic / D2C,Micronutrients & Herbals,"Deep Sea Omega-3 Fish Oil, Pure Himalayan Shilajit Resin, Plant-Based Collagen Booster, Organic Seeds","neuherbs.com, Amazon.in, Tata 1mg"
Man Matters,Domestic / D2C,Performance & Men's Health,"Micronized Creatine Monohydrate, Shilajit Resin with 24K Gold, Ashwagandha Tablets","manmatters.com, Amazon.in, Flipkart"
Zingavita,Domestic / D2C,Micronutrients & Omega,"Triple Strength Omega-3 Fish Oil, Daily Multivitamin for Men/Women, Pre & Probiotics, Magnesium","zingavita.com, Amazon.in, Tata 1mg"
TrueBasics,Domestic / D2C,Micronutrients & Omega,"Ultra Omega-3 Fish Oil, Multivit Men/Women, Joint Support (Curcumin & Glucosamine)","truebasics.com, HealthKart, Amazon.in"
Cosmix,Domestic / D2C,Functional Botanicals & Protein,"No-Nonsense Plant Protein, Healthy Hair Superfoods, What Women Want (Hormonal Balance), Gut Health Cleanse",cosmix.in
Plix Life,Domestic / D2C,Functional Health & Wellness,"Strength Plant Protein (Pea/Brown Rice), Supergreens Effervescent, Marine Collagen, Glutathione Effervescent","plixlife.com, Amazon.in, Tata 1mg"
OZiva,Domestic / D2C,Plant Protein & Herbals,"Organic Plant Protein, Superfood Greens & Herbs, Protein & Herbs for Men/Women, Bioactive Collagen","oziva.in, Amazon.in, Tata 1mg"
Naturaltein / Beast Life,Domestic / Certified,Clean Performance Nutrition,"Creapure Micronized Creatine, Whey Protein Isolate (Cologne List Certified), Organic Vegan Protein","naturaltein.in, Amazon.in"
"""

reader = csv.DictReader(io.StringIO(CSV_DATA.strip()))
brands_list = []
d2c_registry = []
marketplace_queries = []

for row in reader:
    brand = row["Brand Name"]
    tier = row["Origin / Tier"]
    categories = row["Core Tracked Categories"]
    products = [p.strip() for p in row["Flagship Products Tracked"].split(",")]
    channels = [c.strip() for c in row["Primary Scraped Channels"].split(",")]
    
    # Identify D2C domains (ending with .in, .com, .co.in, .co)
    d2c_domain = None
    for c in channels:
        clean_c = c.lower().replace("https://", "").replace("http://", "").strip()
        if any(clean_c.endswith(ext) for ext in [".in", ".com", ".co.in", ".co"]) and not any(m in clean_c for m in ["amazon", "flipkart", "healthkart", "nutrabay", "1mg", "apollo", "netmeds", "zepto", "blinkit", "instamart", "bigbasket", "ubuy", "desertcart"]):
            d2c_domain = clean_c
            break
            
    if d2c_domain:
        d2c_registry.append({"brand": brand, "domain": d2c_domain})
        
    brands_list.append({
        "brand": brand,
        "tier": tier,
        "categories": categories,
        "flagship_products": products,
        "channels": channels,
        "d2c_domain": d2c_domain
    })

print(f"Total Canonical Brands: {len(brands_list)}")
print(f"Total D2C Storefronts Identified: {len(d2c_registry)}")

with open("scraper/scrapling_scraper/src/data/canonical_brands.json", "w", encoding="utf-8") as f:
    json.dump({"brands": brands_list, "d2c_registry": d2c_registry}, f, indent=2)

print("Saved to scraper/scrapling_scraper/src/data/canonical_brands.json")
