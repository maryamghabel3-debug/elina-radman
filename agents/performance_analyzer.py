"""
Performance & Analytics Agent (The Strategist)
Monitors post-upload metrics (views, retention, CTR, sentiment of comments).
Uses this data to pivot strategies, suggest new hooks, or tweak the editing style for Elina.
"""
import random
import os
import json
from datetime import datetime

class PerformanceAnalyzer:
    def __init__(self):
        self.name = "PerformanceAnalyzer"
        self.metrics_db = "content/performance_metrics.json"

    def analyze_past_performance(self):
        print(f"📊 [{self.name}] Analyzing Elina's recent content performance...")
        
        # Simulating fetching real data from Instagram Insights / YouTube Analytics
        metrics = {
            "recent_views": random.randint(10000, 500000),
            "ctr": round(random.uniform(3.5, 12.0), 1),
            "retention_dropoff": "Seconds 3 to 5",
            "audience_retention": "72%",
            "top_comment_keywords": ["outfit link", "love this", "where to buy", "so aesthetic"],
            "sentiment": "85% Positive, 15% Inquiring"
        }
        
        print(f"   📈 Data Pulled: {metrics['recent_views']} Views | CTR: {metrics['ctr']}% | Retention: {metrics['audience_retention']}")
        
        strategy_fixes = []
        
        # 1. Check CTR (Click-Through Rate)
        if metrics["ctr"] < 5.0:
            strategy_fixes.append("THUMBNAIL_FIX: CTR is dropping. Make Elina's face larger in the first frame and use higher contrast.")
        else:
            strategy_fixes.append("THUMBNAIL_KEEP: Aesthetic is working well. Keep current hook styles.")

        # 2. Check Retention
        if "Seconds 3 to 5" in metrics["retention_dropoff"]:
            strategy_fixes.append("HOOK_FIX: Audience drop at second 4. Add a camera angle change or subtle BGM shift right before second 4.")

        # 3. Check Comments (Affiliate intent)
        if "where to buy" in metrics["top_comment_keywords"] or "outfit link" in metrics["top_comment_keywords"]:
            strategy_fixes.append("SALES_FIX: High purchase intent! Ensure ContentCreator heavily pushes LTK/Amazon affiliate links in the next 3 posts.")

        print(f"   💡 New Strategy Generated for Elina: {strategy_fixes}")
        
        # Save analysis
        os.makedirs(os.path.dirname(self.metrics_db), exist_ok=True)
        with open(self.metrics_db, "w") as f:
            json.dump({"date": datetime.now().isoformat(), "metrics": metrics, "strategy": strategy_fixes}, f, indent=2)
            
        return strategy_fixes
