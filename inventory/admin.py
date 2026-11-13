from django.contrib import admin

from .models import (
    Equipment,
    Request,
    RequestItem,
    UserPermission
)


# =========================
# EQUIPMENT ADMIN
# =========================

class EquipmentAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'category',
        'model',
        'serial_number',
        'quantity',
        'status'
    )


admin.site.register(
    Equipment,
    EquipmentAdmin
)



# =========================
# REQUEST ADMIN
# =========================

class RequestAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'user',
        'department',
        'borrow_date',
        'return_date',
        'priority',
        'status',
        
    )


admin.site.register(
    Request,
    RequestAdmin
)



# =========================
# REQUEST ITEM ADMIN
# =========================

class RequestItemAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'request',
        'equipment',
        'quantity'
    )


admin.site.register(
    RequestItem,
    RequestItemAdmin
)



# =========================
# USER PERMISSION ADMIN
# =========================
@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):

    list_display = (
        "user",

        # Employee
        "employee_dashboard",
        "employee_home",
        "view_available",
        "create_request",
        "return_borrowed",

        # Storekeeper
        "storekeeper_dashboard",
        "storekeeper_home",
        "manage_equipment",
        "manage_requests",
        "return_equipment",
        "report",

        # Admin
        "admin_dashboard",
        "admin_home",
        "user_management",
        "role_management",
        "equipment_management",
        "request_management",
        "reports",
    )