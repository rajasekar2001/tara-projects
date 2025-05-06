from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.generics import CreateAPIView, GenericAPIView
from .models import Order
from BusinessPartner.models import BusinessPartner
from .serializers import OrderSerializer, KeyUserApprovalSerializer, AdminApprovalSerializer, OrderReassignSerializer, ApprovalSerializer, OrderCompletionSerializer, CraftsmanSerializer, OrderCraftsmanSerializer, OrderAssignmentSerializer, OrderActionSerializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


# Helper function to check if user role is valid
def is_valid_user_role(user): 
    """
    Check if the user's role is one of the allowed roles:
    'admin', 'staff', 'seller', 'customer'.
    """
    valid_roles = ['Super Admin', 'Admin', 'Key User', 'User']
    return user.role_name in valid_roles
    

class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Get all Orders or filter by `bp_code`.
        Shows pending orders for regular users, shows all for staff/admin users.
        """
        bp_code = request.query_params.get("bp_code")
        queryset = self.get_queryset()
        
        if bp_code:
            queryset = queryset.filter(bp_code=bp_code)
        if not request.user.is_staff:
            queryset = queryset.filter(created_by=request.user, status='pending')
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        """
        User submits an order (status = 'pending').
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.validated_data['status'] = 'pending'
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class KeyUserApprovalView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = KeyUserApprovalSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            "order_no": result['order'].order_no,
            "status": result['status'],
            "message": result['message']
        }, status=status.HTTP_200_OK)
       
        
    def delete(self, request, order_no, *args, **kwargs):
        """
        Key User rejects an order – delete the pending order
        """
        order = get_object_or_404(Order, id=order_no)

        if order.status != 'pending':
            return Response(
                {"error": "Only pending orders can be rejected by Key User."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rejection_notes = request.data.get('rejection_notes', '')
        order.delete()

        return Response({
            "message": "Order rejected by Key User and deleted.",
            "order_no": order_no,
            # "rejected_by": request.user.username,
            "rejection_notes": rejection_notes
        }, status=status.HTTP_200_OK)
        

class AdminVerificationView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = AdminApprovalSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            "order_no": result["order"].order_no,
            "status": result["order"].status,
            "message": result["message"]
        }, status=status.HTTP_200_OK)

 

    def delete(self, request, order_no, *args, **kwargs):
        """
        Admin rejects an order – set status to 'admin-rejected'
        """
        order = get_object_or_404(Order, id=order_no)

        if order.status != 'in-process':
            return Response(
                {"error": "Only in-process orders can be rejected by admin."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'admin-rejected'
        order.admin_rejection_notes = request.data.get('rejection_notes', '')
        order.rejected_by_admin = request.user
        order.save()

        return Response({
            "message": "Order rejected by admin.",
            "order_no": order_no,
            "status": "admin-rejected",
            "rejected_by": request.user.username,
        }, status=status.HTTP_200_OK)

class NewOrdersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        new_orders = Order.objects.filter(status='in-process', craftsman__isnull=True)
        serializer = OrderSerializer(new_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

        
class OrderList(generics.GenericAPIView):
    
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """
        Get all Order or filter by `bp_code`.
        """
        bp_code = request.query_params.get("bp_code")
        queryset = self.get_queryset().filter(bp_code=bp_code) if bp_code else self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
        
class OrderDetailView(generics.GenericAPIView):
    """
    - GET: Retrieve a Order by bp_code.
    - PUT: Update a Order.
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    

    def get_object(self, order_no):
        """Helper method to get the object or return 404 using bp_code."""
        return get_object_or_404(Order, order_no=order_no)

    def get(self, request, order_no, *args, **kwargs):
        """Retrieve a Order by bp_code."""
        instance = self.get_object(order_no)
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, order_no, *args, **kwargs):
        """Update an existing Order using bp_code."""
        instance = self.get_object(order_no)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AssignOrdersToCraftsman(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = OrderAssignmentSerializer
    
    def get(self, request):
         """Return all new orders (in-process) and available craftsmen."""
         new_orders = Order.objects.filter(status="in-process")
         craftsmen = BusinessPartner.objects.filter(role='CRAFTSMAN')

         craftsman_serializer = CraftsmanSerializer(craftsmen, many=True)

         return Response({
             "craftsmen": craftsman_serializer.data
         })

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        return Response({
            "message": f"Order {order.id} assigned to {order.craftsman.full_name}",
            "order_no": order.id,
            "assigned_to": order.craftsman.full_name,
            "due_date": order.due_date.strftime('%Y-%m-%d') if order.due_date else None,
            "status": order.status
        }, status=status.HTTP_200_OK)

            
    
class AssignedOrdersList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return all orders assigned to a craftsman (regardless of status)."""
        assigned_orders = Order.objects.filter(craftsman__isnull=False)
        order_serializer = OrderCraftsmanSerializer(assigned_orders, many=True)

        return Response({
            "orders": order_serializer.data
        })

class CraftsmanOrderResponse(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = OrderActionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        order = result['order']

        if result["status"] == "success":
            return Response({
                "message": result["message"],
                "order_no": order.order_no,
                "status": order.status,
                "craftsman": result["craftsman"].full_name
            }, status=status.HTTP_200_OK)

        elif result["status"] == "rejected":
            return Response({
                "message": f"Order {order.order_no} rejected by {result['previous_craftsman'].full_name}",
                "order_no": order.order_no,
                "status": order.status,
                "rejection_reason": result["rejection_reason"]
            }, status=status.HTTP_200_OK)
    
class OrderInProcessAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(status='in-process', craftsman__isnull=False)
        serializer = OrderCraftsmanSerializer(orders, many=True)
        return Response(serializer.data)
    
class ApproveOrderView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = ApprovalSerializer

    def get(self, request):
        orders = self.get_queryset().filter(status="in-process",  craftsman__isnull=False)
        order_data = [
            {
                "order_no": order.order_no,
                "status": order.status,
            }
            for order in orders
        ]
        return Response({"orders": order_data})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            "order_no": result["order"].order_no,
            "status": result["order"].status,
            "message": result["message"]
        }, status=status.HTTP_200_OK)


class CompletedOrdersView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()
    serializer_class = OrderCompletionSerializer
    
    def get(self, request):
        completed_orders = Order.objects.filter(status="complete")
        serializer = OrderCraftsmanSerializer(completed_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            "order_no": result["order"].order_no,
            "status": result["order"].status,
            "message": result["message"]
        }, status=status.HTTP_200_OK)
        
class RejectedOrdersView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderReassignSerializer
    
    def get(self, request):
        # Query all rejected orders with related craftsman info
        rejected_orders_qs = Order.objects.filter(status="rejected").select_related("rejected_by").values(
            'order_no',
            'rejected_by__full_name',
            'rejected_by__bp_code',
            'rejected_by__business_name',
        )
        
        total_rejected = rejected_orders_qs.count()
        rejected_orders = list(rejected_orders_qs)

        return Response({
            "rejected_orders": rejected_orders,
            "total_rejected": total_rejected
        }, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        order = result["order"]
        order_no = result["order_no"]

        return Response({
            "message": f"Order {order_no} assigned to {order.craftsman.full_name}",
            "order_no": order_no,
            "assigned_to": order.craftsman.full_name,
            "due_date": order.due_date.strftime('%Y-%m-%d') if order.due_date else None,
            "status": order.status
        }, status=status.HTTP_200_OK)        

    
# class RejectedOrdersView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         # Query all rejected orders with related craftsman info
#         rejected_orders_qs = Order.objects.filter(status="rejected").select_related("rejected_by").values(
#             'order_no',
#             'rejected_by__full_name',
#             'rejected_by__bp_code',
#             'rejected_by__business_name',
#         )
        
#         total_rejected = rejected_orders_qs.count()
#         rejected_orders = list(rejected_orders_qs)

#         return Response({
#             "rejected_orders": rejected_orders,
#             "total_rejected": total_rejected
#         }, status=status.HTTP_200_OK)
    
# class OrderReassignmentView(APIView):
    
#     permission_classes = [IsAuthenticated]
#     queryset = Order.objects.all()
#     serializer_class = OrderReassignSerializer
    
#     def post(self, request, *args, **kwargs):
#         serializer = self.serializer_class(
#             data=request.data,
#             context={'request': request}
#         )
#         serializer.is_valid(raise_exception=True)
#         result = serializer.save()

#         order = result["order"]
#         order_no = result["order_no"]

#         return Response({
#             "message": f"Order {order_no} assigned to {order.craftsman.full_name}",
#             "order_no": order_no,
#             "assigned_to": order.craftsman.full_name,
#             "due_date": order.due_date.strftime('%Y-%m-%d') if order.due_date else None,
#             "status": order.status
#         }, status=status.HTTP_200_OK)

