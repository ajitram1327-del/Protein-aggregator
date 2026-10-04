import datetime
from typing import Dict, Any

class ExpiryArbitrageEngine:
    """
    Near-Expiry Clearance Arbitrage Engine (PRD Master Section 10.2).
    Evaluates temporal consumption forecasting vs expiration delta to prevent
    users from buying clearance items they cannot finish safely before expiry.
    """

    @classmethod
    def audit_clearance(
        cls,
        expiry_date_str: str,
        total_servings: int,
        user_scoops_per_day: float = 1.0,
        discount_pct: float = 0.0,
        current_date: datetime.date = None
    ) -> Dict[str, Any]:
        """
        Calculates whether a clearance discount is safe for consumer purchase.
        Safety buffer: 1 full month buffer after expected completion date.
        """
        now = current_date or datetime.date.today()
        
        # Parse expiry date (supports YYYY-MM-DD or MM/YYYY)
        try:
            if "-" in expiry_date_str:
                parts = [int(p) for p in expiry_date_str.split("-")]
                if len(parts) == 3:
                    exp_date = datetime.date(parts[0], parts[1], parts[2])
                elif len(parts) == 2:
                    exp_date = datetime.date(parts[0], parts[1], 28)
                else:
                    return cls._fallback_response()
            elif "/" in expiry_date_str:
                parts = [int(p) for p in expiry_date_str.split("/")]
                if len(parts) == 2:
                    exp_date = datetime.date(parts[1], parts[0], 28)
                else:
                    return cls._fallback_response()
            else:
                return cls._fallback_response()
        except Exception:
            return cls._fallback_response()

        # Delta calculation in months
        days_to_expiry = (exp_date - now).days
        months_to_expiry = days_to_expiry / 30.4375

        # Consumption rate
        scoops_per_day = max(0.5, float(user_scoops_per_day))
        days_to_finish = total_servings / scoops_per_day
        months_to_finish = days_to_finish / 30.4375

        # Strict 1-month safety buffer rule
        is_safe_for_consumption = months_to_expiry > (months_to_finish + 1.0)
        is_clearance = discount_pct >= 25.0 and months_to_expiry <= 5.0

        return {
            "is_clearance": is_clearance,
            "is_safe_for_consumption": is_safe_for_consumption,
            "months_to_expiry": round(months_to_expiry, 1),
            "months_to_finish": round(months_to_finish, 1),
            "safety_buffer_months": round(months_to_expiry - months_to_finish, 1),
            "recommendation": "SAFE_CLEARANCE" if (is_clearance and is_safe_for_consumption) else (
                "EXPIRED_OR_RISK" if not is_safe_for_consumption else "REGULAR_INVENTORY"
            )
        }

    @staticmethod
    def _fallback_response() -> Dict[str, Any]:
        return {
            "is_clearance": False,
            "is_safe_for_consumption": True,
            "months_to_expiry": 12.0,
            "months_to_finish": 1.0,
            "safety_buffer_months": 11.0,
            "recommendation": "UNKNOWN_DATE"
        }
