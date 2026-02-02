class TierService:

    @staticmethod
    def get_tier(total_spent: float) -> str:
        total_spent = float(total_spent or 0)

        if total_spent >= 8000:
            return "Premium"
        elif total_spent >= 2000:
            return "Standard"
        return "Budget"
