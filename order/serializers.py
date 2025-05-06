from django.utils import timezone
import pytz
from rest_framework import serializers
from SuperAdmin.models import SuperAdmin
from .models import Order
from BusinessPartner.models import BusinessPartner
from user.models import ResUser, BusinessPartner  
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from datetime import date


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer class for the Order model.
    """
    bp_code = serializers.SlugRelatedField(
        queryset=BusinessPartner.objects.all(),
        slug_field='bp_code',
        required=False,
        allow_null=True
    )
    order_date = serializers.SerializerMethodField() 
       
    def get_order_date(self, obj):
        ist = pytz.timezone('Asia/Kolkata')
        return obj.order_date.astimezone(ist).strftime('%d-%m-%Y %H:%M:%S IST')
    class Meta:
        model = Order
        fields = [
            'order_image', 'order_no', 'bp_code', 'name', 'reference_no', 'order_date', 'due_date', 'segment', 'category', 'order_type',
            'quantity', 'weight', 'dtype', 'branch_code', 'product', 'design', 'vendor_design', 'barcoded_quality',
            'supplied', 'balance', 'assigned_by', 'narration', 'note', 'sub_brand', 'make', 'work_style', 'form',
            'finish', 'theme', 'collection', 'description', 'assign_remarks', 'screw', 'polish', 'metal_colour',
            'purity', 'stone', 'hallmark', 'rodium', 'enamel', 'hook', 'size', 'open_close', 'length', 'hbt_class',
            'console_id', 'tolerance_from', 'tolerance_to'
        ]
        read_only_fields = ['order_no', 'order_date'] 

    def create(self, validated_data):
        if 'bp_code' not in validated_data:
            raise serializers.ValidationError({"bp_code": "This field is required."})
        return super().create(validated_data)

    def to_representation(self, instance):
        """Modify the output representation to include business_name with bp_code."""
        data = super().to_representation(instance)
        if instance.bp_code:
            data['bp_code'] = f"{instance.bp_code.bp_code}-{instance.bp_code.business_name}"
        return data
    
    def validate(self, data):
        if 'order_date' in data:
            raise serializers.ValidationError("Order date is auto-set to today's date")
        return data
    
    def validate_due_date(self, value):
        """
        Validate that due_date is at least tomorrow (future date only).
        """
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        if value <= today:
            raise serializers.ValidationError("Due date must be tomorrow or later. Cannot be today or in the past.")
        return value
    
    def create(self, validated_data):
        if 'bp_code' not in validated_data:
            raise serializers.ValidationError({"bp_code": "This field is required."})
        last_order = Order.objects.all().order_by('id').last()
        
        if not last_order:
            new_order_no = '001'
        else:
            try:
                last_number = int(last_order.order_no)
                new_number = last_number + 1
                new_order_no = f"{new_number:03d}"
            except (ValueError, AttributeError):
                new_order_no = f"{Order.objects.count() + 1:002d}"
        
        validated_data['order_no'] = new_order_no
        return super().create(validated_data)
    
class KeyUserApprovalSerializer(serializers.ModelSerializer):
    approval_notes = serializers.ChoiceField(
        choices=['Approved by Key User', 'Rejected by Key User'],
        write_only=True)
    order_no = serializers.CharField(write_only=True)

    class Meta:
        model = Order
        fields = ['order_no', 'approval_notes']

    def validate(self, attrs):
        order_no = attrs.get('order_no')
        try:
            order = Order.objects.get(order_no=order_no)
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_no": "Order not found."})

        if order.status != 'pending':
            raise serializers.ValidationError({"status": "Only pending orders can be approved."})

        attrs['order'] = order
        return attrs

    def save(self, **kwargs):
        order = self.validated_data['order']
        approval_note = self.validated_data.get('approval_notes', '')

        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            raise serializers.ValidationError({"user": "Authentication required."})

        order.key_user_approval_notes = approval_note
        order.approved_by_key_user = request.user

        if approval_note == 'Approved by Key User':
            order.status = 'in-process'
            message = f"Order {order.order_no} approved by Key User."
        else:
            order.status = 'reject'
            message = f"Order {order.order_no} rejected by Key User."

        order.save()
        return {
            "order": order,
            "message": message,
            "status": order.status
        }


class AdminApprovalSerializer(serializers.ModelSerializer):
    approval_notes = serializers.ChoiceField(choices=['Accepted by Admin', 'Rejected by Admin'], write_only=True)
    order_no = serializers.CharField(write_only=True)

    class Meta:
        model = Order
        fields = ['order_no', 'approval_notes']

    def validate(self, attrs):
        try:
            order = Order.objects.get(order_no=attrs['order_no'])
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_no": "Order not found."})

        if order.status != 'in-process':
            raise serializers.ValidationError({"status": "Only in-process orders can be reviewed by Admin."})

        attrs['order'] = order
        return attrs

    def save(self, **kwargs):
        order = self.validated_data['order']
        approval_note = self.validated_data['approval_notes']

        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            raise serializers.ValidationError({"user": "Authentication required."})

        order.admin_approval_notes = approval_note
        order.approved_by_admin = request.user

        if approval_note == 'Accepted by Admin':
            order.status = 'in-process'
            message = f"Order {order.order_no} accepted by Admin."
        else:
            order.status = 'reject'
            message = f"Order {order.order_no} rejected by Admin."

        order.save()
        return {
            "order": order,
            "message": message
        }
    
class CraftsmanSerializer(serializers.ModelSerializer):
    """Serializer for listing available craftsmen."""
    bp_code = serializers.SerializerMethodField()
    class Meta:
        model = BusinessPartner
        fields = ['full_name', 'bp_code']
    
    def get_bp_code(self, obj):
        if hasattr(obj, 'business_name'):
            return f"{obj.bp_code}-{obj.business_name}"
        return str(obj.bp_code)

# class OrderActionSerializer(serializers.Serializer):
#     order_no = serializers.CharField()
#     action = serializers.ChoiceField(choices=["Accepted by Craftsman", "Rejected by Craftsman"])

#     def validate(self, data):
#         try:
#             order = Order.objects.get(order_no=data['order_no'])
#         except Order.DoesNotExist:
#             raise serializers.ValidationError({"order_no": "Order not found."})

#         if order.status != "assigned":
#             raise serializers.ValidationError({"status": "Only assigned orders can be acted upon."})

#         data['order'] = order
#         return data

#     def save(self, **kwargs):
#         order = self.validated_data['order']
#         action = self.validated_data['action']

#         if action == 'Accepted by Craftsman':
#             order.status = 'in-process'
#             order.save()
#             return {
#                 "status": "success",
#                 "order": order,
#                 "message": f"Order {order.order_no} accepted and is now in-process",
#                 "craftsman": order.craftsman
#             }

#         elif action == 'Rejected by Craftsman':
#             previous_craftsman = order.craftsman
#             order.status = 'rejected'
#             order.rejected_by = previous_craftsman
#             order.craftsman = None
#             order.save()

#             return {
#                 "status": "rejected",
#                 "order": order,
#                 "previous_craftsman": previous_craftsman
#             }


class OrderActionSerializer(serializers.Serializer):
    order_no = serializers.CharField()
    action = serializers.ChoiceField(choices=["Accepted by Craftsman", "Rejected by Craftsman"])
    rejection_reason = serializers.ChoiceField(
        choices=[
            ('material_unavailable', 'Material Unavailable'),
            ('low_quality_material', 'Material Quality Too Low'),
            ('supplier_delays', 'Supplier Delays'),
            ('material_cost_increase', 'Material Cost Increased Unacceptably'),
            
            # Design/Technical Issues
            ('design_complexity', 'Design Too Complex'),
            ('design_errors', 'Design Has Errors/Flaws'),
            ('technical_infeasible', 'Technically Not Feasible'),
            ('3d_model_problems', '3D Model Cannot Be Executed'),
            ('size_constraints', 'Size/Proportions Not Workable'),
            
            # Time/Logistics
            ('time_constraints', 'Cannot Meet Deadline'),
            ('overbooked', 'Overbooked (No Capacity)'),
            ('shipping_restrictions', 'Shipping/Delivery Not Possible'),
            
            # Quality/Standards
            ('quality_concerns', 'Quality Standards Cannot Be Met'),
            ('finishing_issues', 'Cannot Achieve Desired Finish'),
            ('durability_risk', 'Durability Compromised'),
            
            # Customer-Related
            ('customer_changes', 'Customer Changed Requirements'),
            ('customer_unreachable', 'Customer Unreachable'),
            ('customer_cancellation', 'Customer Canceled Mid-Process'),
            ('customer_dispute', 'Customer Dispute (Legal/Contract)'),
            
            # Financial
            ('pricing_issues', 'Pricing Dispute'),
            ('payment_issues', 'Payment Not Secured'),
            ('budget_mismatch', 'Budget Too Low for Requirements'),
            
            # Administrative
            ('incomplete_specs', 'Incomplete Specifications'),
            ('documentation_missing', 'Legal/Mandatory Docs Missing'),
            ('policy_violation', 'Violates Shop Policies'),
            
            # Miscellaneous
            ('force_majeure', 'Force Majeure (Natural Disaster, etc.)'),
            ('other', 'Other Reason (Specify in Notes)'),
        ],
        required=False,
        allow_blank=True
    )
    rejection_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        try:
            order = Order.objects.get(order_no=data['order_no'])
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_no": "Order not found."})

        if order.status != "assigned":
            raise serializers.ValidationError({"status": "Only assigned orders can be acted upon."})

        if data['action'] == "Rejected by Craftsman":
            if not data.get("rejection_reason"):
                raise serializers.ValidationError({"rejection_reason": "This field is required when rejecting an order."})
            if data.get('rejection_reason') == 'other' and not data.get('rejection_notes'):
                raise serializers.ValidationError({"rejection_notes": "Notes are required for 'Other Reason'."})

        data['order'] = order
        return data

    def save(self, **kwargs):
        order = self.validated_data['order']
        action = self.validated_data['action']

        if action == 'Accepted by Craftsman':
            order.status = 'in-process'
            order.save()
            return {
                "status": "success",
                "order": order,
                "message": f"Order {order.order_no} accepted and is now in-process",
                "craftsman": order.craftsman
            }

        elif action == 'Rejected by Craftsman':
            previous_craftsman = order.craftsman
            rejection_reason = self.validated_data.get('rejection_reason')
            rejection_notes = self.validated_data.get('rejection_notes')

            order.status = 'rejected'
            order.rejected_by = previous_craftsman
            order.craftsman = None
            order.rejection_reason = rejection_reason
            order.rejection_notes = rejection_notes if rejection_reason == 'other' else None
            order.save()

            return {
                "status": "rejected",
                "order": order,
                "previous_craftsman": previous_craftsman,
                "rejection_reason": dict(self.fields['rejection_reason'].choices).get(rejection_reason),
                "rejection_notes": rejection_notes if rejection_reason == 'other' else None
            }

class OrderCraftsmanSerializer(serializers.ModelSerializer):
    craftsman = CraftsmanSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['order_no', 'status', 'due_date', 'craftsman']

        
        
class OrderCraftsman(serializers.ModelSerializer):
    craftsman_full_name = serializers.CharField(source='craftsman.full_name', read_only=True)
    craftsman_bp_code = serializers.CharField(source='craftsman.bp_code', read_only=True)

    class Meta:
        model = Order
        fields = ['order_no', 'status', 'created_at', 'craftsman_full_name', 'craftsman_bp_code']
        


class ApprovalSerializer(serializers.Serializer):
    order_no = serializers.CharField()

    def validate(self, attrs):
        order_no = attrs.get('order_no')
        try:
            order = Order.objects.get(order_no=order_no)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found")
        
        if order.status != "in-process":
            raise serializers.ValidationError("Order is not in-process")
        
        attrs['order'] = order
        return attrs

    def save(self):
        order = self.validated_data['order']
        order.status = "awaiting-approval"
        order.save()
        
        return {
            "order": order,
            "message": f"Order {order.order_no} marked as completed by craftsman, waiting for approval"
        }

    
    
class OrderAssignmentSerializer(serializers.Serializer):
    order_no = serializers.IntegerField()
    bp_code = serializers.CharField()
    due_date = serializers.DateField(required=False)

    def validate(self, data):
        # Validate craftsman
        try:
            code_part, business_name_part = data['bp_code'].split("-", 1)
        except ValueError:
            raise serializers.ValidationError({"bp_code": "Invalid format. Expected format 'BP-CODE-NAME'."})

        try:
            craftsman = BusinessPartner.objects.get(
                bp_code=code_part.strip(),
                business_name__iexact=business_name_part.strip(),
                role="CRAFTSMAN"
            )
        except BusinessPartner.DoesNotExist:
            raise serializers.ValidationError({"bp_code": "Craftsman not found."})

        # Validate order
        try:
            order = Order.objects.get(id=data['order_no'], status='in-process')
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_no": "Order not found or not in 'in-process' status."})

        data['order'] = order
        data['craftsman'] = craftsman
        return data
    
    def validate_bp_code(self, value):
        try:
            code_part, business_name_part = value.split("-", 1)
            if not BusinessPartner.objects.filter(
                bp_code=code_part,
                business_name__iexact=business_name_part.strip(),
                role="CRAFTSMAN"
            ).exists():
                raise serializers.ValidationError("No CRAFTSMAN found with this BP Code and Business Name.")
            
            return value
        
        except ValueError:
            raise serializers.ValidationError("BP Code must be in format 'CODE-Business Name'.")

    def validate_order_no(self, value):
        if not Order.objects.filter(id=value).exists():
            raise serializers.ValidationError("Order does not exist.")
        return value

    def save(self, **kwargs):
        order = self.validated_data['order']
        craftsman = self.validated_data['craftsman']
        due_date = self.validated_data.get('due_date')

        order.craftsman = craftsman
        order.status = 'assigned'
        if due_date:
            order.due_date = due_date

        order.save()
        return order
    
class OrderCompletionSerializer(serializers.Serializer):
    order_no = serializers.CharField()

    def validate(self, attrs):
        order_no = attrs.get('order_no')
        try:
            order = Order.objects.get(order_no=order_no)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found")
        
        if order.status != "awaiting-approval":
            raise serializers.ValidationError("Order is not awaiting approval")
        
        attrs['order'] = order
        return attrs

    def save(self):
        order = self.validated_data['order']
        order.status = "complete"
        order.save()
        
        return {
            "order": order,
            "message": f"Order {order.order_no} approved and marked as complete"
        }
    
class OrderReassignSerializer(serializers.Serializer):
    order_no = serializers.IntegerField()
    bp_code = serializers.CharField()
    due_date = serializers.DateField(required=False)

    def validate(self, data):
        # Validate craftsman
        try:
            code_part, business_name_part = data['bp_code'].split("-", 1)
        except ValueError:
            raise serializers.ValidationError({"bp_code": "Invalid format. Expected format 'BP-CODE-NAME'."})

        try:
            craftsman = BusinessPartner.objects.get(
                bp_code=code_part.strip(),
                business_name__iexact=business_name_part.strip(),
                role="CRAFTSMAN"
            )
        except BusinessPartner.DoesNotExist:
            raise serializers.ValidationError({"bp_code": "Craftsman not found."})

        # Validate order
        try:
            order = Order.objects.get(id=data['order_no'], status='rejected')
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order_no": "Order not found or not in 'in-process' status."})

        data['order'] = order
        data['craftsman'] = craftsman
        return data
    
    def validate_bp_code(self, value):
        try:
            code_part, business_name_part = value.split("-", 1)
            if not BusinessPartner.objects.filter(
                bp_code=code_part,
                business_name__iexact=business_name_part.strip(),
                role="CRAFTSMAN"
            ).exists():
                raise serializers.ValidationError("No CRAFTSMAN found with this BP Code and Business Name.")
            
            return value
        
        except ValueError:
            raise serializers.ValidationError("BP Code must be in format 'CODE-Business Name'.")

    def validate_order_no(self, value):
        if not Order.objects.filter(id=value).exists():
            raise serializers.ValidationError("Order does not exist.")
        return value

    def save(self, **kwargs):
        order = self.validated_data['order']
        craftsman = self.validated_data['craftsman']
        due_date = self.validated_data.get('due_date')

        order.craftsman = craftsman
        order.status = 'assigned'
        if due_date:
            order.due_date = due_date

        order.save()
        return {
            "order": order,
            "order_no": self.validated_data['order_no']
        }


    
@receiver(post_save, sender=ResUser)
def assign_bp_code_to_orders(sender, instance, created, **kwargs):
    """Assign user's bp_code to their orders when a new user is created."""
    if created and instance.bp_code:
        Order.objects.filter(user=instance).update(bp_code=instance.bp_code)
        
        
@receiver(post_save, sender=Order)
def set_order_date(sender, instance, created, **kwargs):
    if created and not instance.order_date:
        instance.order_date = date.today()
        instance.save()
        