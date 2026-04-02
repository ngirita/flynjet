from django.db import models
from django.utils import timezone
from .models import Aircraft, AircraftMaintenance
import logging

logger = logging.getLogger(__name__)

class PartsInventory(models.Model):
    """Track aircraft parts inventory"""
    
    PART_CATEGORIES = (
        ('engine', 'Engine Parts'),
        ('avionics', 'Avionics'),
        ('landing_gear', 'Landing Gear'),
        ('hydraulic', 'Hydraulic System'),
        ('electrical', 'Electrical'),
        ('interior', 'Interior'),
        ('consumable', 'Consumables'),
        ('tool', 'Tools'),
    )
    
    part_number = models.CharField(max_length=100, unique=True)
    part_name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=PART_CATEGORIES)
    manufacturer = models.CharField(max_length=100)
    
    # Inventory counts
    quantity_on_hand = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)
    reorder_point = models.IntegerField(default=10)
    maximum_stock = models.IntegerField(default=100)
    
    # Location
    warehouse_location = models.CharField(max_length=50, blank=True)
    bin_location = models.CharField(max_length=50, blank=True)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.CharField(max_length=200)
    
    # Specifications
    applicable_aircraft = models.ManyToManyField(Aircraft, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_ordered = models.DateTimeField(null=True, blank=True)
    last_received = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['part_number']
        indexes = [
            models.Index(fields=['part_number']),
            models.Index(fields=['category']),
            models.Index(fields=['supplier']),
        ]
    
    def __str__(self):
        return f"{self.part_number} - {self.part_name}"
    
    @property
    def available_quantity(self):
        """Get available quantity (not reserved)"""
        return self.quantity_on_hand - self.quantity_reserved
    
    @property
    def needs_reorder(self):
        """Check if part needs to be reordered"""
        return self.available_quantity <= self.reorder_point
    
    def reserve(self, quantity):
        """Reserve parts for maintenance"""
        if quantity > self.available_quantity:
            raise ValueError(f"Insufficient available quantity. Available: {self.available_quantity}")
        
        self.quantity_reserved += quantity
        self.save(update_fields=['quantity_reserved'])
        
        logger.info(f"Reserved {quantity} of {self.part_number}")
    
    def release(self, quantity):
        """Release reserved parts"""
        if quantity > self.quantity_reserved:
            self.quantity_reserved = 0
        else:
            self.quantity_reserved -= quantity
        
        self.save(update_fields=['quantity_reserved'])
        logger.info(f"Released {quantity} of {self.part_number}")
    
    def receive(self, quantity, unit_cost=None):
        """Receive new stock"""
        self.quantity_on_hand += quantity
        if unit_cost:
            self.unit_cost = unit_cost
        self.last_received = timezone.now()
        self.save(update_fields=['quantity_on_hand', 'unit_cost', 'last_received'])
        
        logger.info(f"Received {quantity} of {self.part_number}")

class PartsOrder(models.Model):
    """Order for parts"""
    
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    )
    
    order_number = models.CharField(max_length=50, unique=True)
    supplier = models.CharField(max_length=200)
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Tracking
    tracking_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-order_date']
    
    def __str__(self):
        return f"Order {self.order_number} - {self.supplier}"
    
    def calculate_total(self):
        """Calculate order total"""
        items_total = self.items.aggregate(total=models.Sum('line_total'))['total'] or 0
        self.subtotal = items_total
        self.total = self.subtotal + self.tax + self.shipping
        self.save(update_fields=['subtotal', 'total'])
    
    def receive_order(self):
        """Receive all items in order"""
        for item in self.items.all():
            item.receive_item()
        
        self.status = 'received'
        self.received_date = timezone.now()
        self.save(update_fields=['status', 'received_date'])
        
        logger.info(f"Order {self.order_number} received")

class PartsOrderItem(models.Model):
    """Individual items in parts order"""
    
    order = models.ForeignKey(PartsOrder, on_delete=models.CASCADE, related_name='items')
    part = models.ForeignKey(PartsInventory, on_delete=models.PROTECT)
    
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    received_quantity = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def receive_item(self, quantity=None):
        """Receive this item"""
        receive_qty = quantity or self.quantity
        self.received_quantity += receive_qty
        
        # Update inventory
        self.part.receive(receive_qty, self.unit_price)
        
        self.save(update_fields=['received_quantity'])

class PartsUsage(models.Model):
    """Track parts used in maintenance"""
    
    maintenance = models.ForeignKey(AircraftMaintenance, on_delete=models.CASCADE, related_name='parts_used')
    part = models.ForeignKey(PartsInventory, on_delete=models.PROTECT)
    
    quantity = models.IntegerField()
    unit_price_at_time = models.DecimalField(max_digits=10, decimal_places=2)
    
    used_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    used_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity} x {self.part.part_number} for {self.maintenance}"

class InventoryAlert(models.Model):
    """Alerts for inventory issues"""
    
    ALERT_TYPES = (
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('expiring', 'Expiring Soon'),
        ('reorder', 'Reorder Recommended'),
    )
    
    part = models.ForeignKey(PartsInventory, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.CharField(max_length=255)
    
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.part.part_number}"
    
    def resolve(self):
        """Resolve alert"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save(update_fields=['is_resolved', 'resolved_at'])

class InventoryManager:
    """Manage inventory operations"""
    
    @classmethod
    def check_inventory_levels(cls):
        """Check all inventory levels and create alerts"""
        alerts = []
        
        for part in PartsInventory.objects.filter(is_active=True):
            if part.quantity_on_hand == 0:
                alert, created = InventoryAlert.objects.get_or_create(
                    part=part,
                    alert_type='out_of_stock',
                    defaults={'message': f"{part.part_number} is out of stock"}
                )
                if created:
                    alerts.append(alert)
            
            elif part.available_quantity <= part.reorder_point:
                alert, created = InventoryAlert.objects.get_or_create(
                    part=part,
                    alert_type='low_stock',
                    defaults={'message': f"{part.part_number} below reorder point. Current: {part.available_quantity}, Reorder at: {part.reorder_point}"}
                )
                if created:
                    alerts.append(alert)
        
        return alerts
    
    @classmethod
    def generate_recommended_orders(cls):
        """Generate recommended purchase orders based on inventory levels"""
        recommendations = []
        
        parts_needed = PartsInventory.objects.filter(
            is_active=True,
            quantity_on_hand__lte=models.F('reorder_point')
        ).exclude(
            quantity_on_hand__gte=models.F('maximum_stock')
        )
        
        for part in parts_needed:
            order_quantity = min(
                part.maximum_stock - part.quantity_on_hand,
                part.maximum_stock * 2  # Don't order more than double max
            )
            
            if order_quantity > 0:
                recommendations.append({
                    'part': part,
                    'recommended_quantity': order_quantity,
                    'estimated_cost': order_quantity * part.unit_cost,
                    'supplier': part.supplier,
                    'priority': 'high' if part.available_quantity == 0 else 'medium'
                })
        
        return recommendations
    
    @classmethod
    def calculate_inventory_value(cls):
        """Calculate total inventory value"""
        parts = PartsInventory.objects.filter(is_active=True)
        total = sum(p.quantity_on_hand * p.unit_cost for p in parts)
        
        return {
            'total_value': total,
            'total_parts': parts.count(),
            'total_quantity': sum(p.quantity_on_hand for p in parts),
        }