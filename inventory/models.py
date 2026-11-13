from django.db import models
from django.contrib.auth.models import User


# =========================
# EQUIPMENT TABLE
# =========================

class Equipment(models.Model):

    CATEGORY_CHOICES = [
        ('Camera', 'Camera'),
        ('Microphone', 'Microphone'),
        ('Lighting', 'Lighting'),
        ('Drone', 'Drone'),
    ]

    name = models.CharField(
        max_length=100
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    model = models.CharField(
        max_length=100
    )

    serial_number = models.CharField(
        max_length=100,
        unique=True
    )

    quantity = models.IntegerField(
        default=1
    )

    available_quantity = models.IntegerField(
        default=0
    )

    status = models.CharField(
        max_length=50,
        default="Available"
    )

    image = models.ImageField(
        upload_to="equipment/",
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.name} ({self.model})"


# =========================
# REQUEST TABLE
# =========================

class Request(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Borrowed', 'Borrowed'),
        ('Returned', 'Returned'),
        ('Expired', 'Time Limit Expired'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="equipment_requests"
    )

    employee_id = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    department = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    category = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    quantity = models.IntegerField(
        default=1
    )

    borrow_date = models.DateField(
        null=True,
        blank=True
    )

    return_date = models.DateField(
        null=True,
        blank=True
    )

    priority = models.CharField(
        max_length=20,
        default="Normal"
    )

    purpose = models.TextField(
        null=True,
        blank=True
    )

    # =========================
    # REQUEST STATUS
    # =========================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    # =========================
    # APPROVAL TIME
    # Used for 6-hour limit
    # =========================

    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # =========================
    # REQUEST CREATION TIME
    # =========================

    request_date = models.DateTimeField(
        auto_now_add=True
    )

    # =========================
    # REJECTION INFORMATION
    # =========================

    rejection_reason = models.TextField(
        blank=True,
        null=True
    )

    rejection_message = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.status}"


# =========================
# REQUEST ITEM TABLE
# =========================

class RequestItem(models.Model):

    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="request_items"
    )

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="requested_items"
    )

    quantity = models.IntegerField(
        default=1
    )

    def __str__(self):
        return f"{self.equipment.name} x {self.quantity}"


# =========================
# USER PERMISSION
# =========================

class UserPermission(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    # =========================
    # EMPLOYEE DASHBOARD
    # =========================

    employee_dashboard = models.BooleanField(
        default=False
    )

    employee_home = models.BooleanField(
        default=False
    )

    view_available = models.BooleanField(
        default=False
    )

    create_request = models.BooleanField(
        default=False
    )

    return_borrowed = models.BooleanField(
        default=False
    )

    employee_logout = models.BooleanField(
        default=True
    )


    # =========================
    # STOREKEEPER DASHBOARD
    # =========================

    storekeeper_dashboard = models.BooleanField(
        default=False
    )

    storekeeper_home = models.BooleanField(
        default=False
    )

    manage_equipment = models.BooleanField(
        default=False
    )

    manage_requests = models.BooleanField(
        default=False
    )

    return_equipment = models.BooleanField(
        default=False
    )

    report = models.BooleanField(
        default=False
    )

    storekeeper_logout = models.BooleanField(
        default=True
    )


    # =========================
    # ADMIN DASHBOARD
    # =========================

    admin_dashboard = models.BooleanField(
        default=False
    )

    admin_home = models.BooleanField(
        default=False
    )

    user_management = models.BooleanField(
        default=False
    )

    role_management = models.BooleanField(
        default=False
    )

    equipment_management = models.BooleanField(
        default=False
    )

    request_management = models.BooleanField(
        default=False
    )

    reports = models.BooleanField(
        default=False
    )

    admin_logout = models.BooleanField(
        default=True
    )


    def __str__(self):
        return self.user.username
    
# =========================
# EQUIPMENT MAINTENANCE
# =========================

class Maintenance(models.Model):

    MAINTENANCE_TYPES = [
        ("Repair", "Repair"),
        ("Inspection", "Inspection"),
        ("Cleaning", "Cleaning"),
        ("Replacement", "Replacement"),
        ("Other", "Other"),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
    ]

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="maintenance_records"
    )

    maintenance_type = models.CharField(
        max_length=50,
        choices=MAINTENANCE_TYPES
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    maintenance_date = models.DateField()

    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.equipment.name} - {self.maintenance_type}"
