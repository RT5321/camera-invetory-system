from django.urls import path
from . import views


urlpatterns = [

    # -----------------------------
    # HOME
    # -----------------------------
    path(
        '',
        views.home,
        name='home'
    ),


    # -----------------------------
    # AUTHENTICATION
    # -----------------------------
    path(
        'login/',
        views.login_view,
        name='login'
    ),

    path(
        'register/',
        views.register,
        name='register'
    ),

    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),



    # -----------------------------
    # ADMIN DASHBOARD
    # -----------------------------
    path(
        'admin-dashboard/',
        views.admin_dashboard,
        name='admin_dashboard'
    ),



    # -----------------------------
    # EMPLOYEE DASHBOARD
    # -----------------------------
    path(
        'dashboard/',
        views.user_dashboard,
        name='user_dashboard'
    ),



    # -----------------------------
    # STOREKEEPER DASHBOARD
    # -----------------------------
    path(
        'storekeeper-dashboard/',
        views.storekeeper_dashboard,
        name='storekeeper_dashboard'
    ),



    # -----------------------------
    # AVAILABLE EQUIPMENT
    # -----------------------------
    path(
        'view-available/',
        views.view_available,
        name='view_available'
    ),



    # -----------------------------
    # CREATE REQUEST
    # -----------------------------
    path(
        'create-request/',
        views.create_request,
        name='create_request'
    ),



    # -----------------------------
    # REQUEST MANAGEMENT
    # -----------------------------
    path(
        'manage-requests/',
        views.manage_requests,
        name='manage_requests'
    ),


    path(
        'approve-request/<int:id>/',
        views.approve_request,
        name='approve_request'
    ),


    path(
        'reject-request/<int:id>/',
        views.reject_request,
        name='reject_request'
    ),



    # -----------------------------
    # STOREKEEPER EQUIPMENT
    # -----------------------------
    path(
        'manage-equipment/',
        views.manage_equipment,
        name='manage_equipment'
    ),


    path(
        'add-equipment/',
        views.add_equipment,
        name='add_equipment'
    ),


    path(
        'update-equipment-status/<int:id>/',
        views.update_equipment_status,
        name='update_equipment_status'
    ),



    # -----------------------------
    # CHECKOUT
    # -----------------------------
    path(
        'process-checkout/<int:id>/',
        views.process_checkout,
        name='process_checkout'
    ),



    # -----------------------------
    # EMPLOYEE RETURN
    # -----------------------------
    path(
        'return-borrowed/',
        views.return_borrowed,
        name='return_borrowed'
    ),


    path(
        'process-return/<int:id>/',
        views.process_return,
        name='process_return'
    ),



    # -----------------------------
    # STOREKEEPER RETURN
    # -----------------------------
    path(
        'storekeeper-return/',
        views.storekeeper_return,
        name='storekeeper_return'
    ),


    path(
        'confirm-return/<int:id>/',
        views.confirm_return,
        name='confirm_return'
    ),



    # -----------------------------
    # REQUEST DETAIL
    # -----------------------------
    path(
        'request-detail/<int:id>/',
        views.request_detail,
        name='request_detail'
    ),



    # -----------------------------
    # REPORT
    # -----------------------------
    path(
        'report/',
        views.report,
        name='report'
    ),

path(
    'report/pdf/',
    views.report_pdf,
    name='report_pdf'
),

    # -----------------------------
    # ADMIN USER MANAGEMENT
    # -----------------------------
    path(
        'user-management/',
        views.user_management,
        name='user_management'
    ),


    path(
        'add-user/',
        views.add_user,
        name='add_user'
    ),


    path(
        'edit-user/<int:id>/',
        views.edit_user,
        name='edit_user'
    ),


    path(
        'delete-user/<int:id>/',
        views.delete_user,
        name='delete_user'
    ),


    path(
        'print-users/',
        views.print_users,
        name='print_users'
    ),


    path(
        'export-users-pdf/',
        views.export_users_pdf,
        name='export_users_pdf'
    ),



    # -----------------------------
    # ROLE MANAGEMENT
    # -----------------------------
    path(
        'role-management/',
        views.role_management,
        name='role_management'
    ),


    path(
        'manage-user-role/<int:id>/',
        views.manage_user_role,
        name='manage_user_role'
    ),



    # -----------------------------
    # ADMIN EQUIPMENT MANAGEMENT
    # -----------------------------
    path(
        'admin-equipment/',
        views.admin_equipment_management,
        name='admin_equipment_management'
    ),


    path(
        'admin-equipment/add/',
        views.admin_add_equipment,
        name='admin_add_equipment'
    ),


    path(
        'admin-equipment/edit/<int:id>/',
        views.edit_equipment,
        name='edit_equipment'
    ),


    path(
        'admin-equipment/delete/<int:id>/',
        views.delete_equipment,
        name='delete_equipment'
    ),


    # -----------------------------
    # EQUIPMENT DETAIL
    # -----------------------------
    path(
        'equipment-detail/<int:id>/',
        views.equipment_detail,
        name='equipment_detail'
    ),



    # -----------------------------
    # ADMIN REQUEST MANAGEMENT
    # -----------------------------
    path(
        'admin-requests/',
        views.admin_requests,
        name='admin_requests'
    ),



    # -----------------------------
    # ADMIN REPORT
    # -----------------------------
    path(
        'admin-report/',
        views.admin_report,
        name='admin_report'
    ),

path(
    'admin-report/pdf/',
    views.admin_report_pdf,
    name='admin_report_pdf'
),

path(
    "equipment-usage/<int:equipment_id>/",
    views.equipment_usage_detail,
    name="equipment_usage_detail"
),

path(
    "admin-delete-request/<int:id>/",
    views.admin_delete_request,
    name="admin_delete_request"
),
path(
    "equipment-usage/<int:equipment_id>/employees/",
    views.department_employee_detail,
    name="department_employee_detail"
),
]
