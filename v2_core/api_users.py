"""
REST API views for Users
"""
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def users_list(request):
    """
    Get list of all users (for opponent selection)
    GET /api/users/
    """
    current_user = request.user

    # Get all users except current user
    users = User.objects.exclude(id=current_user.id).filter(is_active=True).order_by('username')

    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email
        })

    return Response({
        'users': users_data,
        'count': len(users_data)
    })
