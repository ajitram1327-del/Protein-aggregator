from typing import List, Optional, Dict, Any

try:
    from pydantic import BaseModel, Field

    class PackagingInfo(BaseModel):
        weightGrams: int = Field(..., description="Container weight in grams")
        servingsCount: int = Field(..., description="Total servings/scoops")
        servingSizeGrams: float = Field(..., description="Serving/scoop size in grams")

    class NutritionalProfile(BaseModel):
        activeIngredientPerServingGrams: float = Field(..., description="Active ingredient yield per scoop (e.g. protein, creatine)")
        pdcaasScore: float = Field(default=1.0, description="PDCAAS / DIAAS digestibility score")
        bioavailableProteinPerServing: float = Field(..., description="Physiologically bioavailable active per scoop")
        proteinPurityPct: float = Field(..., description="Active yield percentage of scoop")
        caloriesPerServing: float = Field(default=120.0, description="Calories per serving")
        carbsPerServingGrams: float = Field(default=1.0, description="Carbohydrates per serving")

    class UsefulDoseAnalysis(BaseModel):
        leucinePerServingGrams: float = Field(default=2.7, description="Leucine content per scoop")
        meetsMpsThreshold: bool = Field(default=True, description="Meets Muscle Protein Synthesis trigger (~2.5g+)")
        aminoSpikeRisk: bool = Field(default=False, description="Flagged for free-form amino acid spiking")
        fillersDetected: List[str] = Field(default_factory=list, description="Detected low-cost bulking agents")

    class EqualizerMetrics(BaseModel):
        primaryMetricLabel: str = Field(..., description="Label for silo primary equalizer")
        primaryMetricValue: float = Field(..., description="Computed value for primary equalizer")
        secondaryMetricLabel: str = Field(..., description="Label for secondary metric")
        secondaryMetricValue: float = Field(..., description="Computed value for secondary metric")

    class VendorOffer(BaseModel):
        platform: str = Field(..., description="Retailer or marketplace platform name")
        url: str = Field(..., description="Direct listing URL")
        priceInr: float = Field(..., description="Current price in INR")
        inStock: bool = Field(default=True, description="Inventory availability")
        sellerName: Optional[str] = Field(default="", description="Merchant of record")
        isAuthorizedSeller: bool = Field(default=True, description="Authorized distributor status")

    class PricingSummary(BaseModel):
        lowestPriceInr: float = Field(..., description="Lowest active in-stock price")
        lowestAuthorizedPriceInr: Optional[float] = Field(default=None, description="Lowest price from authorized sellers")
        vendorOffers: List[VendorOffer] = Field(default_factory=list, description="All retailer offers")

    class FSSAIInfo(BaseModel):
        licenseNumber: Optional[str] = Field(default=None, description="14-digit FSSAI registration number")
        status: str = Field(default="ACTIVE", description="FoSCoS registration status")
        verifiedManufacturer: Optional[str] = Field(default=None, description="Registered legal entity")

    class VerificationRecord(BaseModel):
        authority: str = Field(default="NABL Accredited", description="Testing or certification body")
        labName: str = Field(default="Eurofins", description="Testing facility")
        status: str = Field(default="PASS", description="PASS or FAIL status")
        proofUrl: Optional[str] = Field(default=None, description="Hyperlink to certificate of analysis PDF")

    class VerificationInfo(BaseModel):
        tier: str = Field(default="bronze", description="gold, silver, or bronze verification tier")
        fssai: FSSAIInfo = Field(default_factory=FSSAIInfo)
        records: List[VerificationRecord] = Field(default_factory=list)

    class MasterUniversalSKU(BaseModel):
        """
        Proteindex Master Universal JSON Schema (PRD v2.1 Section 2)
        Every scraped SKU is normalized and validated against this contract.
        """
        skuId: str = Field(..., description="Unique deterministic SKU identifier")
        brand: str = Field(..., description="Manufacturer brand name")
        productName: str = Field(..., description="Base product formulation name")
        categorySilo: str = Field(..., description="Isolated silo: protein, mass_gainers, creatine, pre_workout")
        subCategory: str = Field(..., description="Specific subcategory formulation (e.g. Whey Isolate, Pea Protein)")
        flavor: str = Field(..., description="Canonical flavor")
        imageUrl: Optional[str] = Field(default=None, description="Product image URL")
        packaging: PackagingInfo
        nutritionalProfile: NutritionalProfile
        usefulDoseAnalysis: UsefulDoseAnalysis
        equalizerMetrics: EqualizerMetrics
        pricing: PricingSummary
        verification: VerificationInfo

except ImportError:
    # Graceful zero-dependency schema validation fallback
    class _AttrDict:
        def __init__(self, d: dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    setattr(self, k, _AttrDict(v))
                elif isinstance(v, list):
                    setattr(self, k, [_AttrDict(i) if isinstance(i, dict) else i for i in v])
                else:
                    setattr(self, k, v)
        def dict(self) -> dict:
            return self.__dict__
        def model_dump(self) -> dict:
            return self.__dict__

    class PackagingInfo(_AttrDict): pass
    class NutritionalProfile(_AttrDict): pass
    class UsefulDoseAnalysis(_AttrDict): pass
    class EqualizerMetrics(_AttrDict): pass
    class VendorOffer(_AttrDict): pass
    class PricingSummary(_AttrDict): pass
    class FSSAIInfo(_AttrDict): pass
    class VerificationRecord(_AttrDict): pass
    class VerificationInfo(_AttrDict): pass

    class MasterUniversalSKU(_AttrDict):
        @classmethod
        def model_validate(cls, data: dict):
            required = ["skuId", "brand", "productName", "categorySilo", "subCategory", "flavor", "packaging", "nutritionalProfile", "usefulDoseAnalysis", "equalizerMetrics", "pricing", "verification"]
            for r in required:
                if r not in data:
                    raise ValueError(f"Missing required field: {r}")
            return cls(data)
