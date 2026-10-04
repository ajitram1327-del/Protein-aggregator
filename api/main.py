from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Proteindex Terminal API", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared schemas based on Universal JSON Schema
class Packaging(BaseModel):
    weightGrams: int
    servingsCount: int
    servingSizeGrams: float

class NutritionalProfile(BaseModel):
    activeIngredientPerServingGrams: float
    pdcaasScore: float
    bioavailableProteinPerServing: float
    proteinPurityPct: float
    caloriesPerServing: int
    carbsPerServingGrams: float

class UsefulDoseAnalysis(BaseModel):
    leucinePerServingGrams: float
    meetsMpsThreshold: bool
    aminoSpikeRisk: bool
    fillersDetected: List[str]

class EqualizerMetrics(BaseModel):
    primaryMetricLabel: str
    primaryMetricValue: float
    secondaryMetricLabel: str
    secondaryMetricValue: float

class VendorOffer(BaseModel):
    platform: str
    url: str
    priceInr: float

class Pricing(BaseModel):
    lowestPriceInr: float
    vendorOffers: List[VendorOffer]

class Fssai(BaseModel):
    licenseNumber: str
    status: str
    verifiedManufacturer: str

class VerificationRecord(BaseModel):
    authority: str
    labName: str
    status: str
    proofUrl: str

class Verification(BaseModel):
    tier: str
    fssai: Fssai
    records: List[VerificationRecord]

class ProductSKU(BaseModel):
    skuId: str
    brand: str
    productName: str
    categorySilo: str
    subCategory: str
    flavor: str
    packaging: Packaging
    nutritionalProfile: NutritionalProfile
    usefulDoseAnalysis: UsefulDoseAnalysis
    equalizerMetrics: EqualizerMetrics
    pricing: Pricing
    verification: Verification

# Mock data based on PRD
MOCK_PROTEIN = ProductSKU(
    skuId="nakpro-plat-iso-unflavored-1kg",
    brand="Nakpro",
    productName="Platinum Whey Protein Isolate",
    categorySilo="protein",
    subCategory="Whey Isolate",
    flavor="Unflavored",
    packaging=Packaging(weightGrams=1000, servingsCount=33, servingSizeGrams=30.0),
    nutritionalProfile=NutritionalProfile(
        activeIngredientPerServingGrams=28.0,
        pdcaasScore=1.0,
        bioavailableProteinPerServing=28.0,
        proteinPurityPct=93.33,
        caloriesPerServing=118,
        carbsPerServingGrams=0.5
    ),
    usefulDoseAnalysis=UsefulDoseAnalysis(
        leucinePerServingGrams=2.8,
        meetsMpsThreshold=True,
        aminoSpikeRisk=False,
        fillersDetected=[]
    ),
    equalizerMetrics=EqualizerMetrics(
        primaryMetricLabel="₹/g bioavailable protein",
        primaryMetricValue=2.10,
        secondaryMetricLabel="Purity %",
        secondaryMetricValue=93.33
    ),
    pricing=Pricing(
        lowestPriceInr=1949.00,
        vendorOffers=[
            VendorOffer(platform="Brand D2C", url="https://nakpro.com/...", priceInr=1949.00)
        ]
    ),
    verification=Verification(
        tier="gold",
        fssai=Fssai(licenseNumber="10020043003186", status="ACTIVE", verifiedManufacturer="Nakpro Nutrition"),
        records=[
            VerificationRecord(authority="Trustified", labName="Eurofins", status="PASS", proofUrl="https://www.trustified.in/passandfail/nakpro-iso")
        ]
    )
)

import json
import os

@app.get("/api/protein", response_model=List[ProductSKU])
async def get_protein():
    snapshot_path = "data/protein_snapshot.json"
    
    # Decoupled Failure Isolation: The API reads the last known good snapshot.
    # If the scraper goes down, this cache remains completely unaffected.
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            # If read fails mid-write, fallback safely
            pass
            
    return [MOCK_PROTEIN]

@app.get("/api/mass-gainers")
async def get_mass_gainers():
    return []

@app.get("/api/creatine")
async def get_creatine():
    return []

@app.get("/api/pre-workout")
async def get_pre_workout():
    return []
