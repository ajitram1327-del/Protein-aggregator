class SellerMatrix:
    # Known authorized distributors for major brands on Amazon/Flipkart
    AUTHORIZED_SELLERS = [
        "cocoblu retail", "cocoblu", 
        "supercomnet", "supercom net",
        "retailnetz", "retail netz",
        "rk world infocom",
        "appario retail",
        "nutrabay", "healthkart", "hyugalife" # Direct platforms
    ]
    
    @classmethod
    def verify_seller(cls, seller_name: str, brand: str) -> bool:
        if not seller_name:
            # If we couldn't scrape it, default to True so we don't accidentally block valid items
            # In production, we might want to default to False for stricter security
            return True
            
        normalized_seller = seller_name.lower().strip()
        
        # Check against whitelist
        for auth_seller in cls.AUTHORIZED_SELLERS:
            if auth_seller in normalized_seller:
                return True
                
        # Check if the brand itself is selling it (e.g., "Optimum Nutrition Official")
        if brand.lower().strip() in normalized_seller:
            return True
            
        # If it doesn't match the whitelist or the brand name, it's unauthorized
        return False
