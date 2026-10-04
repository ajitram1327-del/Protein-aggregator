import re

class IngredientAuditor:
    # Fillers that are often "fairy-dusted" (used in high quantities but presented as premium)
    # or just cheap bulking agents
    FILLERS = [
        "maltodextrin", "taurine", "glycine", "creatine monohydrate", 
        "dextrose", "sucrose", "sugar", "fructose", "corn syrup"
    ]
    
    # Premium actives that brands want you to think are the main ingredient
    ACTIVES = [
        "whey protein isolate", "whey isolate", "bcaa", "l-citrulline",
        "citrulline malate", "hydrolyzed whey", "micellar casein"
    ]
    
    @classmethod
    def audit(cls, raw_ingredients: str) -> dict:
        if not raw_ingredients:
            return {"is_fairy_dusted": False, "flags": [], "trust_deduction": 0}
            
        ingredients = [i.strip().lower() for i in re.split(r'[,|\[\]\(\)]', raw_ingredients) if i.strip()]
        
        flags = []
        deduction = 0
        
        # Check relative positions
        for filler in cls.FILLERS:
            try:
                # Find first occurrence of filler
                filler_idx = next(i for i, v in enumerate(ingredients) if filler in v)
            except StopIteration:
                continue
                
            for active in cls.ACTIVES:
                try:
                    active_idx = next(i for i, v in enumerate(ingredients) if active in v)
                except StopIteration:
                    continue
                    
                # If filler appears BEFORE active ingredient, it's fairy dusting
                if filler_idx < active_idx:
                    flags.append(f"Cheap filler '{filler}' listed before premium active '{active}'")
                    deduction += 15
        
        # Deduplicate flags
        flags = list(set(flags))
        
        return {
            "is_fairy_dusted": len(flags) > 0,
            "flags": flags,
            "trust_deduction": deduction
        }

if __name__ == "__main__":
    # Test case
    test_str = "Maltodextrin, Whey Protein Concentrate, Taurine, Cocoa Powder, Whey Protein Isolate, Sucralose"
    print(IngredientAuditor.audit(test_str))
