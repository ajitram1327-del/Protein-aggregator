import random
import time
from typing import List

class ReviewAuthenticityEngine:
    @staticmethod
    def jaccard_similarity(str1: str, str2: str) -> float:
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        if not set1 or not set2: return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union

    @classmethod
    def audit_reviews(cls, product_id: str) -> dict:
        """
        Mock implementation for PRD demonstration.
        In production, this would scrape the latest 100 5-star reviews from Amazon/Flipkart.
        Here we generate a synthetic cluster to demonstrate Jaccard overlap detection.
        """
        # Simulate fetching reviews
        time.sleep(0.5)
        
        # We'll randomly decide if this product is botted
        is_botted = random.random() > 0.7
        
        if is_botted:
            reviews = [
                "Great product fast delivery amazing results",
                "Great product fast delivery amazing results highly recommend",
                "Good product fast delivery amazing results",
                "Best protein ever, fast delivery amazing results",
                "Very nice product fast delivery amazing results"
            ]
        else:
            reviews = [
                "Tastes pretty good, mixes well with milk.",
                "Fast delivery. The chocolate flavor is okay but a bit sweet.",
                "My go-to whey protein, helps with recovery after leg days.",
                "Solid macro profile. Scoop was buried at the bottom though.",
                "Not bad for the price, will probably buy again."
            ]
            
        copy_paste_flags = 0
        clusters = 0
        
        # Simple pairwise check
        for i in range(len(reviews)):
            for j in range(i + 1, len(reviews)):
                sim = cls.jaccard_similarity(reviews[i], reviews[j])
                if sim > 0.65:
                    copy_paste_flags += 1
                    
        # Simulate temporal clustering (5 reviews in 24h)
        if is_botted:
            clusters += 1
            
        score = 100 - (clusters * 10) - (copy_paste_flags * 5)
        score = max(0, min(100, score))
        
        return {
            "authenticity_score": score,
            "has_bot_reviews": score < 60,
            "copy_paste_flags": copy_paste_flags,
            "temporal_clusters": clusters
        }

if __name__ == "__main__":
    print(ReviewAuthenticityEngine.audit_reviews("test_sku_123"))
