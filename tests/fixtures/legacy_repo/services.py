"""Candidate business rules with source evidence."""
from repository import save_claim


class ClaimsService:
    def calculate_discount(self, age, membership_years, amount):
        if age >= 60 and membership_years >= 10:
            return amount * 0.15
        return 0

    def submit_claim(self, payload):
        if payload["amount"] <= 0:
            raise ValueError("Claim amount must be positive")
        discount = self.calculate_discount(
            payload["age"], payload["membershipYears"], payload["amount"]
        )
        return save_claim(payload["customerId"], payload["amount"] - discount)
