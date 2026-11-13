# ============================================================
# IMPORTS
# ============================================================

import json
import profile
from datetime import timedelta
import calendar
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from django.contrib import messages

from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from django.db.models import Sum, Count, Q

from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from .models import (
    Equipment,
    Request,
    RequestItem,
    UserPermission
)
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from functools import wraps


def home(request):

    equipment = Equipment.objects.all()

    total_equipment = sum(
        item.quantity for item in equipment
    )

    total_available = sum(
        item.available_quantity
        for item in equipment
        if item.status in ["Available", "Low Stock"]
    )

    total_maintenance = sum(
        item.quantity
        for item in equipment
        if item.status == "Maintenance"
    )

    total_in_use = max(
        0,
        total_equipment - total_available - total_maintenance
    )

    equipment_list = Equipment.objects.filter(
        status__in=["Available", "Low Stock"],
        available_quantity__gt=0
    )

    return render(request, "inventory/home.html", {
        "equipment_list": equipment_list,
        "total_equipment": total_equipment,
        "total_available": total_available,
        "total_in_use": total_in_use,
        "total_maintenance": total_maintenance,
    })
# ============================================================
# VIEW AVAILABLE EQUIPMENT
# ============================================================

@login_required
def view_available(request):

    equipments = Equipment.objects.filter(
        status__in=["Available", "Low Stock"],
        available_quantity__gt=0
    ).order_by("name")

    for equipment in equipments:
        if equipment.status != "Maintenance":
            if equipment.available_quantity < 5:
                equipment.status = "Low Stock"
            else:
                equipment.status = "Available"

            equipment.save(update_fields=["status"])

    return render(
        request,
        "inventory/view_available.html",
        {
            "equipments": equipments
        }
    )
# ============================================================
# LOGIN
# ============================================================

def login_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            # ADMIN
            if user.groups.filter(
                name="admin"
            ).exists():

                return redirect(
                    "admin_dashboard"
                )

            # STORE KEEPER
            elif user.groups.filter(
                name="Store Keeper"
            ).exists():

                return redirect(
                    "storekeeper_dashboard"
                )

            # EMPLOYEE
            elif user.groups.filter(
                name="employee"
            ).exists():

                return redirect(
                    "user_dashboard"
                )

            else:

                return redirect(
                    "user_dashboard"
                )

        else:

            messages.error(
                request,
                "Invalid username or password."
            )

    return render(
        request,
        "inventory/login.html"
    )


# ============================================================
# REGISTER
# ============================================================

def register(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        if password != password2:
            messages.error(
                request,
                "Passwords do not match."
            )
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                "Username already exists."
            )
            return redirect("register")

        # Find the highest existing employee ID number
        existing_ids = UserPermission.objects.exclude(
            employee_id__isnull=True
        ).exclude(
            employee_id=""
        ).values_list(
            "employee_id",
            flat=True
        )

        numbers = [
            int(emp_id[3:])
            for emp_id in existing_ids
            if emp_id.startswith("EMP")
            and emp_id[3:].isdigit()
        ]

        next_number = max(numbers, default=0) + 1
        new_employee_id = f"EMP{next_number:03d}"

        # Create the user account
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Assign employee group
        employee_group = Group.objects.get(
            name="employee"
        )
        user.groups.add(employee_group)

        # Create or update the user's permission profile
        permission, created = UserPermission.objects.get_or_create(
            user=user
        )

        permission.employee_id = new_employee_id
        permission.save()

        messages.success(
            request,
            f"Account created successfully. Your Employee ID is {new_employee_id}."
        )

        return redirect("login")

    return render(
        request,
        "inventory/register.html"
    )


# ============================================================
# USER DASHBOARD
# ============================================================

@login_required
def user_dashboard(request):

    user_requests = Request.objects.filter(
        user=request.user
    ).prefetch_related(
        "request_items__equipment"
    ).order_by("-id")

    pending_count = user_requests.filter(
        status="Pending"
    ).count()

    approved_count = user_requests.filter(
        status="Approved"
    ).count()

    borrowed_count = user_requests.filter(
        status="Borrowed"
    ).count()

    return render(
        request,
        "inventory/userdashboard.html",
        {
            "user_requests": user_requests,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "borrowed_count": borrowed_count,
        }
    )

# ============================================================
# CREATE REQUEST
# ============================================================

@login_required
def create_request(request):

    # Get or create the employee's profile
    profile, created = UserPermission.objects.get_or_create(
        user=request.user
    )

    # Generate an ID for an existing employee if missing
    if not profile.employee_id:

        existing_ids = UserPermission.objects.exclude(
            employee_id__isnull=True
        ).exclude(
            employee_id=""
        ).values_list(
            "employee_id",
            flat=True
        )

        numbers = [
            int(emp_id[3:])
            for emp_id in existing_ids
            if emp_id.startswith("EMP")
            and emp_id[3:].isdigit()
        ]

        next_number = max(numbers, default=0) + 1
        profile.employee_id = f"EMP{next_number:03d}"
        profile.save()

    equipments = Equipment.objects.all()

    if request.method == "POST":

        items = request.POST.getlist("items")

        # ----------------------------------------------------
        # CHECK IF EQUIPMENT WAS SELECTED
        # ----------------------------------------------------

        if not items:

            messages.error(
                request,
                "Please select at least one equipment."
            )

            return redirect("create_request")

        # ----------------------------------------------------
        # CHECK STOCK BEFORE CREATING REQUEST
        # ----------------------------------------------------

        selected_items = []

        for item_id in items:

            equipment = get_object_or_404(
                Equipment,
                id=item_id
            )

            # ------------------------------------------------
            # GET QUANTITY
            # ------------------------------------------------

            quantity_value = request.POST.get(
                f"quantity_{equipment.id}",
                "1"
            )

            try:

                quantity = int(
                    quantity_value
                )

            except (ValueError, TypeError):

                quantity = 1

            # ------------------------------------------------
            # CHECK QUANTITY
            # ------------------------------------------------

            if quantity < 1:

                messages.error(
                    request,
                    f"Quantity for {equipment.name} "
                    f"must be at least 1."
                )

                return redirect(
                    "create_request"
                )

            # ------------------------------------------------
            # CHECK EQUIPMENT STATUS
            # ------------------------------------------------

            if equipment.status == "Maintenance":

                messages.error(
                    request,
                    f"{equipment.name} is currently under "
                    f"maintenance and cannot be requested."
                )

                return redirect(
                    "create_request"
                )

            # ------------------------------------------------
            # CHECK AVAILABLE STOCK
            # ------------------------------------------------

            if quantity > equipment.available_quantity:

                messages.error(
                    request,
                    f"Not enough stock for {equipment.name}. "
                    f"Only {equipment.available_quantity} available."
                )

                return redirect(
                    "create_request"
                )

            # ------------------------------------------------
            # SAVE SELECTED EQUIPMENT
            # ------------------------------------------------

            selected_items.append(
                (equipment, quantity)
            )

        # ----------------------------------------------------
        # TOTAL REQUEST QUANTITY
        # ----------------------------------------------------

        total_quantity = sum(
            quantity
            for equipment, quantity in selected_items
        )

        # ----------------------------------------------------
        # CREATE REQUEST
        # ----------------------------------------------------

        new_request = Request.objects.create(

            user=request.user,

           employee_id=profile.employee_id,

            department=request.POST.get(
                "department"
            ),

            phone=request.POST.get(
                "phone"
            ),

            category=request.POST.get(
                "category"
            ),

            quantity=total_quantity,

            priority=request.POST.get(
                "priority"
            ),

            borrow_date=request.POST.get(
                "borrow_date"
            ),

            return_date=request.POST.get(
                "return_date"
            ),

            purpose=request.POST.get(
                "purpose"
            ),

            status="Pending"
        )

        # ----------------------------------------------------
        # CREATE REQUEST ITEMS
        # ----------------------------------------------------

        for equipment, quantity in selected_items:

            RequestItem.objects.create(

                request=new_request,

                equipment=equipment,

                quantity=quantity
            )

        # ----------------------------------------------------
        # CHECK LOW STOCK
        # ----------------------------------------------------

        low_stock_items = []

        for equipment, quantity in selected_items:

            remaining = (
                equipment.available_quantity
                - quantity
            )

            if remaining < 5:

                low_stock_items.append(
                    f"{equipment.name}: "
                    f"only {remaining} remaining"
                )

               # ----------------------------------------------------
        # SUCCESS MESSAGE
        # ----------------------------------------------------

        if low_stock_items:

            messages.warning(
                request,
                "Equipment request submitted successfully. "
                "Low stock: "
                + ", ".join(low_stock_items)
            )

        else:

            messages.success(
                request,
                "Equipment request submitted successfully."
            )

        return redirect("user_dashboard")

    # ----------------------------------------------------
    # DISPLAY REQUEST FORM
    # ----------------------------------------------------

    return render(
        request,
        "inventory/create_request.html",
        {
            "equipments": equipments,
            "employee_id": profile.employee_id
        }
    )

# ============================================================
# RETURN BORROWED AND RETURN HISTORY
# ============================================================

@login_required
def return_borrowed(request):

    # Current borrowed equipment
    borrowed_items = RequestItem.objects.filter(
        request__user=request.user,
        request__status="Borrowed"
    ).select_related(
        "request",
        "equipment"
    ).order_by("-request__id")


    # Equipment already returned
    returned_items = RequestItem.objects.filter(
        request__user=request.user,
        request__status="Returned"
    ).select_related(
        "request",
        "equipment"
    ).order_by("-request__id")


    return render(
        request,
        "inventory/return_borrowed.html",
        {
            "borrowed_items": borrowed_items,
            "returned_items": returned_items
        }
    )
# ============================================================
# REQUEST DETAIL
# ============================================================

@login_required
def request_detail(request, id):

    req = get_object_or_404(
        Request,
        id=id
    )

    return render(
        request,
        "inventory/request_detail.html",
        {
            "req": req
        }
    )


# ============================================================
# LOGOUT
# ============================================================

def logout_view(request):

    logout(request)

    return redirect(
        "home"
    )


# ============================================================
# STORE KEEPER DASHBOARD
# ============================================================

@login_required
def storekeeper_dashboard(request):

    requests = Request.objects.all().order_by(
        "-request_date"
    )

    context = {

        "requests": requests,

        "pending_count":
            Request.objects.filter(
                status="Pending"
            ).count(),

        "approved_count":
            Request.objects.filter(
                status="Approved"
            ).count(),

        "borrowed_count":
            Request.objects.filter(
                status="Borrowed"
            ).count(),

        "low_stock":
    Equipment.objects.filter(
        available_quantity__lt=5
    )
    }

    return render(
        request,
        "inventory/storekeeper_dashboard.html",
        context
    )


# ============================================================
# APPROVE REQUEST
# ============================================================

@login_required
def approve_request(request, id):

    req = get_object_or_404(
        Request,
        id=id
    )

    # --------------------------------------------------------
    # ONLY PENDING REQUESTS CAN BE APPROVED
    # --------------------------------------------------------

    if req.status != "Pending":

        messages.warning(
            request,
            f"This request is already {req.status}."
        )

        return redirect(
            "manage_requests"
        )

    # --------------------------------------------------------
    # CHECK EQUIPMENT QUANTITY AGAIN
    # --------------------------------------------------------

    for item in req.request_items.all():

        equipment = item.equipment

        if equipment.status == "Maintenance":

            messages.error(
                request,
                f"{equipment.name} is currently under maintenance."
            )

            return redirect(
                "manage_requests"
            )

        if equipment.available_quantity < item.quantity:

            messages.error(
                request,
                f"{equipment.name} does not have enough "
                f"available quantity."
            )

            return redirect(
                "manage_requests"
            )

    # --------------------------------------------------------
    # APPROVE REQUEST
    # --------------------------------------------------------

    req.status = "Approved"

    req.approved_at = timezone.now()

    req.save(
        update_fields=[
            "status",
            "approved_at"
        ]
    )

  
    return redirect(
        "manage_requests"
    )


# ============================================================
# REJECT REQUEST
# ============================================================

@login_required
def reject_request(request, id):

    req = get_object_or_404(
        Request,
        id=id
    )

    if request.method == "POST":

        reasons = request.POST.getlist(
            "reasons"
        )

        message = request.POST.get(
            "rejection_message",
            ""
        ).strip()

        reason_text = ", ".join(
            reasons
        )

        if not reason_text:

            reason_text = (
                "No specific reason provided."
            )

        req.status = "Rejected"

        req.rejection_reason = (
            reason_text
        )

        req.rejection_message = (
            message
        )

        req.save()

        messages.success(
            request,
            "Request rejected successfully."
        )

        return redirect(
            "manage_requests"
        )

    return redirect(
        "manage_requests"
    )


# ============================================================
# MANAGE REQUESTS
# ============================================================

@login_required
def manage_requests(request):

    requests = Request.objects.all().order_by(
        "-request_date"
    )

    # --------------------------------------------------------
    # CHECK 6-HOUR APPROVAL TIME LIMIT
    # --------------------------------------------------------

    now = timezone.now()

    for req in requests:

        if (
            req.status == "Approved"
            and req.approved_at
        ):

            time_passed = (
                now - req.approved_at
            )

            if time_passed.total_seconds() >= (
                6 * 60 * 60
            ):

                req.status = "Expired"

                req.save(
                    update_fields=["status"]
                )

    requests = Request.objects.all().order_by(
        "-request_date"
    )

    return render(
        request,
        "inventory/manage_requests.html",
        {
            "requests": requests
        }
    )


# ============================================================
# MANAGE EQUIPMENT
# ============================================================

@login_required
def manage_equipment(request):

    equipments = Equipment.objects.all()

    return render(
        request,
        "inventory/manage_equipment.html",
        {
            "equipments": equipments
        }
    )


# ============================================================
# ADD EQUIPMENT
# ============================================================

@login_required
def add_equipment(request):

    if request.method == "POST":

        serial = request.POST.get(
            "serial_number"
        )

        try:

            quantity = int(
                request.POST.get(
                    "quantity",
                    0
                )
            )

        except (ValueError, TypeError):

            quantity = 0

        if quantity < 1:

            messages.error(
                request,
                "Quantity must be at least 1."
            )

            return redirect(
                "manage_equipment"
            )

        update_existing = request.POST.get(
            "update_existing"
        )

        equipment = Equipment.objects.filter(
            serial_number=serial
        ).first()

        # ----------------------------------------------------
        # EXISTING EQUIPMENT
        # ----------------------------------------------------

        if equipment:

            if update_existing:

                equipment.quantity += quantity

                equipment.available_quantity += quantity

                equipment.status = "Available"

                equipment.save()

                messages.success(
                    request,
                    f"Quantity updated successfully. "
                    f"New quantity: {equipment.quantity}"
                )

            else:

                messages.warning(
                    request,
                    f"This serial number already exists. "
                    f"Equipment: {equipment.name}. "
                    f"Current quantity: {equipment.quantity}."
                )

            return redirect(
                "manage_equipment"
            )

        # ----------------------------------------------------
        # NEW EQUIPMENT
        # ----------------------------------------------------

        Equipment.objects.create(

            name=request.POST.get(
                "name"
            ),

            category=request.POST.get(
                "category"
            ),

            model=request.POST.get(
                "model"
            ),

            serial_number=serial,

            quantity=quantity,

            available_quantity=quantity,

            status="Available"
        )

        messages.success(
            request,
            "Equipment added successfully."
        )

        return redirect(
            "manage_equipment"
        )

    return redirect(
        "manage_equipment"
    )


# ============================================================
# UPDATE EQUIPMENT STATUS
# ============================================================

@login_required
def update_equipment_status(request, id):

    equipment = get_object_or_404(
        Equipment,
        id=id
    )

    if request.method == "POST":

        new_status = request.POST.get(
            "status"
        )

        equipment.status = new_status

        equipment.save()

        messages.success(
            request,
            "Equipment status updated successfully."
        )

    return redirect(
        "manage_equipment"
    )


# ============================================================
# PROCESS CHECKOUT
# ============================================================

@login_required
def process_checkout(request, id):

    req = get_object_or_404(
        Request,
        id=id
    )

    # --------------------------------------------------------
    # ONLY APPROVED REQUESTS CAN BE CHECKED OUT
    # --------------------------------------------------------

    if req.status != "Approved":

        messages.warning(
            request,
            f"This request cannot be checked out because "
            f"its status is {req.status}."
        )

        return redirect(
            "manage_requests"
        )

    # --------------------------------------------------------
    # CHECK STOCK AGAIN BEFORE CHECKOUT
    # --------------------------------------------------------

    for item in req.request_items.all():

        equipment = item.equipment

        if equipment.status == "Maintenance":

            messages.error(
                request,
                f"{equipment.name} is under maintenance."
            )

            return redirect(
                "manage_requests"
            )

        if equipment.available_quantity < item.quantity:

            messages.error(
                request,
                f"Not enough available stock for "
                f"{equipment.name}."
            )

            return redirect(
                "manage_requests"
            )

    # --------------------------------------------------------
    # REDUCE AVAILABLE STOCK
    # --------------------------------------------------------

    for item in req.request_items.all():

        equipment = item.equipment

        equipment.available_quantity -= (
            item.quantity
        )

        if equipment.available_quantity < 0:

            equipment.available_quantity = 0

        equipment.save()

    # --------------------------------------------------------
    # SET BORROWED
    # --------------------------------------------------------

    req.status = "Borrowed"

    req.save(
        update_fields=["status"]
    )

    messages.success(
        request,
        "Equipment checked out successfully."
    )

    return redirect(
        "manage_requests"
    )


# ============================================================
# PROCESS RETURN - EMPLOYEE
# ============================================================

@login_required
def process_return(request, id):

    req = get_object_or_404(
        Request,
        id=id,
        user=request.user
    )

    # --------------------------------------------------------
    # ONLY BORROWED REQUESTS CAN BE RETURNED
    # --------------------------------------------------------

    if req.status != "Borrowed":

        messages.warning(
            request,
            "This equipment is not currently borrowed."
        )

        return redirect(
            "return_borrowed"
        )

    # --------------------------------------------------------
    # RETURN EQUIPMENT
    # --------------------------------------------------------

    for item in req.request_items.all():

        equipment = item.equipment

        # IMPORTANT:
        # Do NOT increase equipment.quantity here.
        # quantity = total physical stock.
        # available_quantity = currently available stock.

        equipment.available_quantity += (
            item.quantity
        )

        if equipment.available_quantity > equipment.quantity:

            equipment.available_quantity = (
                equipment.quantity
            )

        if equipment.available_quantity > 0:

            equipment.status = "Available"

        equipment.save()

    req.status = "Returned"

    req.save(
        update_fields=["status"]
    )

    messages.success(
        request,
        "Equipment returned successfully."
    )

    return redirect(
        "return_borrowed"
    )

# ============================================================
# STORE KEEPER RETURN PAGE
# ============================================================

@login_required
def storekeeper_return(request):

    # Equipment waiting for return confirmation
    borrowed_items = Request.objects.filter(
        status="Borrowed"
    ).select_related(
        "user"
    ).prefetch_related(
        "request_items__equipment"
    ).order_by(
        "-borrow_date"
    )


    # Equipment already returned
    returned_items = Request.objects.filter(
        status="Returned"
    ).select_related(
        "user"
    ).prefetch_related(
        "request_items__equipment"
    ).order_by(
        "-borrow_date"
    )


    return render(
        request,
        "inventory/storekeeper_return.html",
        {
            "borrowed_items": borrowed_items,
            "returned_items": returned_items
        }
    )

# ============================================================
# CONFIRM RETURN
# ============================================================

@login_required
def confirm_return(request, id):

    req = get_object_or_404(
        Request,
        id=id
    )

    if req.status != "Borrowed":

        messages.warning(
            request,
            "This request is not currently borrowed."
        )

        return redirect(
            "storekeeper_return"
        )

    # --------------------------------------------------------
    # RETURN EQUIPMENT TO AVAILABLE STOCK
    # --------------------------------------------------------

    for item in req.request_items.all():

        equipment = item.equipment

        equipment.available_quantity += (
            item.quantity
        )

        if equipment.available_quantity > equipment.quantity:

            equipment.available_quantity = (
                equipment.quantity
            )

        if equipment.available_quantity > 0:

            equipment.status = "Available"

        equipment.save()

    req.status = "Returned"

    req.save(
        update_fields=["status"]
    )

    messages.success(
        request,
        "Equipment returned successfully."
    )

    return redirect(
        "storekeeper_return"
    )

## ============================================================
# BASIC REPORT
# ============================================================

@login_required
def report(request):

    # ALL EQUIPMENT
    equipments = Equipment.objects.all()

    # TOTAL EQUIPMENT
    total_equipment = Equipment.objects.aggregate(
        total=Sum("quantity")
    )["total"] or 0

    # AVAILABLE EQUIPMENT
    available_equipment = Equipment.objects.aggregate(
        total=Sum("available_quantity")
    )["total"] or 0

    # BORROWED REQUESTS
    borrowed_equipment = Request.objects.filter(
        status="Borrowed"
    ).count()

    # PENDING REQUESTS
    pending_requests = Request.objects.filter(
        status="Pending"
    ).count()

    # ALL REQUESTS
    all_requests = Request.objects.select_related(
        "user"
    ).prefetch_related(
        "request_items__equipment"
    ).order_by("-id")

    # LOW STOCK EQUIPMENT
    low_stock_items = Equipment.objects.filter(
        available_quantity__lt=5
    ).exclude(
        status="Maintenance"
    )

    # MAINTENANCE EQUIPMENT
    maintenance_items = Equipment.objects.filter(
        status="Maintenance"
    )

    # REPORT DATA
    context = {

        "equipments": equipments,
        "total_equipment": total_equipment,
        "available_equipment": available_equipment,
        "borrowed_equipment": borrowed_equipment,
        "pending_requests": pending_requests,
        "all_requests": all_requests,
        "low_stock_items": low_stock_items,
        "maintenance_items": maintenance_items,

    }

    return render(
        request,
        "inventory/report.html",
        context
    )
# ============================================================
# REPORT PDF
# ============================================================

@login_required
def report_pdf(request):

    response = HttpResponse(
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        'attachment; filename="Inventory_Report.pdf"'
    )

    pdf = canvas.Canvas(
        response
    )

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawString(
        40,
        800,
        "AMN Camera Store Inventory Report"
    )

    y = 760

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        40,
        y,
        "Equipment"
    )

    pdf.drawString(
        170,
        y,
        "Category"
    )

    pdf.drawString(
        280,
        y,
        "Quantity"
    )

    pdf.drawString(
        360,
        y,
        "Available"
    )

    pdf.drawString(
        450,
        y,
        "Status"
    )

    y -= 20

    pdf.setFont(
        "Helvetica",
        10
    )

    equipments = Equipment.objects.all()

    for equipment in equipments:

        available = equipment.available_quantity

        pdf.drawString(
            40,
            y,
            equipment.name
        )

        pdf.drawString(
            170,
            y,
            equipment.category
        )

        pdf.drawString(
            280,
            y,
            str(equipment.quantity)
        )

        pdf.drawString(
            360,
            y,
            str(available)
        )

        pdf.drawString(
            450,
            y,
            equipment.status
        )

        y -= 20

        if y < 50:

            pdf.showPage()

            y = 800

            pdf.setFont(
                "Helvetica",
                10
            )

    pdf.save()

    return response


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@login_required
def admin_dashboard(request):

    total_users = User.objects.count()

    total_equipment = Equipment.objects.count()

    pending_requests = Request.objects.filter(
        status="Pending"
    ).count()

    borrowed_requests = Request.objects.filter(
        status="Borrowed"
    ).count()

    recent_requests = Request.objects.select_related(
        "user"
    ).order_by(
        "-id"
    )[:10]

    context = {

        "total_users":
            total_users,

        "total_equipment":
            total_equipment,

        "pending_requests":
            pending_requests,

        "borrowed_equipment":
            borrowed_requests,

        "recent_requests":
            recent_requests,
    }

    return render(
        request,
        "inventory/admin_dashboard.html",
        context
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@login_required
def user_management(request):

    users = User.objects.all().order_by("username")
    roles = Group.objects.all().order_by("name")

    search = request.GET.get("search", "").strip()
    role = request.GET.get("role", "").strip()

    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search)
        )

    if role:
        users = users.filter(groups__name=role)

    context = {
        "users": users.distinct(),
        "roles": roles,
    }

    return render(
        request,
        "inventory/user_management.html",
        context
    )

# ============================================================
# ADD USER
# ============================================================

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

@login_required
def add_user(request):

    if request.method != "POST":
        return redirect("user_management")

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    role_name = request.POST.get("role", "").strip()

    if not username or not email or not password or not role_name:
        messages.error(request, "Please fill in all required fields.")
        return redirect("user_management")

    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Enter a valid email address.")
        return redirect("user_management")

    if User.objects.filter(username=username).exists():
        messages.error(request, "Username already exists.")
        return redirect("user_management")

    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "This email is already registered.")
        return redirect("user_management")

    group = Group.objects.filter(name=role_name).first()

    if group is None:
        messages.error(request, "Please select a valid role.")
        return redirect("user_management")

    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.groups.add(group)

    except Exception:
        messages.error(request, "The user could not be created.")
        return redirect("user_management")

    messages.success(request, f"User '{username}' added successfully.")
    return redirect("user_management")


# ============================================================
# EDIT USER
# ============================================================

@login_required
def edit_user(request, id):

    user = get_object_or_404(
        User,
        id=id
    )

    if request.method == "POST":

        username = request.POST.get(
            "username"
        )

        email = request.POST.get(
            "email"
        )

        role_name = request.POST.get(
            "role"
        )

        user.username = username

        user.email = email

        user.save()

        if role_name:

            group = Group.objects.filter(
                name=role_name
            ).first()

            if group:

                user.groups.clear()

                user.groups.add(
                    group
                )

        messages.success(
            request,
            "User updated successfully."
        )

        return redirect(
            "user_management"
        )

    return redirect(
        "user_management"
    )


# ============================================================
# DELETE USER
# ============================================================

@login_required
def delete_user(request, id):

    user = get_object_or_404(
        User,
        id=id
    )

    if request.method == "POST":

        user.delete()

        messages.success(
            request,
            "User deleted successfully."
        )

    return redirect(
        "user_management"
    )


# ============================================================
# PRINT USERS
# ============================================================

@login_required
def print_users(request):

    users = User.objects.all()

    return render(
        request,
        "inventory/print_users.html",
        {
            "users": users
        }
    )


# ============================================================
# EXPORT USERS PDF
# ============================================================

@login_required
def export_users_pdf(request):

    response = HttpResponse(
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        'attachment; filename="AMN_User_Report.pdf"'
    )

    pdf = canvas.Canvas(
        response
    )

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawString(
        50,
        800,
        "AMN Camera Store - User Report"
    )

    y = 760

    pdf.setFont(
        "Helvetica-Bold",
        11
    )

    pdf.drawString(
        50,
        y,
        "Username"
    )

    pdf.drawString(
        180,
        y,
        "Email"
    )

    pdf.drawString(
        330,
        y,
        "Role"
    )

    pdf.drawString(
        450,
        y,
        "Status"
    )

    y -= 25

    pdf.setFont(
        "Helvetica",
        10
    )

    users = User.objects.all()

    for user in users:

        groups = user.groups.all()

        if groups.exists():

            role = groups.first().name

        else:

            role = "No Role"

        if user.is_active:

            status = "Active"

        else:

            status = "Inactive"

        pdf.drawString(
            50,
            y,
            user.username
        )

        pdf.drawString(
            180,
            y,
            user.email
        )

        pdf.drawString(
            330,
            y,
            role
        )

        pdf.drawString(
            450,
            y,
            status
        )

        y -= 20

        if y < 50:

            pdf.showPage()

            y = 800

            pdf.setFont(
                "Helvetica",
                10
            )

    pdf.save()

    return response


# ============================================================
# ROLE MANAGEMENT
# ============================================================

@login_required
def role_management(request):

    # Only Admin can manage permissions
    if not request.user.groups.filter(name="admin").exists():
        raise PermissionDenied(
            "Only Admin can manage permissions."
        )

    users = User.objects.all().order_by("username")

    selected_user = None
    permission = None
    role_type = None

    # Employee navigation permissions
    employee_fields = [
        ("employee_home", "Dashboard / Home"),
        ("view_available", "View Available Equipment"),
        ("create_request", "Create Request"),
        ("return_borrowed", "Return Borrowed Equipment"),
        ("employee_logout", "Logout"),
    ]

    # Storekeeper navigation permissions
    storekeeper_fields = [
        ("storekeeper_home", "Dashboard / Home"),
        ("manage_equipment", "Manage Equipment"),
        ("manage_requests", "Manage Requests"),
        ("return_equipment", "Return Equipment"),
        ("report", "Reports"),
        ("storekeeper_logout", "Logout"),
    ]

    # Admin navigation permissions
    admin_fields = [
        ("admin_home", "Dashboard / Home"),
        ("user_management", "User Management"),
        ("role_management", "Role Management"),
        ("equipment_management", "Equipment Management"),
        ("request_management", "Request Management"),
        ("reports", "Reports"),
        ("admin_logout", "Logout"),
    ]

    # Get selected user
    user_id = (
        request.POST.get("user_id")
        if request.method == "POST"
        else request.GET.get("user_id")
    )

    if user_id:
        selected_user = get_object_or_404(
            User,
            id=user_id
        )

        permission, created = (
            UserPermission.objects.get_or_create(
                user=selected_user
            )
        )

        # Determine the selected user's role
        if selected_user.groups.filter(
            name="admin"
        ).exists():
            role_type = "admin"
            fields = admin_fields

        elif selected_user.groups.filter(
            name="Store Keeper"
        ).exists():
            role_type = "storekeeper"
            fields = storekeeper_fields

        elif selected_user.groups.filter(
            name="employee"
        ).exists():
            role_type = "employee"
            fields = employee_fields

        else:
            fields = []
            messages.warning(
                request,
                "This user does not belong to a recognized role group."
            )

        # Save selected role permissions
        if request.method == "POST":

            for field, label in fields:
                setattr(
                    permission,
                    field,
                    field in request.POST
                )

            permission.save()

            messages.success(
                request,
                f"Permissions saved for {selected_user.username}."
            )

            return redirect(
                f"{reverse('role_management')}?user_id={selected_user.id}"
            )

    # Prepare checkbox data for the template
    employee_permissions = []
    storekeeper_permissions = []
    admin_permissions = []

    if permission:
        employee_permissions = [
            {
                "field": field,
                "label": label,
                "checked": getattr(permission, field),
            }
            for field, label in employee_fields
        ]

        storekeeper_permissions = [
            {
                "field": field,
                "label": label,
                "checked": getattr(permission, field),
            }
            for field, label in storekeeper_fields
        ]

        admin_permissions = [
            {
                "field": field,
                "label": label,
                "checked": getattr(permission, field),
            }
            for field, label in admin_fields
        ]

    context = {
        "users": users,
        "selected_user": selected_user,
        "permission": permission,
        "role_type": role_type,
        "employee_permissions": employee_permissions,
        "storekeeper_permissions": storekeeper_permissions,
        "admin_permissions": admin_permissions,
    }

    return render(
        request,
        "inventory/role_management.html",
        context
    )


# ============================================================
# MANAGE SINGLE USER ROLE
# ============================================================

@login_required
def manage_user_role(request, id):

    # Only Admin can manage permissions
    if not request.user.groups.filter(name="admin").exists():
        raise PermissionDenied(
            "Only Admin can manage permissions."
        )

    # Use the main role management page
    return redirect(
        f"{reverse('role_management')}?user_id={id}"
    )



# ============================================================
# ADMIN EQUIPMENT MANAGEMENT
# ============================================================

@login_required
def admin_equipment_management(request):

    equipments = Equipment.objects.all().order_by(
        "-id"
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    search = request.GET.get(
        "search"
    )

    if search:

        equipments = (
            equipments.filter(
                name__icontains=search
            )
            |
            equipments.filter(
                model__icontains=search
            )
            |
            equipments.filter(
                serial_number__icontains=search
            )
        )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category = request.GET.get(
        "category"
    )

    if category:

        equipments = equipments.filter(
            category=category
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = request.GET.get(
        "status"
    )

    if status:

        equipments = equipments.filter(
            status=status
        )

    context = {

        "equipments":
            equipments,

       
"total_equipment":
    Equipment.objects.aggregate(
        total=Sum("quantity")
    )["total"] or 0,

"borrowed":
    sum(
        equipment.quantity - equipment.available_quantity
        for equipment in Equipment.objects.all()
    ),

"maintenance":
    Equipment.objects.filter(
        status="Maintenance"
    ).count(),

"low_stock":
    Equipment.objects.filter(
        available_quantity__lt=5
    ).count(),

        "categories":
            Equipment.objects.values_list(
                "category",
                flat=True
            ).distinct(),

        "statuses":
            Equipment.objects.values_list(
                "status",
                flat=True
            ).distinct(),
    }

    return render(
        request,
        "inventory/admin_equipment.html",
        context
    )


# ============================================================
# ADMIN ADD EQUIPMENT
# ============================================================

@login_required
def admin_add_equipment(request):

    if request.method == "POST":

        try:

            quantity = int(
                request.POST.get(
                    "quantity",
                    0
                )
            )

        except (ValueError, TypeError):

            quantity = 0

        if quantity < 1:

            messages.error(
                request,
                "Quantity must be at least 1."
            )

            return redirect(
                "admin_equipment_management"
            )

        Equipment.objects.create(

            name=request.POST.get(
                "name"
            ),

            category=request.POST.get(
                "category"
            ),

            model=request.POST.get(
                "model"
            ),

            serial_number=request.POST.get(
                "serial_number"
            ),

            quantity=quantity,

            available_quantity=quantity,

            status="Available"
        )

        messages.success(
            request,
            "Equipment added successfully."
        )

        return redirect(
            "admin_equipment_management"
        )

    return redirect(
        "admin_equipment_management"
    )


# ============================================================
# ADMIN EDIT EQUIPMENT
# ============================================================

@login_required
def edit_equipment(request, id):

    equipment = get_object_or_404(
        Equipment,
        id=id
    )

    if request.method == "POST":

        equipment.name = request.POST.get(
            "name"
        )

        equipment.category = request.POST.get(
            "category"
        )

        equipment.model = request.POST.get(
            "model"
        )

        equipment.serial_number = request.POST.get(
            "serial_number"
        )

        try:

            new_quantity = int(
                request.POST.get(
                    "quantity",
                    equipment.quantity
                )
            )

        except (ValueError, TypeError):

            new_quantity = equipment.quantity

        # ----------------------------------------------------
        # KEEP BORROWED UNITS
        # ----------------------------------------------------

        borrowed_quantity = (
            equipment.quantity
            - equipment.available_quantity
        )

        if new_quantity < borrowed_quantity:

            messages.error(
                request,
                f"Quantity cannot be less than "
                f"{borrowed_quantity}, because "
                f"{borrowed_quantity} unit(s) are currently borrowed."
            )

            return redirect(
                "admin_equipment_management"
            )

        equipment.quantity = new_quantity

        equipment.available_quantity = (
            new_quantity - borrowed_quantity
        )

        equipment.status = request.POST.get(
            "status",
            equipment.status
        )

        equipment.save()

        messages.success(
            request,
            "Equipment updated successfully."
        )

        return redirect(
            "admin_equipment_management"
        )

    return redirect(
        "admin_equipment_management"
    )


# ============================================================
# ADMIN DELETE EQUIPMENT
# ============================================================

@login_required
def delete_equipment(request, id):

    equipment = get_object_or_404(
        Equipment,
        id=id
    )

    if request.method == "POST":

        equipment.delete()

        messages.success(
            request,
            "Equipment deleted successfully."
        )

    return redirect(
        "admin_equipment_management"
    )


# ============================================================
# ADMIN REQUEST MANAGEMENT
# ============================================================

@login_required
def admin_requests(request):

    requests = Request.objects.all().order_by("-request_date")

    return render(
        request,
        "inventory/admin_requests.html",
        {"requests": requests}
    )

# ============================================================
# ADMIN DELETE REQUEST
# ============================================================

@login_required
def admin_delete_request(request, id):

    # Only Admin can delete requests
    if not request.user.groups.filter(name="admin").exists():
        raise PermissionDenied(
            "Only Admin can delete requests."
        )

    if request.method == "POST":

        req = get_object_or_404(
            Request,
            id=id
        )

        req.delete()

        messages.success(
            request,
            "Request deleted successfully."
        )

    return redirect("admin_requests")

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    search = request.GET.get(
        "search"
    )

    if search:

        requests = requests.filter(
            user__username__icontains=search
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = request.GET.get(
        "status"
    )

    if status:

        requests = requests.filter(
            status=status
        )

    context = {

        "requests":
            requests,

        "statuses":
            Request.objects.values_list(
                "status",
                flat=True
            ).distinct()
    }

    return render(
        request,
        "inventory/admin_requests.html",
        context
    )


# ============================================================
# ADMIN REPORT
# ============================================================

@login_required
def admin_report(request):

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    total_users = User.objects.count()

    # --------------------------------------------------------
    # EQUIPMENT
    # --------------------------------------------------------

    equipments = Equipment.objects.all().order_by(
        "name"
    )

    total_equipment = equipments.count()

    total_equipment_units = equipments.aggregate(
        total=Sum("quantity")
    )["total"] or 0

    available_equipment = equipments.aggregate(
        total=Sum("available_quantity")
    )["total"] or 0

    # --------------------------------------------------------
    # BORROWED / RETURNED
    # --------------------------------------------------------

    borrowed_equipment = (
        RequestItem.objects.filter(
            request__status="Borrowed"
        ).aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    returned_equipment = (
        RequestItem.objects.filter(
            request__status="Returned"
        ).aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    # --------------------------------------------------------
    # REQUESTS
    # --------------------------------------------------------

    pending_requests = Request.objects.filter(
        status="Pending"
    ).count()

    borrowed_requests = Request.objects.filter(
        status="Borrowed"
    ).count()

    returned_requests = Request.objects.filter(
        status="Returned"
    ).count()

    rejected_requests = Request.objects.filter(
        status="Rejected"
    ).count()

    total_requests = Request.objects.count()

    # --------------------------------------------------------
    # AVAILABLE EQUIPMENT
    # --------------------------------------------------------

    available_equipment_items = (
        Equipment.objects.filter(
            available_quantity__gt=0,
            status="Available"
        ).order_by(
            "name"
        )
    )


    # --------------------------------------------------------
    # LOW STOCK
    # --------------------------------------------------------

    low_stock_items = Equipment.objects.filter(
        available_quantity__lt=5
    ).order_by(
        "available_quantity",
        "name"
    )

    # --------------------------------------------------------
    # RECENT REQUESTS
    # --------------------------------------------------------

    recent_requests = (
        Request.objects.select_related(
            "user"
        ).prefetch_related(
            "request_items__equipment"
        ).order_by(
            "-request_date"
        )[:10]
    )
# --------------------------------------------------------
    # EQUIPMENT USAGE REPORT          
    # --------------------------------------------------------

    usage_period = get_usage_period(request)

    usage_report = build_usage_report(
        usage_period["start_date"],
        usage_period["end_date"]
    )

    usage_map = {
        item["id"]: item
        for item in usage_report
    }

    usage_equipments = []

    for equipment in equipments:

        usage_equipments.append({
            "equipment": equipment,
            "times_borrowed": usage_map.get(
                equipment.id, {}
            ).get("times", 0),
        })

    # --------------------------------------------------------
    # GRAPH
    # --------------------------------------------------------

    chart_data = [

        {
            "label": "Users",
            "value": total_users
        },

        {
            "label": "Equipment",
            "value": total_equipment
        },

        {
            "label": "Available",
            "value": available_equipment
        },

        {
            "label": "Borrowed",
            "value": borrowed_equipment
        },

        {
            "label": "Returned",
            "value": returned_equipment
        },

        {
            "label": "Pending",
            "value": pending_requests
        },

        {
            "label": "Rejected",
            "value": rejected_requests
        },
    ]

    context = {

        "total_users":
            total_users,

        "total_equipment":
            total_equipment,

        "total_equipment_units":
            total_equipment_units,

        "available_equipment":
            available_equipment,

        "borrowed_equipment":
            borrowed_equipment,

        "returned_equipment":
            returned_equipment,

        "total_requests":
            total_requests,

        "pending_requests":
            pending_requests,

        "borrowed_requests":
            borrowed_requests,

        "returned_requests":
            returned_requests,

        "rejected_requests":
            rejected_requests,

        "equipments":
            equipments,

        "available_equipment_items":
            available_equipment_items,

        "low_stock_items":
            low_stock_items,

        "recent_requests":
            recent_requests,

       "chart_data": chart_data,
             # ---------------- USAGE REPORT ----------------   <-- NEW STARTS HERE

        "usage_equipments":
            usage_equipments,

        "usage_report":
            usage_report,

        "usage_label":
            get_usage_label(usage_period),

        "usage_period":
            usage_period["period"],

        "usage_start_date":
            usage_period["start_date"],

        "usage_end_date":
            usage_period["end_date"],

        "usage_date":
            usage_period["date_value"],

        "usage_week":
            usage_period["week_value"],

        "usage_month":
            usage_period["month_value"],
    }

    return render(
        request,
        "inventory/admin_report.html",
        context
    )

# ============================================================
# EQUIPMENT USAGE DETAILS
# ============================================================

@login_required
def equipment_usage_detail(request, equipment_id):

    equipment = get_object_or_404(
        Equipment,
        id=equipment_id
    )

    usage_period = get_usage_period(request)

    usage_items = RequestItem.objects.filter(
        equipment=equipment,
        request__status__in=["Borrowed", "Returned"],
        request__request_date__date__range=(
            usage_period["start_date"],
            usage_period["end_date"]
        )
    )

    # SUMMARY STATISTICS

    different_employees = usage_items.values(
        "request__user_id"
    ).distinct().count()

    borrowing_transactions = usage_items.values(
        "request_id"
    ).distinct().count()

    total_borrowed_units = usage_items.aggregate(
        total=Sum("quantity")
    )["total"] or 0

    # DEPARTMENT USAGE

    department_results = usage_items.values(
        "request__department"
    ).annotate(
        times_borrowed=Count(
            "request_id",
            distinct=True
        ),

        employee_count=Count(
            "request__user_id",
            distinct=True
        )

    ).order_by("request__department")

    department_usage = []

    for item in department_results:

        department_name = (
            item["request__department"] or "Not specified"
        )

        department_key = (
            item["request__department"] or "__empty__"
        )

        department_usage.append({
            "department": department_name,
            "department_key": department_key,
            "times_borrowed": item["times_borrowed"],
            "employee_count": item["employee_count"],
        })

    context = {

        "equipment": equipment,

        "different_employees": different_employees,
        "borrowing_transactions": borrowing_transactions,
        "total_borrowed_units": total_borrowed_units,

        "department_usage": department_usage,

        "usage_period": usage_period["period"],
        "usage_start_date": usage_period["start_date"],
        "usage_end_date": usage_period["end_date"],

        "usage_month": usage_period["month_value"],
        "usage_week": usage_period["week_value"],
        "usage_date": usage_period["date_value"],
    }

    return render(
        request,
        "inventory/equipment_usage_detail.html",
        context
    )


# ============================================================
# DEPARTMENT EMPLOYEE USAGE DETAILS
# ============================================================

@login_required
def department_employee_detail(request, equipment_id):

    equipment = get_object_or_404(
        Equipment,
        id=equipment_id
    )

    department_key = request.GET.get(
        "department",
        ""
    )

    usage_period = get_usage_period(request)

    usage_items = RequestItem.objects.filter(
        equipment=equipment,
        request__status__in=["Borrowed", "Returned"],
        request__request_date__date__range=(
            usage_period["start_date"],
            usage_period["end_date"]
        )
    )

    # SELECT DEPARTMENT

    if department_key == "__empty__":

        usage_items = usage_items.filter(
            Q(request__department__isnull=True) |
            Q(request__department="")
        )

        department_name = "Not specified"

    else:

        usage_items = usage_items.filter(
            request__department=department_key
        )

        department_name = department_key

    # EMPLOYEE USAGE

    employee_results = usage_items.values(
        "request__employee_id",
        "request__user__username",
        "request__department"
    ).annotate(
        times_borrowed=Count(
            "request_id",
            distinct=True
        ),

        total_units=Sum("quantity")

    ).order_by(
        "request__employee_id",
        "request__user__username"
    )

    employee_usage = []

    for item in employee_results:

        employee_id = (
            item["request__employee_id"] or
            item["request__user__username"]
        )

        employee_usage.append({
            "employee_id": employee_id,
            "username": item["request__user__username"],
            "department": item["request__department"] or "Not specified",
            "times_borrowed": item["times_borrowed"],
            "total_units": item["total_units"] or 0,
        })

    context = {

        "equipment": equipment,

        "department_name": department_name,

        "employee_usage": employee_usage,

        "employee_count": len(employee_usage),

        "usage_period": usage_period["period"],
        "usage_start_date": usage_period["start_date"],
        "usage_end_date": usage_period["end_date"],

        "usage_month": usage_period["month_value"],
        "usage_week": usage_period["week_value"],
        "usage_date": usage_period["date_value"],
    }

    return render(
        request,
        "inventory/department_employee_detail.html",
        context
    )
# ============================================================
# ADMIN REPORT PDF
# ============================================================

@login_required
def admin_report_pdf(request):

    response = HttpResponse(
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        'attachment; filename="Admin_Report.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4)
    )

    elements = []

    styles = getSampleStyleSheet()

    elements.append(
        Paragraph(
            "<b>AMN Camera Store — Admin Report</b>",
            styles["Title"]
        )
    )

    equipments = Equipment.objects.all().order_by(
        "name"
    )

    summary = [

        ["Metric", "Value"],

        [
            "Total Users",
            User.objects.count()
        ],

        [
            "Total Equipment",
            equipments.count()
        ],

        [
            "Total Equipment Units",
            equipments.aggregate(
                total=Sum("quantity")
            )["total"] or 0
        ],

        [
            "Available Equipment",
            equipments.aggregate(
                total=Sum("available_quantity")
            )["total"] or 0
        ],

        [
            "Borrowed Equipment",
            RequestItem.objects.filter(
                request__status="Borrowed"
            ).aggregate(
                total=Sum("quantity")
            )["total"] or 0
        ],

        [
            "Returned Equipment",
            RequestItem.objects.filter(
                request__status="Returned"
            ).aggregate(
                total=Sum("quantity")
            )["total"] or 0
        ],

        [
            "Total Requests",
            Request.objects.count()
        ],

        [
            "Pending Requests",
            Request.objects.filter(
                status="Pending"
            ).count()
        ],

        [
            "Borrowed Requests",
            Request.objects.filter(
                status="Borrowed"
            ).count()
        ],

        [
            "Returned Requests",
            Request.objects.filter(
                status="Returned"
            ).count()
        ],

        [
            "Rejected Requests",
            Request.objects.filter(
                status="Rejected"
            ).count()
        ],
    ]

    summary_table = Table(
        summary,
        colWidths=[180, 120]
    )

    summary_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#071322")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#eef2f7")
                ]
            ),
        ])
    )

    elements.append(
        summary_table
    )

    elements.append(
        Paragraph(
            "Equipment Inventory",
            styles["Heading2"]
        )
    )

    rows = [[
        "Name",
        "Category",
        "Model",
        "Serial",
        "Qty",
        "Available",
        "Status"
    ]]

    for equipment in equipments:

        rows.append([

            equipment.name,

            equipment.category,

            equipment.model,

            equipment.serial_number,

            equipment.quantity,

            equipment.available_quantity,

            equipment.status
        ])

    equip_table = Table(
        rows,
        repeatRows=1
    )

    equip_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#071322")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9
            ),
        ])
    )

    elements.append(
        equip_table
    )

    doc.build(
        elements
    )

    return response


# ============================================================
# EQUIPMENT DETAIL
# ============================================================

@login_required
def equipment_detail(request, id):

    equipment = get_object_or_404(
        Equipment,
        id=id
    )

    return render(
        request,
        "inventory/equipment_detail.html",
        {
            "equipment": equipment
        }
    )
# ============================================================
# EQUIPMENT USAGE PERIOD FILTER
# ============================================================
def get_usage_period(request):

    today = timezone.localdate()

    period = request.GET.get("period", "monthly")

    if period not in ["daily", "weekly", "monthly"]:
        period = "monthly"

    date_value = request.GET.get("date", today.isoformat())
    week_value = request.GET.get("week", "")
    month_value = request.GET.get("month", today.strftime("%Y-%m"))

    # ===============================
    # DAILY FILTER
    # ===============================

    if period == "daily":

        try:
            selected_date = date.fromisoformat(date_value)
        except (ValueError, TypeError):
            selected_date = today

        start_date = selected_date
        end_date = selected_date
        date_value = selected_date.isoformat()

    # ===============================
    # WEEKLY FILTER
    # Week 1 = day 1 to 7
    # Week 2 = day 8 to 14
    # Week 3 = day 15 to 21
    # Week 4 = day 22 to end of month
    # ===============================

    elif period == "weekly":

        try:
            selected_month = date.fromisoformat(month_value + "-01")
        except (ValueError, TypeError):
            selected_month = today.replace(day=1)

        last_day = calendar.monthrange(
            selected_month.year,
            selected_month.month
        )[1]

        try:
            week_number = int(week_value)
        except (ValueError, TypeError):
            week_number = 0

        if week_number not in (1, 2, 3, 4):

            if (
                selected_month.year == today.year
                and selected_month.month == today.month
            ):
                week_number = min(4, (today.day - 1) // 7 + 1)
            else:
                week_number = 1

        start_day = (week_number - 1) * 7 + 1

        if week_number == 4:
            end_day = last_day
        else:
            end_day = start_day + 6

        start_date = selected_month.replace(day=start_day)
        end_date = selected_month.replace(day=end_day)

        week_value = str(week_number)
        month_value = selected_month.strftime("%Y-%m")

    # ===============================
    # MONTHLY FILTER
    # ===============================

    else:

        try:
            selected_month = date.fromisoformat(month_value + "-01")
        except (ValueError, TypeError):
            selected_month = today.replace(day=1)

        start_date = selected_month.replace(day=1)

        last_day = calendar.monthrange(
            start_date.year,
            start_date.month
        )[1]

        end_date = start_date.replace(day=last_day)
        month_value = start_date.strftime("%Y-%m")

    # ===============================
    # RETURN FILTER RESULTS
    # ===============================

    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "date_value": date_value,
        "week_value": week_value,
        "month_value": month_value,
    }
# ============================================================
# EQUIPMENT USAGE REPORT HELPERS
# ============================================================

USAGE_STATUSES = ["Borrowed", "Returned"]


def get_usage_label(usage_period):

    if usage_period["period"] == "daily":
        return "Daily"

    if usage_period["period"] == "weekly":
        return "Weekly - Week " + str(usage_period["week_value"])

    return "Monthly"


def build_usage_report(start_date, end_date):

    rows = RequestItem.objects.filter(
        request__status__in=USAGE_STATUSES,
        request__request_date__date__range=(
            start_date,
            end_date
        )
    ).values(
        "equipment_id",
        "equipment__name",
        "request__department",
        "request__employee_id",
        "request__user__username"
    ).annotate(
        times=Count("request_id", distinct=True),
        units=Sum("quantity")
    ).order_by(
        "equipment__name",
        "request__department",
        "request__employee_id"
    )

    report = {}

    for r in rows:

        equipment_data = report.setdefault(
            r["equipment_id"],
            {
                "id": r["equipment_id"],
                "name": r["equipment__name"],
                "times": 0,
                "units": 0,
                "employees": 0,
                "rows": [],
            }
        )

        units = r["units"] or 0

        equipment_data["times"] += r["times"]
        equipment_data["units"] += units
        equipment_data["employees"] += 1

        equipment_data["rows"].append({
            "department": r["request__department"] or "Not specified",
            "employee_id": (
                r["request__employee_id"]
                or r["request__user__username"]
            ),
            "times": r["times"],
            "units": units,
        })
    return list(report.values())
