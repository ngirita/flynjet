from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

class PricingCalculator:
    """Calculate pricing for bookings"""
    
    BASE_TAX_RATE = Decimal('0.10')  # 10% tax
    PEAK_HOURS_MULTIPLIER = Decimal('1.25')  # 25% premium for peak hours
    OFF_PEAK_MULTIPLIER = Decimal('0.85')  # 15% discount for off-peak
    
    # Peak hours (weekdays 7-9 AM and 4-7 PM)
    PEAK_HOURS = {
        'morning_start': 7,
        'morning_end': 9,
        'evening_start': 16,
        'evening_end': 19
    }
    
    @classmethod
    def calculate_base_price(cls, aircraft, flight_hours, is_peak=False):
        """Calculate base price for flight"""
        hourly_rate = aircraft.hourly_rate_usd
        base = hourly_rate * Decimal(str(flight_hours))
        
        if is_peak:
            base *= cls.PEAK_HOURS_MULTIPLIER
        
        return base.quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_fuel_surcharge(cls, aircraft, flight_hours, fuel_price_per_gallon):
        """Calculate fuel surcharge"""
        fuel_consumption = aircraft.fuel_consumption_lph
        total_gallons = fuel_consumption * flight_hours
        return (Decimal(str(total_gallons)) * Decimal(str(fuel_price_per_gallon))).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_handling_fees(cls, departure_airport, arrival_airport):
        """Calculate airport handling fees"""
        # Simplified - in production, this would call an API
        base_handling = Decimal('500.00')
        return base_handling.quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_catering(cls, passenger_count, meal_preferences):
        """Calculate catering costs"""
        base_cost_per_pax = Decimal('75.00')
        premium_meal_multiplier = Decimal('1.5')
        
        total = base_cost_per_pax * Decimal(str(passenger_count))
        
        # Check for premium meal requests
        if meal_preferences and 'premium' in meal_preferences.lower():
            total *= premium_meal_multiplier
        
        return total.quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_overnight_charge(cls, aircraft, nights):
        """Calculate overnight parking charges"""
        return (aircraft.overnight_charge_usd * Decimal(str(nights))).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_discount(cls, base_price, loyalty_tier=None, promo_code=None):
        """Calculate applicable discounts"""
        discount = Decimal('0')
        
        # Loyalty tier discounts
        if loyalty_tier == 'bronze':
            discount += base_price * Decimal('0.05')  # 5%
        elif loyalty_tier == 'silver':
            discount += base_price * Decimal('0.10')  # 10%
        elif loyalty_tier == 'gold':
            discount += base_price * Decimal('0.15')  # 15%
        elif loyalty_tier == 'platinum':
            discount += base_price * Decimal('0.20')  # 20%
        
        # Promo code discounts would be handled separately
        
        return discount.quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_taxes(cls, subtotal):
        """Calculate taxes on subtotal"""
        return (subtotal * cls.BASE_TAX_RATE).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_total(cls, base_price, extras=None, discounts=None):
        """Calculate total price"""
        subtotal = base_price
        
        # Add extras
        if extras:
            subtotal += sum(extras)
        
        # Apply discounts
        if discounts:
            subtotal -= sum(discounts)
        
        # Add taxes
        taxes = cls.calculate_taxes(subtotal)
        
        return (subtotal + taxes).quantize(Decimal('0.01'))
    
    @classmethod
    def is_peak_hour(cls, datetime_obj):
        """Check if given datetime is during peak hours"""
        hour = datetime_obj.hour
        return (cls.PEAK_HOURS['morning_start'] <= hour <= cls.PEAK_HOURS['morning_end']) or \
               (cls.PEAK_HOURS['evening_start'] <= hour <= cls.PEAK_HOURS['evening_end'])

class InstallmentCalculator:
    """Calculate installment payment plans"""
    
    @classmethod
    def calculate_installments(cls, total_amount, num_installments=3, interest_rate=Decimal('0.05')):
        """Calculate installment amounts"""
        if num_installments <= 1:
            return [total_amount]
        
        # Calculate with interest
        total_with_interest = total_amount * (1 + interest_rate)
        installment_amount = (total_with_interest / Decimal(str(num_installments))).quantize(Decimal('0.01'))
        
        # Adjust last installment to ensure sum matches
        installments = [installment_amount] * (num_installments - 1)
        last_installment = total_with_interest - (installment_amount * (num_installments - 1))
        installments.append(last_installment.quantize(Decimal('0.01')))
        
        return installments
    
    @classmethod
    def get_installment_schedule(cls, total_amount, start_date, num_installments=3):
        """Get schedule of installment due dates"""
        installments = cls.calculate_installments(total_amount, num_installments)
        schedule = []
        
        for i, amount in enumerate(installments):
            due_date = start_date + timedelta(days=30 * (i + 1))
            schedule.append({
                'installment_number': i + 1,
                'amount': amount,
                'due_date': due_date,
                'status': 'pending'
            })
        
        return schedule